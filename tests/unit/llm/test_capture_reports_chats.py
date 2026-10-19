from __future__ import annotations

import importlib.util
import io
import json
from pathlib import Path

import pytest
from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[3]
REVISION = "d" * 40


def _load_script():
    path = ROOT / "scripts/qa/capture_edai2_evidence.py"
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _png_bytes(seed: int) -> bytes:
    image = Image.new("RGB", (1600, 1000), (10 + seed, 20, 30))
    ImageDraw.Draw(image).rectangle([0, 0, 100 + seed, 100 + seed], fill=(200, 100, 50))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


class FakePage:
    shots = 0

    def __init__(self, body: str) -> None:
        self.body = body
        self.visited: list[str] = []

    def goto(self, url: str, **_kwargs: object) -> None:
        self.visited.append(url)

    def locator(self, _selector: str):
        body = self.body

        class Locator:
            def inner_text(self, timeout: int = 0) -> str:
                del timeout
                return body

        return Locator()

    def screenshot(self, **kwargs: object) -> None:
        type(self).shots += 1
        Path(str(kwargs["path"])).write_bytes(_png_bytes(type(self).shots * 13))


def _machine(root: Path, name: str, payload: dict) -> Path:
    path = root / name
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    return path


def test_capture_report_view_renders_and_links_machine_evidence() -> None:
    """Executed-result captures come from rendered reports, never blank pages."""
    capture = _load_script()
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        shots = root / "shots"
        shots.mkdir()
        coverage = _machine(root, "coverage.json", {"percent": 95.0, "files": ["a.py"]})
        body = " ".join(capture.REQUIRED_VIEWS["coverage_and_api_fixtures.png"])
        entry = capture.capture_report_view(
            name="coverage_and_api_fixtures", html_title="Coverage report",
            rows=[("total", "95.0%"), ("files", "a.py")],
            machine_files=[coverage], screenshots_dir=shots,
            manifest_path=shots / "ui_manifest.json", revision=REVISION,
            page_factory=lambda: FakePage(body), workspace=root,
        )
        assert entry["path"] == "coverage_and_api_fixtures.png"


def test_capture_report_view_rejects_blank_render() -> None:
    capture = _load_script()
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        shots = root / "shots"
        shots.mkdir()
        coverage = _machine(root, "coverage.json", {"percent": 95.0})
        with pytest.raises(ValueError, match="selectors"):
            capture.capture_report_view(
                name="coverage_and_api_fixtures", html_title="Coverage report",
                rows=[("total", "95.0%")], machine_files=[coverage],
                screenshots_dir=shots, manifest_path=shots / "ui_manifest.json",
                revision=REVISION, page_factory=lambda: FakePage("empty void"),
                workspace=root,
            )


def test_capture_agent_chats_records_three_transcripts() -> None:
    """Each chat shows agent/version, request, routing result, and grounded output."""
    capture = _load_script()
    import tempfile

    posts: list[dict] = []

    def chat_post(agent: str, prompt: str) -> dict:
        posts.append({"agent": agent, "prompt": prompt})
        return {
            "agent": agent, "version": "v1-primary", "request": prompt,
            "route": "specialist", "tool": "retrieval.search",
            "answer": "Grounded answer with citation.", "citations": ["doc#1"],
        }

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        shots = root / "shots"
        shots.mkdir()
        registry = _machine(root, "registry.json", {"agents": ["retrieval"]})
        https = _machine(root, "https_rate_limit.json", {"accepted": 5})
        notebooks = {}
        for agent in ("retrieval", "drift", "coordinator"):
            path = root / f"{agent}.ipynb"
            path.write_text(json.dumps({"cells": [], "metadata": {}}), encoding="utf-8")
            notebooks[agent] = path
        bodies_union = " page ".join(
            selector
            for agent in ("retrieval", "drift", "coordinator")
            for selector in capture.REQUIRED_VIEWS[f"kagent_{agent}_chat.png"]
        )
        urls = {agent: f"https://chat.example.test/agent/{agent}" for agent in ("retrieval", "drift", "coordinator")}
        entries = capture.capture_agent_chats(
            agents=["retrieval", "drift", "coordinator"], urls=urls, chat_post=chat_post,
            registry_path=registry, notebooks=notebooks, https_evidence=https,
            chat_evidence_path=root / "agent_chats.json",
            screenshots_dir=shots, manifest_path=shots / "ui_manifest.json",
            revision=REVISION, page_factory=lambda: FakePage(bodies_union), workspace=root,
        )
        assert [entry["path"] for entry in entries] == [
            "kagent_retrieval_chat.png", "kagent_drift_chat.png", "kagent_coordinator_chat.png",
        ]
        assert len(posts) == 3
        assert len(json.loads((root / "agent_chats.json").read_text(encoding="utf-8"))) == 3
