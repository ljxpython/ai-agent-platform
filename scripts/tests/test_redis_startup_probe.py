"""Exercise the actual shell probe without starting Redis or sleeping."""

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from redis.exceptions import BusyLoadingError, ConnectionError


class RedisStartupProbeTests(unittest.TestCase):
    def probe(self, outcomes, *, failure=False):
        script = (Path(__file__).resolve().parents[1] / "local-stack.sh").read_text()
        program = script.split("check_redis() {", 1)[1].split("<<'PY'\n", 1)[1].split("\nPY", 1)[0]
        client = SimpleNamespace(ping=AsyncMock(side_effect=outcomes), aclose=AsyncMock())
        with (
            patch("redis.asyncio.Redis.from_url", return_value=client),
            patch("dotenv.dotenv_values", return_value={"REDIS_URI": "redis://probe.invalid"}),
            patch.object(sys, "argv", ["probe", "unused.env"]),
            patch("asyncio.sleep", new_callable=AsyncMock) as sleep,
            patch("builtins.print"),
        ):
            if failure:
                with self.assertRaisesRegex(SystemExit, "^Redis is unavailable at REDIS_URI$"):
                    exec(compile(program, "check_redis", "exec"), {})  # noqa: S102 - checked-in probe only
            else:
                exec(compile(program, "check_redis", "exec"), {})  # noqa: S102 - checked-in probe only
        client.aclose.assert_awaited_once()
        return client.ping.await_count, sleep.await_count

    def test_loading_is_retried_until_ready(self):
        self.assertEqual(self.probe([BusyLoadingError(), BusyLoadingError(), True]), (3, 2))

    def test_non_loading_failure_does_not_retry_or_expose_details(self):
        self.assertEqual(self.probe([ConnectionError("private details")], failure=True), (1, 0))

    def test_loading_has_a_finite_wait(self):
        self.assertEqual(self.probe([BusyLoadingError()] * 120, failure=True), (120, 119))


if __name__ == "__main__":
    unittest.main()
