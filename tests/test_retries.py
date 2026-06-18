import unittest
from types import SimpleNamespace
from unittest.mock import patch

import requests

from wingo.retries import call_with_retry, http_post_with_retry


class RetryTests(unittest.TestCase):
    @patch("wingo.retries.record_metric")
    @patch("wingo.retries._sleep")
    @patch("wingo.retries.requests.post")
    def test_meta_retries_retryable_status(self, post, sleep, metric):
        post.side_effect = [
            SimpleNamespace(status_code=503),
            SimpleNamespace(status_code=200),
        ]
        response = http_post_with_retry("https://example.test", attempts=3)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(post.call_count, 2)
        self.assertEqual(sleep.call_count, 1)

    @patch("wingo.retries.record_metric")
    @patch("wingo.retries._sleep")
    def test_openai_retries_transient_failure(self, sleep, metric):
        calls = []

        def operation():
            calls.append(True)
            if len(calls) == 1:
                raise RuntimeError("temporary")
            return SimpleNamespace(usage=None)

        result = call_with_retry(operation, operation="test", attempts=3)
        self.assertIsNotNone(result)
        self.assertEqual(len(calls), 2)

    @patch("wingo.retries.record_metric")
    @patch("wingo.retries._sleep")
    @patch("wingo.retries.requests.post")
    def test_meta_network_failure_is_raised_after_limit(self, post, sleep, metric):
        post.side_effect = requests.ConnectionError("offline")
        with self.assertRaises(requests.ConnectionError):
            http_post_with_retry("https://example.test", attempts=2)
        self.assertEqual(post.call_count, 2)


if __name__ == "__main__":
    unittest.main()
