import os
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import main
from database import Base
from models import LessonSessionDB, StudentDB


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        self.student = StudentDB(
            name="Ana",
            email="ana@example.com",
            password="hashed",
            phone="5511999999999",
            level="Basic 2",
            preferred_language="Portuguese",
            learning_goal="Travel",
            interests="music",
            current_lesson=2,
            lesson_stage="exercise_1",
            current_stage=7,
            assessment_completed="Yes",
            schedule_completed="Yes",
            lesson_schedule='[{"day":"daily","time":"19:00"}]',
            engagement_minutes=42,
            xp=18,
            streak_days=4,
            last_activity=datetime.utcnow(),
        )
        self.db.add(self.student)
        self.db.commit()
        self.db.refresh(self.student)

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_student_dashboard_uses_authenticated_student_id(self):
        result = main.dashboard_student(
            db=self.db,
            current_user={"student_id": self.student.id},
        )

        self.assertEqual(result["name"], "Ana")
        self.assertEqual(result["xp"], 18)
        self.assertEqual(result["streak_days"], 4)
        self.assertGreater(result["lesson_progress_percent"], 0)
        self.assertNotIn("password", result)

    def test_student_dashboard_rejects_unknown_identity(self):
        with self.assertRaises(HTTPException) as raised:
            main.dashboard_student(db=self.db, current_user={"student_id": 999})
        self.assertEqual(raised.exception.status_code, 404)

    def test_admin_key_is_required_and_compared(self):
        with patch.dict(os.environ, {"DASHBOARD_ADMIN_TOKEN": "strong-test-key"}):
            self.assertTrue(main.require_dashboard_admin("strong-test-key"))
            with self.assertRaises(HTTPException) as raised:
                main.require_dashboard_admin("wrong-key")
        self.assertEqual(raised.exception.status_code, 401)

    def test_teacher_dashboard_aggregates_class(self):
        self.db.add(
            LessonSessionDB(
                student_id=self.student.id,
                lesson_number=1,
                lesson_title="Greetings",
                status="completed",
            )
        )
        self.db.commit()

        result = main.dashboard_teacher(db=self.db, admin=True)

        self.assertEqual(result["summary"]["total_students"], 1)
        self.assertEqual(result["summary"]["active_students"], 1)
        self.assertEqual(result["summary"]["completed_lessons"], 1)
        self.assertEqual(result["summary"]["total_xp"], 18)
        self.assertEqual(result["students"][0]["name"], "Ana")

    def test_dashboard_page_points_to_bundled_frontend(self):
        response = main.dashboard_page()
        self.assertEqual(Path(response.path).parts[-2:], ("dashboard", "index.html"))

    def test_sales_page_points_to_bundled_frontend(self):
        response = main.sales_page()
        self.assertEqual(Path(response.path).parts[-2:], ("sales", "index.html"))


if __name__ == "__main__":
    unittest.main()
