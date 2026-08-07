"""Submit a Spark command through the local socket-free driver service."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from urllib.request import Request, urlopen


OpenUrl = Callable[..., object]


def submit_remote(
    *,
    service_url: str,
    timeout_seconds: float,
    spark_args: list[str],
    open_url: OpenUrl = urlopen,
) -> str:
    request = Request(
        service_url,
        data=json.dumps({"spark_args": spark_args}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with open_url(request, timeout=timeout_seconds) as response:
        result = json.loads(response.read().decode("utf-8"))
    stdout = str(result.get("stdout", ""))
    stderr = str(result.get("stderr", ""))
    if stdout:
        sys.stdout.write(stdout)
    if stderr:
        sys.stderr.write(stderr)
    return "FINISHED" if int(result.get("returncode", 1)) == 0 else "FAILED"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--service-url", required=True)
    parser.add_argument("--timeout-seconds", type=float, default=2400)
    args, spark_args = parser.parse_known_args(argv)
    if spark_args[:1] == ["--"]:
        spark_args = spark_args[1:]
    status = submit_remote(
        service_url=args.service_url,
        timeout_seconds=args.timeout_seconds,
        spark_args=spark_args,
    )
    return 0 if status == "FINISHED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
