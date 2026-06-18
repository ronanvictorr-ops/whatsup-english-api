from dataclasses import dataclass
from enum import IntEnum


class ConversationState(IntEnum):
    NEW = 0
    ASK_NAME = 2
    ASK_GOAL = 3
    ASK_EXPERIENCE = 4
    ASK_DURATION = 5
    ASK_TEST_CONSENT = 6
    LESSON = 7
    ASK_INTERESTS = 35
    TEST_QUESTION_1 = 50
    TEST_QUESTION_2 = 51
    TEST_QUESTION_3 = 52
    TEST_QUESTION_4 = 53
    TEST_QUESTION_5 = 54
    ASK_SCHEDULE = 70
    LANGUAGE_CONFIRMATION = 80
    ADVANCED_LANGUAGE_CONFIRMATION = 81
    LESSON_INVITATION = 82
    PRE_LESSON_REVIEW = 83
    WRITING_PRACTICE = 84
    RECOVERY = 999


STATE_NAMES = {state.value: state.name.lower() for state in ConversationState}

ALLOWED_TRANSITIONS = {
    ConversationState.NEW: {ConversationState.ASK_NAME},
    ConversationState.ASK_NAME: {ConversationState.ASK_GOAL},
    ConversationState.ASK_GOAL: {ConversationState.ASK_INTERESTS},
    ConversationState.ASK_INTERESTS: {ConversationState.ASK_EXPERIENCE},
    ConversationState.ASK_EXPERIENCE: {
        ConversationState.ASK_DURATION,
        ConversationState.ASK_SCHEDULE,
    },
    ConversationState.ASK_DURATION: {
        ConversationState.ASK_TEST_CONSENT,
        ConversationState.ADVANCED_LANGUAGE_CONFIRMATION,
    },
    ConversationState.ADVANCED_LANGUAGE_CONFIRMATION: {ConversationState.ASK_TEST_CONSENT},
    ConversationState.ASK_TEST_CONSENT: {
        ConversationState.TEST_QUESTION_1,
        ConversationState.ASK_SCHEDULE,
    },
    ConversationState.TEST_QUESTION_1: {ConversationState.TEST_QUESTION_2},
    ConversationState.TEST_QUESTION_2: {ConversationState.TEST_QUESTION_3},
    ConversationState.TEST_QUESTION_3: {ConversationState.TEST_QUESTION_4},
    ConversationState.TEST_QUESTION_4: {ConversationState.TEST_QUESTION_5},
    ConversationState.TEST_QUESTION_5: {ConversationState.ASK_SCHEDULE},
    ConversationState.ASK_SCHEDULE: {ConversationState.LESSON},
    ConversationState.LESSON: {
        ConversationState.LESSON,
        ConversationState.ASK_SCHEDULE,
        ConversationState.LANGUAGE_CONFIRMATION,
        ConversationState.LESSON_INVITATION,
        ConversationState.WRITING_PRACTICE,
    },
    ConversationState.LANGUAGE_CONFIRMATION: {ConversationState.LESSON},
    ConversationState.LESSON_INVITATION: {ConversationState.LESSON, ConversationState.PRE_LESSON_REVIEW},
    ConversationState.PRE_LESSON_REVIEW: {ConversationState.LESSON},
    ConversationState.WRITING_PRACTICE: {ConversationState.WRITING_PRACTICE, ConversationState.LESSON},
}


def state_name(value: int | None) -> str:
    return STATE_NAMES.get(value, f"unknown_{value}")


@dataclass(frozen=True)
class StateSnapshot:
    current_stage: int
    current_lesson: int | None
    lesson_stage: str | None
    messages_in_current_lesson: int
    last_lesson_date: str | None
    preferred_language: str | None
    assessment_completed: str | None
    schedule_completed: str | None
    lesson_schedule: str | None
    xp: int


def snapshot_student(student) -> StateSnapshot:
    return StateSnapshot(
        current_stage=int(student.current_stage or 0),
        current_lesson=student.current_lesson,
        lesson_stage=student.lesson_stage,
        messages_in_current_lesson=student.messages_in_current_lesson or 0,
        last_lesson_date=student.last_lesson_date,
        preferred_language=student.preferred_language,
        assessment_completed=student.assessment_completed,
        schedule_completed=student.schedule_completed,
        lesson_schedule=student.lesson_schedule,
        xp=student.xp or 0,
    )


def restore_student(student, snapshot: StateSnapshot) -> None:
    for field, value in snapshot.__dict__.items():
        setattr(student, field, value)


def infer_recovery_state(student) -> ConversationState:
    if not (student.name or "").strip():
        return ConversationState.ASK_NAME
    if not (student.learning_goal or "").strip():
        return ConversationState.ASK_GOAL
    if not (student.interests or "").strip():
        return ConversationState.ASK_INTERESTS
    if student.assessment_completed != "Yes":
        return ConversationState.ASK_EXPERIENCE
    if student.schedule_completed != "Yes":
        return ConversationState.ASK_SCHEDULE
    return ConversationState.LESSON


def validate_state(value: int | None) -> bool:
    return int(value or 0) in STATE_NAMES


def is_transition_allowed(previous: int, next_: int) -> bool:
    if previous == next_:
        return True
    if next_ in {ConversationState.RECOVERY, ConversationState.ASK_NAME}:
        return True
    try:
        previous_state = ConversationState(previous)
        next_state = ConversationState(next_)
    except ValueError:
        return False
    return next_state in ALLOWED_TRANSITIONS.get(previous_state, set())
