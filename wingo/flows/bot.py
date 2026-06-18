from wingo.states import ConversationState

FLOW_NAME = "bot"
STATES = {ConversationState.LESSON}


def owns(student) -> bool:
    return (
        int(student.current_stage or 0) == ConversationState.LESSON
        and (student.lesson_stage or "") == "completed"
    )
