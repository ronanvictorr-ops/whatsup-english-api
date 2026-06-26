import unittest
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import main
from database import Base
from models import PersonalNoteDB, StudentDB
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


if __name__ == "__main__":
    unittest.main()
