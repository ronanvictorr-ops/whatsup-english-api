import asyncio
import hashlib
import hmac
import json
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import main
from wingo import security, webhook
from database import Base
from models import (
    OutboundDeliveryDB,
    ProcessedWebhookMessageDB,
    StudentDB,
)


class FakeRequest:
    def __init__(self, payload, headers=None):
        self.payload = payload
        self.headers = headers or {}

    async def json(self):
        return self.payload

    async def body(self):
        return json.dumps(self.payload, separators=(",", ":")).encode("utf-8")


def text_payload(message_id="wamid.1", text="hello"):
    return {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "id": message_id,
                                    "from": "5511999999999",
                                    "type": "text",
                                    "text": {"body": text},
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }


class WebhookIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        self.sent = []
        self.process_calls = 0

        student = StudentDB(
            phone="5511999999999",
            email="5511999999999@whatsapp.local",
            password="test",
            name="Test Student",
            learning_goal="Conversation",
            interests="travel",
            current_stage=0,
            current_lesson=1,
            lesson_stage="context_question",
            messages_in_current_lesson=0,
            xp=0,
        )
        self.db.add(student)
        self.db.commit()

        self.patches = [
            patch.object(main, "record_metric"),
            patch.object(main, "mark_student_audio_request_if_needed"),
            patch.object(main, "send_pronunciation_audio_if_needed"),
        ]
        for active_patch in self.patches:
            active_patch.start()

    def tearDown(self):
        for active_patch in reversed(self.patches):
            active_patch.stop()
        self.db.close()
        self.engine.dispose()

    def process(self, phone, message, db):
        self.process_calls += 1
        student = db.query(StudentDB).filter(StudentDB.phone == phone).one()
        student.current_stage = 2
        db.commit()
        return "first reply"

    def sender(self, phone, reply):
        self.sent.append((phone, reply))
        return {"messages": [{"id": f"meta-{len(self.sent)}"}]}

    def receive(self, payload):
        return asyncio.run(main.receive_message(FakeRequest(payload), self.db))

    def test_duplicate_webhook_processes_and_sends_once(self):
        payload = text_payload()
        with patch.object(main, "process_whatsapp_message", side_effect=self.process), patch.object(
            main, "send_whatsapp_reply", side_effect=self.sender
        ):
            self.receive(payload)
            self.receive(payload)

        self.assertEqual(self.process_calls, 1)
        self.assertEqual(len(self.sent), 1)
        inbound = self.db.query(ProcessedWebhookMessageDB).one()
        self.assertEqual(inbound.status, "completed")

    def test_multiple_replies_have_independent_delivery_keys(self):
        with patch.object(
            main,
            "process_whatsapp_message",
            return_value=["first reply", "second reply"],
        ), patch.object(main, "send_whatsapp_reply", side_effect=self.sender), patch.object(
            main, "send_whatsapp_typing_indicator"
        ) as typing, patch.object(webhook, "sleep") as wait:
            self.receive(text_payload(message_id="wamid.multi"))

        deliveries = self.db.query(OutboundDeliveryDB).order_by(OutboundDeliveryDB.id).all()
        self.assertEqual(len(self.sent), 2)
        typing.assert_called_once_with("wamid.multi")
        wait.assert_called_once()
        self.assertEqual(
            [item.idempotency_key for item in deliveries],
            ["wamid.multi:0", "wamid.multi:1"],
        )
        self.assertTrue(all(item.status == "sent" for item in deliveries))

    def test_return_after_thirty_minutes_adds_welcome_before_normal_reply(self):
        student = self.db.query(StudentDB).one()
        student.last_activity = datetime.utcnow() - timedelta(minutes=31)
        self.db.commit()

        with patch.object(main, "process_whatsapp_message", side_effect=self.process), patch.object(
            main, "send_whatsapp_reply", side_effect=self.sender
        ), patch.object(main, "send_whatsapp_typing_indicator"), patch.object(webhook, "sleep"):
            self.receive(text_payload(message_id="wamid.returning", text="quero estudar hoje"))

        self.assertEqual(len(self.sent), 2)
        self.assertEqual(self.sent[0][1]["type"], "buttons")
        self.assertIn("Que bom que", self.sent[0][1]["body"])
        self.assertEqual(
            [button["id"] for button in self.sent[0][1]["buttons"]],
            ["return:practice", "return:continue", "return:topic"],
        )
        self.assertEqual(self.sent[1][1], "first reply")

    def test_plain_greeting_after_break_does_not_send_duplicate_return_prompt(self):
        student = self.db.query(StudentDB).one()
        student.last_activity = datetime.utcnow() - timedelta(minutes=31)
        self.db.commit()

        with patch.object(main, "process_whatsapp_message", side_effect=self.process), patch.object(
            main, "send_whatsapp_reply", side_effect=self.sender
        ):
            self.receive(text_payload(message_id="wamid.greeting-return", text="Bom dia"))

        self.assertEqual(len(self.sent), 1)
        self.assertEqual(self.sent[0][1], "first reply")

    def test_control_command_after_break_does_not_send_return_prompt(self):
        student = self.db.query(StudentDB).one()
        student.last_activity = datetime.utcnow() - timedelta(minutes=31)
        self.db.commit()

        with patch.object(main, "process_whatsapp_message", return_value="aula encerrada"), patch.object(
            main, "send_whatsapp_reply", side_effect=self.sender
        ):
            self.receive(text_payload(message_id="wamid.finish", text="Encerrar aula"))

        self.assertEqual(len(self.sent), 1)
        self.assertEqual(self.sent[0][1], "aula encerrada")

    def test_finish_lesson_typo_after_break_does_not_send_return_prompt(self):
        student = self.db.query(StudentDB).one()
        student.last_activity = datetime.utcnow() - timedelta(minutes=31)
        self.db.commit()

        with patch.object(main, "process_whatsapp_message", return_value="aula encerrada"), patch.object(
            main, "send_whatsapp_reply", side_effect=self.sender
        ):
            self.receive(text_payload(message_id="wamid.finish-typo", text="Vamos finalizei a aula"))

        self.assertEqual(len(self.sent), 1)
        self.assertEqual(self.sent[0][1], "aula encerrada")

    def test_return_prompt_failure_rolls_back_before_fallback_buttons(self):
        student = self.db.query(StudentDB).one()

        with patch.object(
            main,
            "build_smart_return_prompt",
            side_effect=RuntimeError("prompt failed"),
        ), patch.object(self.db, "rollback", wraps=self.db.rollback) as rollback:
            prompt = webhook.build_return_choice_buttons(student, self.db)

        rollback.assert_called()
        self.assertEqual(prompt["type"], "buttons")
        self.assertEqual(
            [button["id"] for button in prompt["buttons"]],
            ["return:continue", "return:review", "return:topic"],
        )

    def test_reply_delay_is_longer_after_video(self):
        text_delay = webhook.reply_delay_seconds("Mensagem curta.")
        video_delay = webhook.reply_delay_seconds(
            {
                "type": "video",
                "caption": "Assista este video rapido antes de responder.",
            }
        )

        self.assertGreater(video_delay, text_delay)

    def test_delivery_failure_restores_state_and_retry_completes(self):
        send_attempts = 0

        def flaky_sender(phone, reply):
            nonlocal send_attempts
            send_attempts += 1
            if send_attempts == 1:
                raise RuntimeError("Meta unavailable")
            return {"messages": [{"id": "meta-recovered"}]}

        payload = text_payload(message_id="wamid.retry")
        with patch.object(main, "process_whatsapp_message", side_effect=self.process), patch.object(
            main, "send_whatsapp_reply", side_effect=flaky_sender
        ):
            with self.assertRaises(main.HTTPException) as failure:
                self.receive(payload)
            self.assertEqual(failure.exception.status_code, 503)
            student = self.db.query(StudentDB).one()
            inbound = self.db.query(ProcessedWebhookMessageDB).one()
            self.assertEqual(student.current_stage, 0)
            self.assertEqual(inbound.status, "failed")

            self.receive(payload)

        student = self.db.query(StudentDB).one()
        inbound = self.db.query(ProcessedWebhookMessageDB).one()
        delivery = self.db.query(OutboundDeliveryDB).one()
        self.assertEqual(student.current_stage, 2)
        self.assertEqual(inbound.status, "completed")
        self.assertEqual(inbound.attempts, 2)
        self.assertEqual(delivery.status, "sent")
        self.assertEqual(delivery.attempts, 2)
        self.assertEqual(send_attempts, 2)

    def test_processing_failure_for_ready_student_sends_non_looping_recovery(self):
        student = self.db.query(StudentDB).one()
        student.current_stage = 7
        student.learning_goal = "Travel"
        student.interests = "work"
        student.assessment_completed = "Yes"
        student.schedule_completed = "Yes"
        student.lesson_stage = "completed"
        self.db.commit()

        with patch.object(
            main,
            "process_whatsapp_message",
            side_effect=RuntimeError("openai temporary failure"),
        ), patch.object(main, "send_whatsapp_reply", side_effect=self.sender):
            result = self.receive(text_payload(message_id="wamid.ready-failure", text="Vamos comecar"))

        self.assertEqual(result, {"status": "recovered"})
        self.assertEqual(len(self.sent), 1)
        recovery = self.sent[0][1]
        self.assertEqual(recovery["type"], "buttons")
        self.assertIn("nao vou te prender em loop", recovery["body"])
        self.assertNotIn("vamos comecar", recovery["body"].lower())

        inbound = self.db.query(ProcessedWebhookMessageDB).filter_by(
            message_id="wamid.ready-failure"
        ).one()
        self.assertEqual(inbound.status, "completed")

    def test_processing_duplicate_returns_retryable_status(self):
        self.db.add(
            ProcessedWebhookMessageDB(
                message_id="wamid.processing",
                phone="5511999999999",
                status="processing",
                created_at=datetime.utcnow(),
            )
        )
        self.db.commit()

        with self.assertRaises(main.HTTPException) as failure:
            self.receive(text_payload(message_id="wamid.processing"))

        self.assertEqual(failure.exception.status_code, 409)

    def test_meta_signature_is_verified_when_required(self):
        payload = b'{"entry":[]}'
        secret = "test-meta-secret"
        signature = "sha256=" + hmac.new(
            secret.encode("utf-8"), payload, hashlib.sha256
        ).hexdigest()

        with patch.object(
            security, "meta_signature_required", return_value=True
        ), patch.dict("os.environ", {"META_APP_SECRET": secret}):
            main.verify_meta_webhook_signature(payload, signature)
            with self.assertRaises(main.HTTPException) as failure:
                main.verify_meta_webhook_signature(payload, "sha256=invalid")

        self.assertEqual(failure.exception.status_code, 401)

    def test_health_reports_stuck_processing_and_sending(self):
        stale = datetime.utcnow() - timedelta(minutes=10)
        self.db.add(
            ProcessedWebhookMessageDB(
                message_id="stuck-inbound",
                phone="5511",
                status="processing",
                created_at=stale,
            )
        )
        self.db.add(
            OutboundDeliveryDB(
                idempotency_key="stuck-outbound",
                phone="5511",
                status="sending",
                created_at=stale,
            )
        )
        self.db.commit()

        health = main.operational_health(self.db)

        self.assertEqual(health["status"], "degraded")
        self.assertEqual(health["stuck_inbound_messages"], 1)
        self.assertEqual(health["stuck_outbound_deliveries"], 1)


if __name__ == "__main__":
    unittest.main()
