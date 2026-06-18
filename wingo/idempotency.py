from datetime import datetime, timedelta

from sqlalchemy.exc import IntegrityError

from models import OutboundDeliveryDB, ProcessedWebhookMessageDB
from wingo.observability import log_event


def claim_inbound_message(db, message_id: str | None, phone: str) -> tuple[object | None, bool]:
    if not message_id:
        return None, True

    record = db.query(ProcessedWebhookMessageDB).filter(
        ProcessedWebhookMessageDB.message_id == message_id
    ).first()

    if record:
        if record.status == "completed":
            return record, False
        if (
            record.status == "processing"
            and record.created_at
            and record.created_at > datetime.utcnow() - timedelta(minutes=5)
        ):
            return record, False
        record.status = "processing"
        record.attempts = (record.attempts or 0) + 1
        record.last_error = None
        db.commit()
        return record, True

    record = ProcessedWebhookMessageDB(
        message_id=message_id,
        phone=phone,
        status="processing",
        attempts=1,
    )
    db.add(record)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.query(ProcessedWebhookMessageDB).filter(
            ProcessedWebhookMessageDB.message_id == message_id
        ).first()
        return existing, False
    return record, True


def complete_inbound_message(db, record) -> None:
    if not record:
        return
    record.status = "completed"
    record.completed_at = datetime.utcnow()
    record.last_error = None
    db.commit()


def fail_inbound_message(db, record, error: Exception) -> None:
    if not record:
        return
    record.status = "failed"
    record.last_error = str(error)[:1000]
    db.commit()


def send_reply_once(
    db,
    idempotency_key: str,
    phone: str,
    reply,
    sender,
    reply_text,
):
    delivery = db.query(OutboundDeliveryDB).filter(
        OutboundDeliveryDB.idempotency_key == idempotency_key
    ).first()

    if delivery and delivery.status == "sent":
        log_event("outbound_duplicate_skipped", idempotency_key=idempotency_key)
        return None

    if not delivery:
        delivery = OutboundDeliveryDB(
            idempotency_key=idempotency_key,
            phone=phone,
            message_type=reply.get("type", "text") if isinstance(reply, dict) else "text",
            payload_excerpt=reply_text(reply)[:500],
            status="pending",
            attempts=0,
        )
        db.add(delivery)

    delivery.status = "sending"
    delivery.attempts = (delivery.attempts or 0) + 1
    delivery.last_error = None
    db.commit()

    try:
        result = sender(phone, reply)
        message_id = None
        if isinstance(result, dict):
            messages = result.get("messages") or []
            if messages:
                message_id = messages[0].get("id")
        delivery.status = "sent"
        delivery.meta_message_id = message_id
        delivery.completed_at = datetime.utcnow()
        db.commit()
        return result
    except Exception as error:
        db.rollback()
        delivery = db.query(OutboundDeliveryDB).filter(
            OutboundDeliveryDB.idempotency_key == idempotency_key
        ).first()
        if delivery:
            delivery.status = "failed"
            delivery.last_error = str(error)[:1000]
            db.commit()
        raise
