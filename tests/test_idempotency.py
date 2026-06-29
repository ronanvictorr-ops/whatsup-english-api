import unittest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from database import Base
from models import OutboundDeliveryDB
from wingo.idempotency import (
    claim_inbound_message,
    complete_inbound_message,
    fail_inbound_message,
    send_reply_once,
)


class IdempotencyTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_completed_inbound_message_is_not_processed_twice(self):
        record, should_process = claim_inbound_message(self.db, "msg-1", "5511")
        self.assertTrue(should_process)
        complete_inbound_message(self.db, record)
        _, should_process_again = claim_inbound_message(self.db, "msg-1", "5511")
        self.assertFalse(should_process_again)

    def test_failed_inbound_message_can_retry(self):
        record, _ = claim_inbound_message(self.db, "msg-2", "5511")
        fail_inbound_message(self.db, record, RuntimeError("temporary"))
        retried, should_process = claim_inbound_message(self.db, "msg-2", "5511")
        self.assertTrue(should_process)
        self.assertEqual(retried.attempts, 2)

    def test_outbound_reply_is_sent_once(self):
        calls = []

        def sender(phone, reply):
            calls.append((phone, reply))
            return {"messages": [{"id": "meta-1"}]}

        kwargs = {
            "db": self.db,
            "idempotency_key": "msg-3:0",
            "phone": "5511",
            "reply": "hello",
            "sender": sender,
            "reply_text": str,
        }
        send_reply_once(**kwargs)
        send_reply_once(**kwargs)
        self.assertEqual(len(calls), 1)
        delivery = self.db.query(OutboundDeliveryDB).one()
        self.assertEqual(delivery.status, "sent")
        self.assertEqual(delivery.meta_message_id, "meta-1")

    def test_outbound_reply_rolls_back_and_retries_after_aborted_transaction(self):
        calls = []
        original_query = self.db.query
        query_attempts = 0

        def sender(phone, reply):
            calls.append((phone, reply))
            return {"messages": [{"id": "meta-1"}]}

        def flaky_query(*args, **kwargs):
            nonlocal query_attempts
            if args and args[0] is OutboundDeliveryDB and query_attempts == 0:
                query_attempts += 1
                raise SQLAlchemyError("current transaction is aborted")
            return original_query(*args, **kwargs)

        with patch.object(self.db, "query", side_effect=flaky_query), patch.object(
            self.db, "rollback", wraps=self.db.rollback
        ) as rollback:
            send_reply_once(
                db=self.db,
                idempotency_key="msg-aborted:0",
                phone="5511",
                reply="hello",
                sender=sender,
                reply_text=str,
            )

        self.assertEqual(len(calls), 1)
        rollback.assert_called()
        delivery = original_query(OutboundDeliveryDB).one()
        self.assertEqual(delivery.status, "sent")
        self.assertEqual(delivery.meta_message_id, "meta-1")

    def test_failed_outbound_reply_can_resume(self):
        calls = []

        def sender(phone, reply):
            calls.append((phone, reply))
            if len(calls) == 1:
                raise RuntimeError("temporary")
            return {"messages": [{"id": "meta-2"}]}

        kwargs = {
            "db": self.db,
            "idempotency_key": "msg-4:0",
            "phone": "5511",
            "reply": "hello again",
            "sender": sender,
            "reply_text": str,
        }
        with self.assertRaises(RuntimeError):
            send_reply_once(**kwargs)

        send_reply_once(**kwargs)

        self.assertEqual(len(calls), 2)
        delivery = self.db.query(OutboundDeliveryDB).one()
        self.assertEqual(delivery.status, "sent")
        self.assertEqual(delivery.attempts, 2)
        self.assertEqual(delivery.meta_message_id, "meta-2")


if __name__ == "__main__":
    unittest.main()
