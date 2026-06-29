import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from time import perf_counter, sleep
from typing import Any, Callable

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.orm import Session

from database import get_db
from models import ProcessedWebhookMessageDB, StudentDB
from wingo.flows.router import resolve_flow
from wingo.idempotency import (
    claim_inbound_message,
    complete_inbound_message,
    fail_inbound_message,
    send_reply_once,
)
from wingo.observability import audit_transition, log_event
from wingo.phones import mask_phone, normalize_whatsapp_phone
from wingo.rate_limit import enforce_rate_limit
from wingo.security import meta_signature_required, verify_meta_webhook_signature
from wingo.states import restore_student, snapshot_student, state_name


@dataclass(frozen=True)
class WebhookDependencies:
    resolve: Callable[[str], Any]


_dependencies: WebhookDependencies | None = None
router = APIRouter()

RETURN_GREETING_AFTER = timedelta(minutes=30)
DEFAULT_REPLY_DELAY_SECONDS = 1.2
MAX_REPLY_DELAY_SECONDS = 8.0


def build_return_choice_buttons(student: StudentDB | None = None, db: Session | None = None) -> dict:
    if student is not None and db is not None:
        try:
            return _resolve("build_smart_return_prompt")(student, db)
        except Exception as error:
            try:
                db.rollback()
            except Exception:
                pass
            log_event(
                "smart_return_prompt_failed",
                student_id=getattr(student, "id", None),
                error_type=type(error).__name__,
            )

    return {
        "type": "buttons",
        "body": (
            "Que bom que você está de volta! Quer continuar de onde paramos "
            "ou prefere escolher outro caminho agora?"
        ),
        "buttons": [
            {"id": "return:continue", "title": "Continuar aula"},
            {"id": "return:review", "title": "Revisar"},
            {"id": "return:topic", "title": "Mudar tema"},
        ],
    }


def is_plain_greeting(message: str) -> bool:
    normalized = (message or "").strip().lower()
    normalized = normalized.strip("!.? ")
    return normalized in {
        "bom dia",
        "boa tarde",
        "boa noite",
        "oi",
        "ola",
        "olá",
        "hello",
        "hi",
    }


def should_prepend_return_prompt(message: str) -> bool:
    if is_plain_greeting(message):
        return False
    if (message or "").startswith("__button__:"):
        return False
    try:
        return _resolve("detect_control_command")(message) is None
    except Exception:
        return True


def is_returning_after_break(student: StudentDB, now: datetime | None = None) -> bool:
    last_activity = getattr(student, "last_activity", None)
    if not last_activity:
        return False

    current = now or datetime.now(timezone.utc)
    if last_activity.tzinfo is None:
        last_activity = last_activity.replace(tzinfo=timezone.utc)
    return current - last_activity >= RETURN_GREETING_AFTER


def reply_delay_seconds(previous_reply: Any) -> float:
    if os.getenv("WINGO_REPLY_DELAY_ENABLED", "true").lower() in {
        "0",
        "false",
        "no",
    }:
        return 0.0

    base_delay = float(
        os.getenv("WINGO_REPLY_DELAY_BASE_SECONDS", DEFAULT_REPLY_DELAY_SECONDS)
    )
    max_delay = float(
        os.getenv("WINGO_REPLY_DELAY_MAX_SECONDS", MAX_REPLY_DELAY_SECONDS)
    )

    if isinstance(previous_reply, dict) and previous_reply.get("type") == "video":
        text = previous_reply.get("caption") or ""
        return min(max_delay, max(base_delay + 3.0, 4.0 + len(text) / 160))

    text = str(previous_reply or "")
    return min(max_delay, max(base_delay, len(text) / 90))


def send_typing_indicator_if_available(message_id: str | None) -> None:
    if not message_id:
        return

    try:
        _resolve("send_whatsapp_typing_indicator")(message_id)
    except Exception as error:
        log_event(
            "typing_indicator_skipped",
            message_id=message_id,
            error=str(error),
        )


def configure_webhook(dependencies: WebhookDependencies) -> None:
    global _dependencies
    _dependencies = dependencies


def _resolve(name: str):
    if _dependencies is None:
        raise RuntimeError("Webhook dependencies were not configured")
    return _dependencies.resolve(name)


