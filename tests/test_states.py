import unittest
from types import SimpleNamespace

from wingo.states import (
    ALLOWED_TRANSITIONS,
    ConversationState,
    infer_recovery_state,
    is_transition_allowed,
    restore_student,
    snapshot_student,
    state_name,
)


def student(**overrides):
    values = {
        "current_stage": ConversationState.LESSON,
        "current_lesson": 22,
        "lesson_stage": "conversation",
        "messages_in_current_lesson": 4,
        "last_lesson_date": "2026-06-18",
        "preferred_language": "Adaptive",
        "assessment_completed": "Yes",
        "schedule_completed": "Yes",
        "lesson_schedule": "[]",
        "xp": 20,
        "name": "Ronan",
        "learning_goal": "Travel",
        "interests": "technology",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class StateMachineTests(unittest.TestCase):
    def test_every_declared_transition_is_allowed(self):
        for previous, next_states in ALLOWED_TRANSITIONS.items():
            for next_state in next_states:
                with self.subTest(previous=previous, next_state=next_state):
                    self.assertTrue(is_transition_allowed(previous, next_state))

    def test_unknown_transition_is_rejected(self):
        self.assertFalse(
            is_transition_allowed(
                ConversationState.ASK_NAME,
                ConversationState.TEST_QUESTION_5,
            )
        )

    def test_snapshot_restores_state_after_delivery_failure(self):
        target = student()
        snapshot = snapshot_student(target)
        target.current_stage = ConversationState.WRITING_PRACTICE
        target.current_lesson = 30
        target.lesson_stage = "completed"
        target.xp = 99
        restore_student(target, snapshot)
        self.assertEqual(target.current_stage, ConversationState.LESSON)
        self.assertEqual(target.current_lesson, 22)
        self.assertEqual(target.lesson_stage, "conversation")
        self.assertEqual(target.xp, 20)

    def test_recovery_never_requires_deleting_student(self):
        self.assertEqual(
            infer_recovery_state(student(name="")),
            ConversationState.ASK_NAME,
        )
        self.assertEqual(
            infer_recovery_state(student(assessment_completed="No")),
            ConversationState.ASK_EXPERIENCE,
        )
        self.assertEqual(
            infer_recovery_state(student(schedule_completed="No")),
            ConversationState.ASK_SCHEDULE,
        )
        self.assertEqual(infer_recovery_state(student()), ConversationState.LESSON)

    def test_state_names_are_human_readable(self):
        self.assertEqual(state_name(ConversationState.WRITING_PRACTICE), "writing_practice")


if __name__ == "__main__":
    unittest.main()
