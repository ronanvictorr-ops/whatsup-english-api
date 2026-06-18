import random
import time
from time import perf_counter

import requests

from wingo.observability import log_event, record_metric


RETRYABLE_HTTP_STATUS = {408, 409, 425, 429, 500, 502, 503, 504}


def _sleep(attempt: int, base_delay: float) -> None:
    delay = base_delay * (2 ** (attempt - 1)) + random.uniform(0, 0.1)
    time.sleep(delay)


def http_post_with_retry(*args, operation: str = "meta_post", attempts: int = 3, **kwargs):
    started = perf_counter()
    response = None
    last_error = None

    for attempt in range(1, attempts + 1):
        try:
            response = requests.post(*args, **kwargs)
            if response.status_code not in RETRYABLE_HTTP_STATUS:
                record_metric("meta", operation, "success", (perf_counter() - started) * 1000, attempt)
                return response
            last_error = RuntimeError(f"HTTP {response.status_code}")
        except requests.RequestException as error:
            last_error = error

        log_event("retry", service="meta", operation=operation, attempt=attempt, error=str(last_error))
        if attempt < attempts:
            _sleep(attempt, 0.25)

    record_metric(
        "meta",
        operation,
        "error",
        (perf_counter() - started) * 1000,
        attempts,
        error_type=type(last_error).__name__ if last_error else "HTTPError",
    )
    if response is not None:
        return response
    raise last_error


def http_get_with_retry(*args, operation: str = "meta_get", attempts: int = 3, **kwargs):
    started = perf_counter()
    response = None
    last_error = None

    for attempt in range(1, attempts + 1):
        try:
            response = requests.get(*args, **kwargs)
            if response.status_code not in RETRYABLE_HTTP_STATUS:
                record_metric("meta", operation, "success", (perf_counter() - started) * 1000, attempt)
                return response
            last_error = RuntimeError(f"HTTP {response.status_code}")
        except requests.RequestException as error:
            last_error = error

        log_event("retry", service="meta", operation=operation, attempt=attempt, error=str(last_error))
        if attempt < attempts:
            _sleep(attempt, 0.25)

    record_metric(
        "meta",
        operation,
        "error",
        (perf_counter() - started) * 1000,
        attempts,
        error_type=type(last_error).__name__ if last_error else "HTTPError",
    )
    if response is not None:
        return response
    raise last_error


def call_with_retry(callable_, *args, operation: str, attempts: int = 3, **kwargs):
    started = perf_counter()
    last_error = None

    for attempt in range(1, attempts + 1):
        try:
            result = callable_(*args, **kwargs)
            usage = getattr(result, "usage", None)
            input_tokens = int(
                getattr(usage, "prompt_tokens", 0)
                or getattr(usage, "input_tokens", 0)
                or 0
            )
            output_tokens = int(
                getattr(usage, "completion_tokens", 0)
                or getattr(usage, "output_tokens", 0)
                or 0
            )
            record_metric(
                "openai",
                operation,
                "success",
                (perf_counter() - started) * 1000,
                attempt,
                input_tokens,
                output_tokens,
            )
            return result
        except Exception as error:
            last_error = error
            status_code = getattr(error, "status_code", None)
            if status_code and status_code < 500 and status_code != 429:
                break
            log_event("retry", service="openai", operation=operation, attempt=attempt, error=str(error))
            if attempt < attempts:
                _sleep(attempt, 0.3)

    record_metric(
        "openai",
        operation,
        "error",
        (perf_counter() - started) * 1000,
        attempts,
        error_type=type(last_error).__name__,
    )
    raise last_error
