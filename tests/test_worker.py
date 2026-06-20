import os
import unittest
from unittest.mock import AsyncMock, patch

import worker


class WorkerTests(unittest.IsolatedAsyncioTestCase):
    async def test_enabled_worker_owns_the_automation_loop(self):
        loop = AsyncMock()
        with patch.dict(os.environ, {"ACADEMIC_AUTOMATIONS_ENABLED": "true"}), patch.object(
            worker, "academic_automation_loop", loop
        ):
            await worker.run_worker()

        loop.assert_awaited_once_with()

    async def test_disabled_worker_does_not_start_the_loop(self):
        loop = AsyncMock()
        with patch.dict(os.environ, {"ACADEMIC_AUTOMATIONS_ENABLED": "false"}), patch.object(
            worker, "academic_automation_loop", loop
        ):
            await worker.run_worker()

        loop.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
