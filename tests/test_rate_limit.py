import unittest
from unittest.mock import patch

from fastapi import HTTPException

from wingo.rate_limit import SlidingWindowRateLimiter, enforce_rate_limit, limiter


class MutableClock:
    def __init__(self):
        self.value = 0.0

    def __call__(self):
        return self.value


class RateLimitTests(unittest.TestCase):
    def setUp(self):
        self.clock = MutableClock()
        self.subject = SlidingWindowRateLimiter(clock=self.clock)
        limiter.reset()

    def tearDown(self):
        limiter.reset()

    def test_allows_requests_up_to_limit(self):
        self.subject.check("login", "client-a", limit=2, window_seconds=60)
        self.subject.check("login", "client-a", limit=2, window_seconds=60)

    def test_rejects_excess_request_with_retry_after(self):
        self.subject.check("login", "client-a", limit=1, window_seconds=60)

        with self.assertRaises(HTTPException) as failure:
            self.subject.check("login", "client-a", limit=1, window_seconds=60)

        self.assertEqual(failure.exception.status_code, 429)
        self.assertEqual(failure.exception.headers["Retry-After"], "60")

    def test_separates_clients_and_scopes(self):
        self.subject.check("login", "client-a", limit=1, window_seconds=60)
        self.subject.check("login", "client-b", limit=1, window_seconds=60)
        self.subject.check("register", "client-a", limit=1, window_seconds=60)

    def test_request_is_allowed_after_window_expires(self):
        self.subject.check("chat", "student-1", limit=1, window_seconds=60)
        self.clock.value = 60.1
        self.subject.check("chat", "student-1", limit=1, window_seconds=60)

    def test_environment_can_disable_rate_limiting(self):
        with patch.dict("os.environ", {"RATE_LIMIT_ENABLED": "false"}):
            enforce_rate_limit("login", "client-a", 1, 60)
            enforce_rate_limit("login", "client-a", 1, 60)


if __name__ == "__main__":
    unittest.main()
