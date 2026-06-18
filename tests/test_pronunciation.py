import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import main
from database import Base
from models import ConversationDB, LessonSessionDB, PronunciationAttemptDB, StudentDB
from wingo.pronunciation import (
    assess_pronunciation,
    build_pronunciation_feedback,
    extract_reference_text,
    parse_azure_assessment,
)


class PronunciationTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_extracts_latest_repeat_after_me_phrase(self):
        answer = "Uma explicacao.\n\nRepeat after me:\nI worked yesterday."
        self.assertEqual(extract_reference_text(answer), "I worked yesterday.")

    def test_parses_acoustic_scores_and_phonemes(self):
        payload = {
            "NBest": [{
                "PronunciationAssessment": {
                    "AccuracyScore": 82.4,
                    "FluencyScore": 76.2,
                    "CompletenessScore": 100,
                    "ProsodyScore": 71.5,
                    "PronScore": 80.1,
                },
                "Words": [{
                    "Word": "worked",
                    "PronunciationAssessment": {
                        "AccuracyScore": 62.3,
                        "ErrorType": "Mispronunciation",
                    },
                    "Phonemes": [{
                        "Phoneme": "t",
                        "PronunciationAssessment": {"AccuracyScore": 45.1},
                    }],
                }],
            }],
        }

        result = parse_azure_assessment(payload)

        self.assertEqual(result["accuracy_score"], 82.4)
        self.assertEqual(result["pronunciation_score"], 80.1)
        self.assertEqual(result["words"][0]["word"], "worked")
        self.assertEqual(result["words"][0]["phonemes"][0]["phoneme"], "t")

    def test_without_acoustic_credentials_does_not_invent_scores(self):
        with patch.dict(os.environ, {}, clear=True):
            result = assess_pronunciation(Path("unused.ogg"), "Hello.")

        self.assertEqual(result["status"], "acoustic_unavailable")
        self.assertIsNone(result["accuracy_score"])
        feedback = build_pronunciation_feedback(result, "Hello.", "hello")
        self.assertIn("nao vou inventar", feedback)

    def test_persists_one_attempt_per_webhook_message(self):
        student = StudentDB(
            name="Ana",
            email="pronunciation@example.com",
            password="test",
            phone="5511999999999",
            current_stage=7,
            current_lesson=1,
            lesson_stage="production",
        )
        self.db.add(student)
        self.db.commit()
        session = LessonSessionDB(
            student_id=student.id,
            lesson_number=1,
            lesson_title="Greetings",
            status="started",
            student_audio_requested="Yes",
        )
        conversation = ConversationDB(
            student_id=student.id,
            question="practice",
            answer="Repeat after me:\nHello, my name is Ana.",
        )
        self.db.add_all([session, conversation])
        self.db.commit()
        acoustic_result = {
            "provider": "azure",
            "status": "completed",
            "accuracy_score": 88.0,
            "fluency_score": 81.0,
            "completeness_score": 100.0,
            "prosody_score": 79.0,
            "pronunciation_score": 86.0,
            "words": [],
        }

        with tempfile.NamedTemporaryFile(suffix=".ogg") as audio, patch.object(
            main, "assess_pronunciation", return_value=acoustic_result
        ) as assessor:
            first = main.evaluate_expected_pronunciation(
                student, Path(audio.name), "hello my name is Ana", "wamid.audio", self.db
            )
            second = main.evaluate_expected_pronunciation(
                student, Path(audio.name), "hello my name is Ana", "wamid.audio", self.db
            )

        self.assertEqual(first, second)
        self.assertEqual(assessor.call_count, 1)
        self.assertEqual(self.db.query(PronunciationAttemptDB).count(), 1)
        self.db.refresh(session)
        self.assertEqual(session.student_audio_requested, "No")


if __name__ == "__main__":
    unittest.main()
