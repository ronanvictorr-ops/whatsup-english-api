import unittest
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

import main
from database import Base
from models import ConversationDB, PersonalNoteDB, StudentDB
from wingo import personal_memory


class PersonalMemoryTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def create_student(self):
        student = StudentDB(
            phone="5511999991111",
            email="memory@whatsapp.local",
            password="test",
            name="Ronan",
            level="Basic",
            preferred_language="Portuguese",
            assessment_completed="Yes",
            learning_goal="Conversation",
            interests="travel",
            onboarding_notes="[]",
            current_lesson=1,
            lesson_stage="context_question",
            current_stage=7,
            schedule_completed="Yes",
            xp=0,
        )
        self.db.add(student)
        self.db.commit()
        self.db.refresh(student)
        return student

    def test_topic_request_is_not_relationship_memory(self):
        self.assertFalse(
            personal_memory.should_extract_personal_note("Vamos praticar future")
        )

    def test_personal_note_is_saved_once(self):
        student = self.create_student()
        extracted = [
            {
                "category": "travel",
                "note": "O aluno vai viajar para a Bahia semana que vem.",
            }
        ]

        with patch.object(personal_memory, "extract_personal_notes", return_value=extracted):
            personal_memory.save_personal_notes_if_needed(
                student,
                "Vou viajar pra Bahia semana que vem.",
                self.db,
                get_openai_client=main.get_openai_client,
                call_with_retry=main.call_with_retry,
            )
            personal_memory.save_personal_notes_if_needed(
                student,
                "Vou viajar pra Bahia semana que vem.",
                self.db,
                get_openai_client=main.get_openai_client,
                call_with_retry=main.call_with_retry,
            )

        notes = self.db.query(PersonalNoteDB).filter_by(student_id=student.id).all()
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0].category, "travel")
        self.assertIn("Bahia", notes[0].note)

    def test_relationship_memory_is_injected_into_ai_prompt(self):
        student = self.create_student()
        self.db.add(
            PersonalNoteDB(
                student_id=student.id,
                category="school",
                note="O aluno teve uma prova difícil hoje.",
                source_message="Tive uma prova difícil hoje.",
            )
        )
        self.db.commit()

        fake_client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **kwargs: None))
        )
        fake_response = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="Claro, vamos praticar."))]
        )

        with patch.object(main, "get_openai_client", return_value=fake_client), patch.object(
            main, "call_with_retry", return_value=fake_response
        ) as retry, patch.object(
            main, "save_learning_record_if_needed"
        ), patch.object(
            main, "save_personal_notes_if_needed"
        ):
            main.generate_ai_answer(student, "Bom dia", self.db)

        messages = retry.call_args.kwargs["messages"]
        system_prompt = messages[0]["content"]
        self.assertIn("Personal relationship memory:", system_prompt)
        self.assertIn("prova difícil", system_prompt)
        self.assertIn("Use personal relationship memory naturally", system_prompt)

    def test_relationship_memory_summary_ignores_missing_table(self):
        student = self.create_student()
        self.db.execute(text("DROP TABLE personal_notes"))
        self.db.commit()

        summary = personal_memory.get_recent_personal_notes_summary(student.id, self.db)

        self.assertEqual(summary, "No personal relationship memory saved yet.")
        self.assertEqual(self.db.query(StudentDB).count(), 1)

    def test_generate_ai_answer_uses_safe_fallback_when_openai_fails(self):
        student = self.create_student()

        with patch.object(
            main, "get_openai_client", side_effect=RuntimeError("offline")
        ), patch.object(
            main, "save_learning_record_if_needed"
        ), patch.object(
            main, "save_personal_notes_if_needed"
        ):
            answer = main.generate_ai_answer(student, "Como digo agua?", self.db)

        self.assertIn("correcao inteligente", answer)
        self.assertIn("What do you like?", answer)
        conversation = self.db.query(ConversationDB).filter_by(student_id=student.id).one()
        self.assertEqual(conversation.question, "Como digo agua?")
        self.assertEqual(conversation.answer, answer)

    def test_writing_feedback_uses_safe_fallback_when_openai_fails(self):
        student = self.create_student()

        with patch.object(main, "get_openai_client", side_effect=RuntimeError("offline")):
            answer = main.generate_writing_practice_feedback(
                student,
                "I go to work yesterday.",
                self.db,
            )

        self.assertIn("Past Simple", answer)
        self.assertIn("I studied English yesterday.", answer)
        conversation = self.db.query(ConversationDB).filter_by(student_id=student.id).one()
        self.assertEqual(conversation.question, "I go to work yesterday.")
        self.assertEqual(conversation.answer, answer)


if __name__ == "__main__":
    unittest.main()
