"""Run local PySpark drivers from a socket-free Compose service."""

from __future__ import annotations

import argparse
import json
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


_DRIVER_CONFIG_KEYS = {
    "spark.driver.host",
    "spark.driver.bindAddress",
    "spark.driver.port",
    "spark.blockManager.port",
}


def _application_index(spark_args: list[str]) -> int:
    options_with_values = {
        "--class",
        "--conf",
        "--deploy-mode",
        "--driver-class-path",
        "--driver-memory",
        "--files",
        "--jars",
        "--master",
        "--name",
        "--packages",
        "--py-files",
        "--repositories",
        "--total-executor-cores",
    }
    index = 0
    while index < len(spark_args):
        token = spark_args[index]
        if token == "--":
            return index + 1
        if token in options_with_values:
            index += 2
            continue
        if token.startswith("--"):
            index += 1
            continue
        return index
    return len(spark_args)


def _without_driver_configs(spark_args: list[str]) -> list[str]:
    result: list[str] = []
    index = 0
    while index < len(spark_args):
        if (
            spark_args[index] == "--conf"
            and index + 1 < len(spark_args)
            and spark_args[index + 1].split("=", 1)[0] in _DRIVER_CONFIG_KEYS
        ):
            index += 2
            continue
        result.extend(spark_args[index : index + 1])
        index += 1
    return result


def build_driver_command(*, spark_submit_bin: str, spark_args: list[str]) -> list[str]:
    args = _without_driver_configs(list(spark_args))
    if "--deploy-mode" in args:
        deploy_mode = args[args.index("--deploy-mode") + 1]
        if deploy_mode != "client":
            raise ValueError("The driver service only accepts Spark client deploy mode.")
    else:
        insert_at = _application_index(args)
        args[insert_at:insert_at] = ["--deploy-mode", "client"]
    insert_at = _application_index(args)
    args[insert_at:insert_at] = [
        "--conf",
        "spark.driver.host=spark-driver",
        "--conf",
        "spark.driver.bindAddress=0.0.0.0",
        "--conf",
        "spark.driver.port=39000",
        "--conf",
        "spark.blockManager.port=39001",
    ]
    return [spark_submit_bin, *args]


def run_spark_submit(*, spark_submit_bin: str, spark_args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        build_driver_command(spark_submit_bin=spark_submit_bin, spark_args=spark_args),
        check=False,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )


class _DriverHandler(BaseHTTPRequestHandler):
    server: "_DriverServer"

    def _write_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            self._write_json(200, {"status": "ok"})
            return
        self._write_json(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/run":
            self._write_json(404, {"error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            spark_args = payload.get("spark_args")
            if not isinstance(spark_args, list) or not all(isinstance(item, str) for item in spark_args):
                raise ValueError("spark_args must be a list of strings")
            with self.server.run_lock:
                result = run_spark_submit(spark_submit_bin=self.server.spark_submit_bin, spark_args=spark_args)
            self._write_json(
                200,
                {"returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr},
            )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            self._write_json(400, {"error": str(exc)})

    def log_message(self, _format: str, *_args: object) -> None:
        return


class _DriverServer(ThreadingHTTPServer):
    allow_reuse_address = True

    def __init__(self, address: tuple[str, int], spark_submit_bin: str):
        super().__init__(address, _DriverHandler)
        import threading

        self.spark_submit_bin = spark_submit_bin
        self.run_lock = threading.Lock()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8090)
    parser.add_argument("--spark-submit-bin", default="/opt/spark/bin/spark-submit")
    args = parser.parse_args(argv)
    server = _DriverServer((args.host, args.port), args.spark_submit_bin)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
