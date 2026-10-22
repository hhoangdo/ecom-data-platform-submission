from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest
from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[3]
REVISION = "b" * 40
UI_NAMES = [
    "grafana_http", "grafana_compute", "grafana_llm", "grafana_agents", "grafana_ab",
    "loki_app_logs", "tempo_trace", "langfuse_trace", "nginx_tls", "chat_auth_rate_limit",
]
JENKINS_NAMES = [
    "jenkins_rag_index", "jenkins_retrieval_agent", "jenkins_drift_agent",
    "jenkins_coordinator", "jenkins_feast_offline", "jenkins_feast_online",
]


def _load_script():
    path = ROOT / "scripts/qa/capture_edai2_evidence.py"
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _png_bytes(seed: int) -> bytes:
    import io

    image = Image.new("RGB", (1600, 1000), (10 + seed, 20, 30))
    ImageDraw.Draw(image).rectangle([0, 0, 100 + seed, 100 + seed], fill=(200, 100, 50))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


class FakePage:
    instances = 0
    shots = 0

    def __init__(self, body: str) -> None:
        type(self).instances += 1
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
        Path(str(kwargs["path"])).write_bytes(_png_bytes(type(self).shots * 7 + len(self.visited)))


def _machine(root: Path, name: str) -> Path:
    path = root / name
    path.write_text(json.dumps({"ok": True}) + "\n", encoding="utf-8")
    return path


def _ui_urls() -> dict[str, str]:
    routes = {
        "grafana_http": "grafana", "grafana_compute": "grafana", "grafana_llm": "grafana",
        "grafana_agents": "grafana", "grafana_ab": "grafana", "loki_app_logs": "grafana",
        "tempo_trace": "grafana", "langfuse_trace": "langfuse", "nginx_tls": "retrieval",
        "chat_auth_rate_limit": "chat",
    }
    return {name: f"https://{routes[name]}.example.test/view/{name}" for name in UI_NAMES}


def _body_for(capture, names: list[str]) -> str:
    words = []
    for name in names:
        filename = name + ".png"
        words.extend(capture.LIVE_VIEW_CHECKS.get(filename, capture.REQUIRED_VIEWS[filename]))
    return " page ".join(words)


def test_telemetry_writer_tolerates_metric_tokens_but_rejects_secrets(tmp_path: Path) -> None:
    """LLM/Langfuse views name token metrics; real secret material must still fail."""
    capture = _load_script()
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        destination = Path(tmp) / "out.png"
        ok_page = FakePage("Grafana title dashboard EDAI2 LLM Input tokens visible")
        capture._tunnel_page_writer(
            "https://grafana.example.test/d/x", ["Grafana title", "Input tokens"],
            lambda: ok_page, capture._TELEMETRY_SECRET,
        )(destination)
        assert destination.is_file()
        bad_page = FakePage("Grafana title api-key ABCDEF visible")
        with pytest.raises(ValueError, match="unsafe"):
            capture._tunnel_page_writer(
                "https://grafana.example.test/d/x", ["Grafana title"],
                lambda: bad_page, capture._TELEMETRY_SECRET,
            )(Path(tmp) / "bad.png")
        token_page = FakePage("Grafana title client_token=abc123 visible")
        with pytest.raises(ValueError, match="unsafe"):
            capture._tunnel_page_writer(
                "https://grafana.example.test/d/x", ["Grafana title"],
                lambda: token_page, capture._TELEMETRY_SECRET,
            )(Path(tmp) / "bad2.png")


def test_capture_ui_set_records_ten_named_views() -> None:
    """Ten contextual captures land with exact machine links, one per name."""
    capture = _load_script()
    import tempfile

    assert set(capture.UI_SETS["gateway-observability"]) == set(UI_NAMES)
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        shots = root / "shots"
        shots.mkdir()
        manifest = shots / "ui_manifest.json"
        telemetry = _machine(root, "telemetry.json")
        rate = _machine(root, "https_rate_limit.json")
        urls = _ui_urls()
        machines = {
            name: [telemetry if name != "chat_auth_rate_limit" else rate] for name in UI_NAMES
        }
        FakePage.instances = 0
        entries = capture.capture_ui_set(
            names=UI_NAMES, urls=urls, machine_files=machines,
            screenshots_dir=shots, manifest_path=manifest, revision=REVISION,
            page_factory=lambda: FakePage(_body_for(capture, UI_NAMES)), workspace=root,
        )
        assert [entry["path"] for entry in entries] == [name + ".png" for name in UI_NAMES]
        manifest_entries = json.loads(manifest.read_text(encoding="utf-8"))
        assert len(manifest_entries) == 10


