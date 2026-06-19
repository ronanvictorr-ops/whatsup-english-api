import unittest
from datetime import datetime
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import main
from database import Base
from models import StudentDB


class SecurityAndOperationsTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        self.student = StudentDB(
            phone="5562982853488",
            email="security@example.com",
            password="hashed",
            name="Security Student",
            current_stage=7,
        )
        self.db.add(self.student)
        self.db.commit()
        self.db.refresh(self.student)

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_student_cannot_access_another_student_id(self):
        with self.assertRaises(HTTPException) as failure:
            main.require_student_access(self.student.id + 1, {"student_id": self.student.id})
        self.assertEqual(failure.exception.status_code, 403)

    def test_student_response_never_contains_password(self):
        result = main.get_student(
            self.student.id,
            db=self.db,
            current_user={"student_id": self.student.id},
        )
        self.assertNotIn("password", result)

    def test_phone_variants_resolve_to_one_student(self):
        found = main.get_or_create_whatsapp_student("556282853488", self.db)
        self.assertEqual(found.id, self.student.id)
        self.assertEqual(self.db.query(StudentDB).count(), 1)

    def test_automation_tick_includes_daily_word(self):
        now = datetime(2026, 6, 19, 10, 0)
        with patch.object(main, "send_scheduled_lessons") as scheduled, patch.object(
            main, "send_daily_word_challenges"
        ) as daily, patch.object(main, "send_weekly_quizzes") as quiz, patch.object(
            main, "send_weekly_progress_reports"
        ) as report:
            main.run_academic_automations_once(self.db, now)

        scheduled.assert_called_once_with(self.db, now)
        daily.assert_called_once_with(self.db, now)
        quiz.assert_called_once_with(self.db, now)
        report.assert_called_once_with(self.db, now)


if __name__ == "__main__":
    unittest.main()
