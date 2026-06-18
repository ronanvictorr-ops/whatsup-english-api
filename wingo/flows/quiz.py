FLOW_NAME = "quiz"
STATES = set()


def owns_message(message: str) -> bool:
    return (message or "").startswith("__button__:quiz:")