@router.get("/meta-webhook")
def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
):
    if hub_mode == "subscribe" and hub_verify_token == os.getenv("META_VERIFY_TOKEN"):
        return Response(content=hub_challenge, media_type="text/plain")
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/meta-webhook")
async def receive_message(request: Request, db: Session = Depends(get_db)):
    webhook_started = perf_counter()
    if meta_signature_required():
        raw_payload = await request.body()
        verify_meta_webhook_signature(
            raw_payload,
            request.headers.get("X-Hub-Signature-256"),
        )
        try:
            data = json.loads(raw_payload)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Payload JSON invalido")
    else:
        data = await request.json()

    inbound_record = None
    state_snapshot = None
    flow_name = "unknown"
    delivery_started = False
    student = None
    phone = None
    message_id = None
    message = ""
    incoming_audio_path = None
    pronunciation_feedback = None

    try:
        value = data["entry"][0]["changes"][0]["value"]
        if "messages" not in value:
            return {"status": "ok"}

        incoming_message = value["messages"][0]
        phone = normalize_whatsapp_phone(incoming_message["from"])
        message_id = incoming_message.get("id")
        message_type = incoming_message.get("type")

        enforce_rate_limit(
            "webhook",
            phone,
            default_limit=60,
            default_window_seconds=60,
        )

        inbound_record, should_process = claim_inbound_message(
            db, message_id, phone
        )
        if not should_process:
            log_event(
                "inbound_duplicate_skipped",
                message_id=message_id,
                phone=mask_phone(phone),
            )
            if inbound_record and inbound_record.status == "completed":
                return {"status": "ok"}
            raise HTTPException(status_code=409, detail="Mensagem ainda em processamento")

        if message_type == "text":
            message = incoming_message.get("text", {}).get("body", "").strip()
        elif message_type == "interactive":
            interactive = incoming_message.get("interactive", {})
            interactive_type = interactive.get("type")
            if interactive_type == "button_reply":
                button = interactive.get("button_reply", {})
                message = f"__button__:{button.get('id', '')}::{button.get('title', '')}"
            elif interactive_type == "list_reply":
                message = interactive.get("list_reply", {}).get("title", "").strip()
        elif message_type == "audio":
            media_id = incoming_message.get("audio", {}).get("id")
            if not media_id:
                _send_terminal_reply(
                    db,
                    message_id,
                    phone,
                    "unsupported",
                    "Nao consegui abrir esse audio. Pode tentar mandar novamente?",
                )
                complete_inbound_message(db, inbound_record)
                return {"status": "ok"}

            incoming_audio_path = _resolve("download_whatsapp_audio")(media_id)
            try:
                transcript = _resolve("transcribe_audio_file")(incoming_audio_path)
            except Exception:
                incoming_audio_path.unlink(missing_ok=True)
                incoming_audio_path = None
                raise

            if not transcript:
                incoming_audio_path.unlink(missing_ok=True)
                incoming_audio_path = None
                _send_terminal_reply(
                    db,
                    message_id,
                    phone,
                    "transcription_failed",
                    "Nao consegui entender o audio. Pode gravar de novo, bem curtinho?",
                )
                complete_inbound_message(db, inbound_record)
                return {"status": "ok"}
            message = f"[Voice note transcription] {transcript}"
        else:
            _send_unsupported_reply(db, message_id, phone)
            complete_inbound_message(db, inbound_record)
            return {"status": "ok"}

        if not message:
            _send_unsupported_reply(db, message_id, phone, suffix="empty")
            complete_inbound_message(db, inbound_record)
            return {"status": "ok"}

        log_event(
            "inbound_message_received",
            message_id=message_id,
            message_type=message_type,
            phone=mask_phone(phone),
        )

        student = _resolve("get_or_create_whatsapp_student")(phone, db)
        returning_after_break = is_returning_after_break(student)
        state_snapshot = snapshot_student(student)
        if incoming_audio_path:
            try:
                pronunciation_feedback = _resolve("evaluate_expected_pronunciation")(
                    student=student,
                    audio_path=incoming_audio_path,
                    transcript=transcript,
                    message_id=message_id,
                    db=db,
                )
            finally:
                incoming_audio_path.unlink(missing_ok=True)
                incoming_audio_path = None

        flow_name = resolve_flow(student, message)
        log_event(
            "message_processing_started",
            message_id=message_id,
            student_id=student.id,
            flow=flow_name,
            state=state_name(state_snapshot.current_stage),
        )

        reply = _resolve("process_whatsapp_message")(
            phone=phone,
            message=message,
            db=db,
        )
        replies = reply if isinstance(reply, list) else [reply]
        if returning_after_break and should_prepend_return_prompt(message):
            replies = [
                build_return_choice_buttons(student, db),
                *replies,
            ]
        if pronunciation_feedback:
            replies = [pronunciation_feedback, *replies]

        delivery_started = True
        for reply_index, reply_message in enumerate(replies):
            if reply_index > 0:
                send_typing_indicator_if_available(message_id)
                delay = reply_delay_seconds(replies[reply_index - 1])
                if delay > 0:
                    sleep(delay)

            send_reply_once(
                db=db,
                idempotency_key=f"{message_id or phone}:{reply_index}",
                phone=phone,
                reply=reply_message,
                sender=_resolve("send_whatsapp_reply"),
                reply_text=_resolve("get_reply_text"),
            )

        get_reply_text = _resolve("get_reply_text")
        reply_text = "\n".join(get_reply_text(item) for item in replies)
        student = db.query(StudentDB).filter(StudentDB.phone == phone).first()
        _resolve("mark_student_audio_request_if_needed")(student, reply_text, db)
        _resolve("send_pronunciation_audio_if_needed")(
            phone=phone,
            question=message,
            answer=reply_text,
            student=student,
            db=db,
        )

        student = db.query(StudentDB).filter(StudentDB.id == student.id).first()
        audit_transition(
            db=db,
            student=student,
            previous_stage=state_snapshot.current_stage,
            message_id=message_id,
            flow=flow_name,
            decision=reply_text,
            message=message,
        )
        db.commit()
        complete_inbound_message(db, inbound_record)
        log_event(
            "message_processing_completed",
            message_id=message_id,
            student_id=student.id,
            flow=flow_name,
            state=state_name(student.current_stage),
        )
        _resolve("record_metric")(
            "application",
            "webhook",
            "success",
            (perf_counter() - webhook_started) * 1000,
        )
    except Exception as error:
        if isinstance(error, HTTPException) and error.status_code < 500:
            raise
        if incoming_audio_path:
            try:
                incoming_audio_path.unlink(missing_ok=True)
            except OSError:
                pass

        log_event(
            "message_processing_failed",
            message_id=message_id,
            phone=mask_phone(phone),
            flow=flow_name,
            delivery_started=delivery_started,
            error=str(error),
            error_type=type(error).__name__,
        )
        _resolve("record_metric")(
            "application",
            "webhook",
            "error",
            (perf_counter() - webhook_started) * 1000,
            error_type=type(error).__name__,
        )
        try:
            db.rollback()
            if phone and state_snapshot:
                student = db.query(StudentDB).filter(StudentDB.phone == phone).first()
                if student:
                    restore_student(student, state_snapshot)
                    student.canonical_state = state_name(state_snapshot.current_stage)
                    student.last_activity = datetime.utcnow()
                    db.commit()

                    if not delivery_started:
                        recovery_reply = _resolve("recover_student_flow")(student, db)
                        send_reply_once(
                            db=db,
                            idempotency_key=f"{message_id or phone}:recovery",
                            phone=phone,
                            reply=recovery_reply,
                            sender=_resolve("send_whatsapp_reply"),
                            reply_text=_resolve("get_reply_text"),
                        )
                        inbound_record = _find_inbound(db, message_id)
                        complete_inbound_message(db, inbound_record)
                        return {"status": "recovered"}

            inbound_record = _find_inbound(db, message_id)
            fail_inbound_message(db, inbound_record, error)
        except Exception as recovery_error:
            db.rollback()
            log_event(
                "automatic_recovery_failed",
                message_id=message_id,
                error=str(recovery_error),
            )
        raise HTTPException(status_code=503, detail="Falha temporaria no processamento")

    return {"status": "ok"}


def _find_inbound(db: Session, message_id: str | None):
    if not message_id:
        return None
    return db.query(ProcessedWebhookMessageDB).filter(
        ProcessedWebhookMessageDB.message_id == message_id
    ).first()


def _send_terminal_reply(
    db: Session,
    message_id: str | None,
    phone: str,
    suffix: str,
    reply: str,
):
    send_reply_once(
        db=db,
        idempotency_key=f"{message_id or phone}:{suffix}",
        phone=phone,
        reply=reply,
        sender=_resolve("send_whatsapp_reply"),
        reply_text=_resolve("get_reply_text"),
    )


def _send_unsupported_reply(
    db: Session,
    message_id: str | None,
    phone: str,
    suffix: str = "unsupported",
):
    _send_terminal_reply(
        db,
        message_id,
        phone,
        suffix,
        "Por enquanto consigo responder mensagens de texto e audio. "
        "Me envie uma frase, pergunta ou audio curto.",
    )
