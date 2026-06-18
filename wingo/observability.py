import json
import os
from datetime import datetime

from database import SessionLocal
from models import OperationalMetricDB, StateTransitionDB
from wingo.states import is_transition_allowed, state_name


def log_event(event: str, **fields) -> None:
    payload = {
        "timestamp": datetime.utcnow().isoformat(),
        "event": event,
        **fields,
    }
    print(json.dumps(payload, ensure_ascii=False, default=str))


def estimate_openai_cost(input_tokens: int, output_tokens: int) -> float:
    input_rate = float(os.getenv("OPENAI_INPUT_COST_PER_MILLION", "0"))
    output_rate = float(os.getenv("OPENAI_OUTPUT_COST_PER_MILLION", "0"))
    return round(
        (input_tokens / 1_000_000) * input_rate
        + (output_tokens / 1_000_000) * output_rate,
        8,
    )


def record_metric(
    service: str,
    operation: str,
    status: str,
    latency_ms: float,
    attempts: int = 1,
    input_tokens: int = 0,
    output_tokens: int = 0,
    error_type: str | None = None,
) -> None:
    db = SessionLocal()
    try:
        db.add(
            OperationalMetricDB(
                service=service,
                operation=operation,
                status=status,
                latency_ms=latency_ms,
                attempts=attempts,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                estimated_cost_usd=estimate_openai_cost(
                    input_tokens,
                    output_tokens,
                ),
                error_type=error_type,
            )
        )
        db.commit()
    except Exception as error:
        db.rollback()
        log_event("metric_record_failed", error=str(error))
    finally:
        db.close()


def audit_transition(
    db,
    student,
    previous_stage: int,
    message_id: str | None,
    flow: str,
    decision: str,
    message: str,
) -> None:
    next_stage = int(student.current_stage or 0)
    transition_allowed = is_transition_allowed(previous_stage, next_stage)
    student.canonical_state = state_name(next_stage)
    db.add(
        StateTransitionDB(
            student_id=student.id,
            message_id=message_id,
            previous_state=state_name(previous_stage),
            next_state=state_name(next_stage),
            flow=flow,
            decision=(
                (decision or "")[:170]
                + (" [invalid transition]" if not transition_allowed else "")
            ),
            message_excerpt=(message or "")[:300],
        )
    )
    log_event(
        "state_transition",
        student_id=student.id,
        message_id=message_id,
        previous_state=state_name(previous_stage),
        next_state=state_name(next_stage),
        flow=flow,
        decision=(decision or "")[:120],
        transition_allowed=transition_allowed,
    )
