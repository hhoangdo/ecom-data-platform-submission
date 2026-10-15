"""Local regressions for the suspended Topic 24 remote builder handoff."""

from __future__ import annotations

from pathlib import Path

from scripts.gke import topic24_remote_build as builder

ROOT = Path(__file__).resolve().parents[2]
BUILDER_SCRIPT = ROOT / "scripts/gke/topic24_remote_build.py"


def test_builder_waits_for_touch_created_sentinel_files_and_propagates_pipeline_failure():
    command = builder.job_manifest("a" * 64)["spec"]["template"]["spec"]["containers"][0]["args"][0]

    assert "set -euo pipefail" in command
    assert "GOPATH=/workspace/gopath GOENV=off" in command
    assert "until [ -f /workspace/READY ]; do sleep 2; done" in command
    assert "until [ -f /workspace/COLLECTED ]; do sleep 2; done" in command
    assert "ko build --bare" in command and "| tee /workspace/ko-build.log" in command
    assert command.index("ko build --bare") < command.index("touch /workspace/BUILD_SUCCEEDED")
    assert "unset GOOS GOARCH\nko build --bare --platform=linux/amd64" in command


def test_operator_copy_sources_are_repository_relative_on_windows():
    steps = builder.operator_steps("a" * 64, "topic24-aaaaaaaaaaaaaaaa")
    lines = [line.strip() for line in steps.splitlines() if "kubectl " in line and " cp " in line]

    assert len(lines) == 7
    assert "Run these relative-path copy commands from the repository root." in steps
    assert all("C:/" not in line and "C:\\" not in line for line in lines)
    assert any("tmp/edai2-gcp/topic24-finalize/substrate-source-topic24-finalize.tar.gz " in line for line in lines)
    assert any("tmp/edai2-gcp/topic24-finalize/substrate-source-topic24-finalize.tar.gz.sha256 " in line for line in lines)


def test_remote_build_script_does_not_repurpose_home():
    script = BUILDER_SCRIPT.read_text(encoding="utf-8")
    assert "HOME=" not in script
    assert "export TMPDIR=/workspace/tmp" in script
