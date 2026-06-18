from wingo.flows import assessment, bot, lesson, onboarding, quiz, writing
from wingo.states import ConversationState


def resolve_flow(student, message: str = "") -> str:
    if quiz.owns_message(message):
        return quiz.FLOW_NAME
    if bot.owns(student):
        return bot.FLOW_NAME

    try:
        state = ConversationState(int(student.current_stage or 0))
    except ValueError:
        return "recovery"

    for module in (onboarding, assessment, writing, lesson):
        if state in module.STATES:
            return module.FLOW_NAME
    if state == ConversationState.RECOVERY:
        return "recovery"
    return "unknown"