def test_capture_ui_set_rejects_unknown_or_missing_url() -> None:
    capture = _load_script()
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "shots").mkdir()
        telemetry = _machine(root, "telemetry.json")
        urls = _ui_urls()
        machines = {name: [telemetry] for name in UI_NAMES}
        with pytest.raises(ValueError, match="names"):
            capture.capture_ui_set(
                names=[*UI_NAMES, "grafana_nope"], urls=urls, machine_files=machines,
                screenshots_dir=root / "shots", manifest_path=root / "shots/ui_manifest.json",
                revision=REVISION, page_factory=lambda: FakePage("x"), workspace=root,
            )
        bad = dict(urls)
        bad["grafana_http"] = "http://insecure.example.test/view"
        with pytest.raises(ValueError, match="URL"):
            capture.capture_ui_set(
                names=UI_NAMES, urls=bad, machine_files=machines,
                screenshots_dir=root / "shots", manifest_path=root / "shots/ui_manifest.json",
                revision=REVISION, page_factory=lambda: FakePage("x"), workspace=root,
            )


def test_capture_jenkins_six_pages_uses_one_browser_session() -> None:
    """Six distinct pages come from one authenticated session with zero rebuilds."""
    capture = _load_script()
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        shots = root / "shots"
        shots.mkdir()
        manifest = shots / "ui_manifest.json"
        jobs_src = ROOT / "evidence/04_2_llm_design/cicd/jobs.json"
        jobs = root / "jobs.json"
        jobs.write_bytes(jobs_src.read_bytes())
        urls = {name: f"https://jenkins.example.test/job/{capture.JENKINS_PAGES[name]}/42/" for name in JENKINS_NAMES}
        FakePage.instances = 0
        pages: list[FakePage] = []

        def factory() -> FakePage:
            page = FakePage(_body_for(capture, JENKINS_NAMES))
            pages.append(page)
            return page

        entries = capture.capture_jenkins_six_pages(
            jobs_path=jobs, urls=urls, screenshots_dir=shots, manifest_path=manifest,
            revision=REVISION, page_factory=factory, workspace=root,
        )
        assert len(pages) == 1
        assert sorted(pages[0].visited) == sorted(urls.values())
        assert [entry["path"] for entry in entries] == [name + ".png" for name in JENKINS_NAMES]
        for url in pages[0].visited:
            lowered = url.lower()
            assert "replay" not in lowered and "rebuild" not in lowered and "buildnow" not in lowered


def test_jenkins_six_pages_browser_only_argv_parses_without_kubeconfig() -> None:
    """Browser-only Jenkins capture parses with no kubeconfig/context in argv."""
    capture = _load_script()
    argv = [
        "--capture-jenkins-six-pages", "evidence/04_2_llm_design/cicd/jobs.json",
        "--single-browser-session", "--no-build",
        "--viewport", "1600x1000",
        "--outputs", "a.png,b.png",
        "--manifest", "m.json",
        "--strict",
    ]
    args = capture.parse_args(argv)
    assert args.capture_jenkins_six_pages == "evidence/04_2_llm_design/cicd/jobs.json"
    assert args.single_browser_session is True
    assert args.no_build is True
    assert args.strict is True
    assert args.kubeconfig is None and args.context is None


def test_jenkins_six_pages_argv_accepts_ignored_kubeconfig_and_context() -> None:
    """The same Jenkins path also parses when kubeconfig/context are supplied (ignored)."""
    capture = _load_script()
    argv = [
        "--capture-jenkins-six-pages", "evidence/04_2_llm_design/cicd/jobs.json",
        "--single-browser-session", "--no-build",
        "--viewport", "1600x1000",
        "--outputs", "a.png,b.png",
        "--manifest", "m.json",
        "--strict",
        "--kubeconfig", "kube.yaml",
        "--context", "edai2-gke",
    ]
    args = capture.parse_args(argv)
    assert args.kubeconfig == "kube.yaml" and args.context == "edai2-gke"


def test_capture_jenkins_six_pages_rejects_unknown_job() -> None:
    capture = _load_script()
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "shots").mkdir()
        jobs_src = ROOT / "evidence/04_2_llm_design/cicd/jobs.json"
        jobs = root / "jobs.json"
        jobs.write_bytes(jobs_src.read_bytes())
        urls = {name: f"https://jenkins.example.test/job/{capture.JENKINS_PAGES[name]}/42/" for name in JENKINS_NAMES}
        urls["jenkins_rag_index"] = "https://jenkins.example.test/job/unknown/1/"
        with pytest.raises(ValueError, match="job"):
            capture.capture_jenkins_six_pages(
                jobs_path=jobs, urls=urls, screenshots_dir=root / "shots",
                manifest_path=root / "shots/ui_manifest.json", revision=REVISION,
                page_factory=lambda: FakePage("x"), workspace=root,
            )
