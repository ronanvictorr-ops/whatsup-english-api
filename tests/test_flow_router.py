import unittest
from types import SimpleNamespace

from wingo.flows.router import resolve_flow
from wingo.states import ConversationState


class FlowRouterTests(unittest.TestCase):
    def flow(self, stage, lesson_stage="context_question", message="hello"):
        student = SimpleNamespace(current_stage=stage, lesson_stage=lesson_stage)
        return resolve_flow(student, message)

    def test_onboarding_flow(self):
        self.assertEqual(self.flow(ConversationState.ASK_NAME), "onboarding")

    def test_assessment_flow(self):
        self.assertEqual(self.flow(ConversationState.TEST_QUESTION_3), "assessment")

    def test_lesson_flow(self):
        self.assertEqual(self.flow(ConversationState.LESSON), "lesson")

    def test_writing_flow(self):
        self.assertEqual(self.flow(ConversationState.WRITING_PRACTICE), "writing")

    def test_quiz_flow(self):
        self.assertEqual(
            self.flow(ConversationState.LESSON, message="__button__:quiz:test"),
            "quiz",
        )

    def test_bot_flow(self):
        self.assertEqual(
            self.flow(ConversationState.LESSON, lesson_stage="completed"),
            "bot",
        )

    def test_unknown_state_goes_to_recovery(self):
        self.assertEqual(self.flow(12345), "recovery")


if __name__ == "__main__":
    unittest.main()
