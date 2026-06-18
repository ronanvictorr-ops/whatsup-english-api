from wingo.states import ConversationState

FLOW_NAME = "lesson"
STATES = {
    ConversationState.LESSON,
    ConversationState.LESSON_INVITATION,
    ConversationState.PRE_LESSON_REVIEW,
}
