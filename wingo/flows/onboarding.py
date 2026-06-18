from wingo.states import ConversationState

FLOW_NAME = "onboarding"
STATES = {
    ConversationState.NEW,
    ConversationState.ASK_NAME,
    ConversationState.ASK_GOAL,
    ConversationState.ASK_INTERESTS,
    ConversationState.ASK_EXPERIENCE,
    ConversationState.ASK_DURATION,
    ConversationState.ASK_TEST_CONSENT,
    ConversationState.ASK_SCHEDULE,
    ConversationState.LANGUAGE_CONFIRMATION,
    ConversationState.ADVANCED_LANGUAGE_CONFIRMATION,
}
