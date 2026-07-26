from __future__ import annotations

import hashlib
import re
from collections import defaultdict, deque
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
PACKAGE = ROOT / "tmp" / "edai2-plan" / "execution-v1"
MASTER = PACKAGE / "00-master-session-prompts.md"

EXPECTED = [
    "local/00-workstation-toolchain-context-safety.md",
    "local/01-section03-config-drift-sampler.md",
    "local/02-section03-labels-psi-candidate-evidence.md",
    "local/03-section03-dbt-gold-contracts.md",
    "local/04-section03-spark-gold-parity.md",
    "local/05-section03-airflow-datahub-governance.md",
    "local/06-section03-docs-schema-finalizer.md",
    "local/07-section03-canonical-runtime-promotion.md",
    "local/08-edai2-prerequisite-contracts.md",
    "local/09-rag-source-chunking-embeddings.md",
    "local/10-rag-index-feast-airflow-datahub.md",
    "local/11-retrieval-api-mcp-safety.md",
    "local/12-section03-loader-drift-api-mcp.md",
    "local/13-coordinator-inference-routing-telemetry.md",
    "local/14-agent-security-registry-notebooks.md",
    "local/15-evaluation-test-quality-load.md",
    "local/16-images-jenkins-ci.md",
    "local/17-terraform-vault-iac-static.md",
    "local/18-platform-helm-kustomize.md",
    "local/19-workload-charts-streaming-keda-experiments.md",
    "local/20-observability-ingress-screenshot-contracts.md",
    "local/21-kind-lean-preflight.md",
    "gcp/22-gcp-account-budget-terraform-apply.md",
    "gcp/23-vault-kms-model-cache-bootstrap.md",
    "gcp/24-compact-platform-install.md",
    "gcp/25-jenkins-six-workload-deploy.md",
    "gcp/26-keda-agent-ha-registry-rollbacks.md",
    "gcp/27-observability-https-jenkins-evidence.md",
    "gcp/28-rag-inference-benchmarks.md",
    "gcp/29-evaluation-ab-notebooks-load-test-evidence.md",
    "gcp/30-persistence-vault-recovery-resume.md",
    "gcp/31-final-screenshot-qa-teardown.md",
    "final/32-documentation-rubric-finalization.md",
]

DEPS = {
    0: [], 1: [0], 2: [1], 3: [2], 4: [3], 5: [4], 6: [5], 7: [6],
    8: [7], 9: [8], 10: [9], 11: [10], 12: [8], 13: [11, 12],
    14: [13], 15: [14], 16: [15], 17: [16], 18: [17], 19: [18],
    20: [19], 21: [20], 22: [21], 23: [22], 24: [23], 25: [24],
    26: [25], 27: [26], 28: [27], 29: [28], 30: [29], 31: [30],
    32: [31],
}

HASHES = {
    ROOT / "tmp" / "edai2-plan" / "03_data_generator_improvement.md":
        "ece171c3d400c3b16fc668cd28e3587faebe1f596dd6c0c4498ff055e3fc027f",
    ROOT / "tmp" / "edai2-plan" / "04.2_llm_design.md":
        "b8be3ef5c84fe4d6fe52e8894c3c5dc1c3babc898e2a87684b2b8ff720d6d079",
    ROOT / "tmp" / "rubic-check" / "Coursework Tracking (Public).xlsx":
        "71b2403e068081b00245bea5e15c5754f3762ad354e0a3a6576d69e4963c8657",
}

SCREENSHOTS = [
    "airflow_rag_graph.png", "datahub_rag_lineage.png",
    "kagent_retrieval_chat.png", "kagent_drift_chat.png",
    "kagent_coordinator_chat.png", "agentregistry_agents.png",
    "keda_scale.png", "grafana_http.png", "grafana_compute.png",
    "grafana_llm.png", "grafana_agents.png", "grafana_ab.png",
    "loki_app_logs.png", "tempo_trace.png", "langfuse_trace.png",
    "vault_status.png", "nginx_tls.png", "chat_auth_rate_limit.png",
    "coverage_and_api_fixtures.png", "ep_bva.png", "mutation.png",
    "properties_crosshair.png", "terraform_apply.png",
    "design_patterns.png", "whole_course_diagram.png", "locust_report.png",
    "jenkins_rag_index.png", "jenkins_retrieval_agent.png",
    "jenkins_drift_agent.png", "jenkins_coordinator.png",
    "jenkins_feast_offline.png", "jenkins_feast_online.png",
    "gcp_billing_spend.png",
]

SCREENSHOT_OWNERS = {
    22: ["gcp_billing_spend.png", "terraform_apply.png"],
    26: ["agentregistry_agents.png", "keda_scale.png"],
    27: [
        "grafana_http.png", "grafana_compute.png", "grafana_llm.png",
        "grafana_agents.png", "grafana_ab.png", "loki_app_logs.png",
        "tempo_trace.png", "langfuse_trace.png", "nginx_tls.png",
        "chat_auth_rate_limit.png", "jenkins_rag_index.png",
        "jenkins_retrieval_agent.png", "jenkins_drift_agent.png",
        "jenkins_coordinator.png", "jenkins_feast_offline.png",
        "jenkins_feast_online.png",
    ],
    28: ["airflow_rag_graph.png", "datahub_rag_lineage.png"],
    29: [
        "kagent_retrieval_chat.png", "kagent_drift_chat.png",
        "kagent_coordinator_chat.png", "coverage_and_api_fixtures.png",
        "ep_bva.png", "mutation.png", "properties_crosshair.png",
        "locust_report.png",
    ],
    30: ["vault_status.png"],
    32: ["design_patterns.png", "whole_course_diagram.png"],
}

REQUIRED_CONCEPTS = {
    "goal": r"(?im)(?:^##+\s+.*goal|^\*\*Goal:\*\*)",
    "architecture": r"(?im)(?:^##+\s+.*architecture|^\*\*Architecture(?:/technology)?:\*\*)",
    "tech stack": r"(?im)(?:^##+\s+.*tech(?:nology)?(?: stack)?|^\*\*Tech Stack:\*\*)",
    "metadata": r"(?im)^##+\s+.*metadata",
    "constraints": r"(?im)^##+\s+.*constraints",
    "current state": r"(?im)^##+\s+.*(?:current[- ]state|planning refresh|read-only refresh)",
    "scope": r"(?im)^##+\s+.*scope",
    "file map": r"(?im)^##+\s+.*file map",
    "interfaces": r"(?im)^##+\s+.*interfaces",
    "failure modes": r"(?im)^##+\s+.*failure modes",
    "ordered tasks": r"(?im)^##+\s+.*(?:ordered.*(?:task|execution)|execution tasks|test-first execution)",
    "expected outcomes": r"(?im)expected(?:\s+(?:outcome|result|exit|PASS|FAIL)|:)",
    "evidence": r"(?im)^##+\s+.*evidence",
    "cleanup": r"(?im)^##+\s+.*cleanup",
    "rubric": r"(?im)^##+\s+.*rubric",
    "definition of done": r"(?im)^##+\s+.*definition of done",
    "completion record": r"(?im)^##+\s+completion record",
    "exit codes": r"(?im)exit[- ]code",
    "sha256": r"(?i)sha-?256",
    "successor handoff": r"(?im)\bhandoff\b",
}

FORBIDDEN_POSITIVE_GIT = [
    r"\bgit\s+checkout\s+-b\b",
    r"\bgit\s+switch\s+-c\b",
    r"\bgit\s+worktree\s+add\b",
    r"\bgit\s+add\s+[-./\w]",
    r"\bgit\s+commit(?:\s|$)",
    r"\bgit\s+push(?:\s|$)",
]

FORBIDDEN_LOCAL_LIVE_GCP = [
    r"(?im)^\s*(?:[-*]\s*)?`?rtk\s+gcloud\s+container\s+clusters\s+(?:create|delete|resize)",
    r"(?im)^\s*(?:[-*]\s*)?`?rtk\s+gcloud\s+projects\s+(?:create|delete)",
    r"(?im)^\s*(?:[-*]\s*)?`?rtk\s+terraform\s+(?:apply|destroy)",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_graph() -> list[str]:
    errors: list[str] = []
    indegree = {node: 0 for node in DEPS}
    successors: dict[int, list[int]] = defaultdict(list)
    for node, predecessors in DEPS.items():
        for predecessor in predecessors:
            if predecessor not in DEPS:
                errors.append(f"dependency {predecessor} for {node} is unknown")
                continue
            indegree[node] += 1
            successors[predecessor].append(node)
    queue = deque(node for node, degree in indegree.items() if degree == 0)
    visited: list[int] = []
    while queue:
        node = queue.popleft()
        visited.append(node)
        for successor in successors[node]:
            indegree[successor] -= 1
            if indegree[successor] == 0:
                queue.append(successor)
    if len(visited) != len(DEPS):
        errors.append("dependency graph contains a cycle")
    return errors


errors: list[str] = []

for path, expected in HASHES.items():
    actual = sha256(path)
    if actual != expected:
        errors.append(f"source hash changed: {path} expected {expected} actual {actual}")

actual_subplans = sorted(
    str(path.relative_to(PACKAGE)).replace("\\", "/")
    for path in PACKAGE.rglob("*.md")
    if path != MASTER
)
if actual_subplans != sorted(EXPECTED):
    missing = sorted(set(EXPECTED) - set(actual_subplans))
    extra = sorted(set(actual_subplans) - set(EXPECTED))
    errors.append(f"sub-plan inventory mismatch; missing={missing}; extra={extra}")

if not MASTER.exists():
    errors.append("master file missing")
else:
    master_text = MASTER.read_text(encoding="utf-8")
    planning_count = len(re.findall(r"(?m)^### Topic \d{2} planning prompt$", master_text))
    execution_count = len(re.findall(r"(?m)^### Topic \d{2} execution prompt$", master_text))
    if planning_count != 33 or execution_count != 33:
        errors.append(f"prompt counts are planning={planning_count}, execution={execution_count}")
    owner_rows = re.findall(
        r"(?m)^\| `Sheet3!E(\d+)` \| (\d+) \| (\d{2}) \|",
        master_text,
    )
    owner_cells = [int(cell) for cell, _, _ in owner_rows]
    if sorted(owner_cells) != list(range(3, 63)):
        errors.append("primary ownership table does not cover E3:E62 exactly once")
    if "E49 retains workbook value 1, earns 0" not in master_text:
        errors.append("master does not preserve the E49 zero-earned rule")
    for pin in [
        "Kubernetes.kind",
        "0.32.0",
        "kindest/node:v1.35.5@sha256:ce977ae6d65918d0b58a5f8b5e940429c2ce42fa3a5619ec2bbc60b949c0ac95",
        "Helm.Helm",
        "3.20.0",
        "Hashicorp.Terraform",
        "1.15.8",
        "Google.CloudSDK",
        "577.0.0",
    ]:
        if pin not in master_text:
            errors.append(f"master missing pinned tool value: {pin}")
    for screenshot in SCREENSHOTS:
        if screenshot not in master_text:
            errors.append(f"master missing screenshot owner for {screenshot}")
    for topic in range(33):
        if len(re.findall(
            rf"(?m)^### Topic {topic:02d} planning prompt$", master_text
        )) != 1:
            errors.append(f"master planning prompt for Topic {topic:02d} is not unique")
        if len(re.findall(
            rf"(?m)^### Topic {topic:02d} execution prompt$", master_text
        )) != 1:
            errors.append(f"master execution prompt for Topic {topic:02d} is not unique")
        if EXPECTED[topic] not in master_text:
            errors.append(
                f"master does not reference exact topic path {EXPECTED[topic]}"
            )
    if "section03_config_and_training_join.png" not in master_text:
        errors.append("master missing Section 03 screenshot ownership")
    source_rows = re.findall(
        r"(?m)^\| (Section 03|EDAI2) \| (\d+) \| ([0-9 +]+) \|",
        master_text,
    )
    section03_tasks = sorted(
        int(task) for source, task, _ in source_rows if source == "Section 03"
    )
    edai2_tasks = sorted(
        int(task) for source, task, _ in source_rows if source == "EDAI2"
    )
    if section03_tasks != list(range(1, 11)):
        errors.append("source ownership does not cover Section 03 Tasks 1-10 exactly")
    if edai2_tasks != list(range(0, 14)):
        errors.append("source ownership does not cover EDAI2 Tasks 0-13 exactly")
    for pattern in FORBIDDEN_POSITIVE_GIT:
        if re.search(pattern, master_text, flags=re.IGNORECASE):
            errors.append(f"master contains forbidden positive git command: {pattern}")

for relative in EXPECTED:
    path = PACKAGE / relative
    if not path.exists():
        continue
    text = path.read_text(encoding="utf-8")
    if not text.startswith("# "):
        errors.append(f"{relative}: missing H1 title")
    if "> **For agentic workers:** REQUIRED SUB-SKILL:" not in text:
        errors.append(f"{relative}: missing agentic-worker execution header")
    if "- [ ]" not in text:
        errors.append(f"{relative}: ordered execution steps are not checkboxes")
    if len(text.splitlines()) < 95:
        errors.append(f"{relative}: too short for a detailed self-contained plan")
    for concept, pattern in REQUIRED_CONCEPTS.items():
        if not re.search(pattern, text):
            errors.append(f"{relative}: missing {concept}")
    if re.search(r"(?i)\b(?:TBD|TODO|FIXME)\b|implement later|fill this in", text):
        errors.append(f"{relative}: contains a placeholder marker")
    if re.search(r"<[A-Za-z][^>\r\n]{0,100}>", text):
        errors.append(f"{relative}: contains an angle-bracket placeholder")
    if re.search(
        r"(?:[/\\.]|Jenkinsfile)\{[A-Za-z0-9_./-]+(?:,[A-Za-z0-9_./-]+)+\}",
        text,
    ):
        errors.append(f"{relative}: contains brace-compressed paths or arguments")
    if len(re.findall(r"(?im)^##+\s+Completion Record\s*$", text)) != 1:
        errors.append(f"{relative}: must contain exactly one Completion Record")
    ordered_match = re.search(
        r"(?ims)^##+\s+Ordered[^\r\n]*\r?\n(.*?)(?=^##+\s+)",
        text,
    )
    ordered_text = ordered_match.group(1) if ordered_match else ""
    ordered_offset = ordered_match.start(1) if ordered_match else 0
    task_matches = list(re.finditer(r"(?m)^\s*-\s+\[\s\]\s+", ordered_text))
    for index, match in enumerate(task_matches):
        end = (
            task_matches[index + 1].start()
            if index + 1 < len(task_matches)
            else len(ordered_text)
        )
        block = ordered_text[match.start():end]
        absolute_start = ordered_offset + match.start()
        line_number = text.count("\n", 0, absolute_start) + 1
        if "expected" not in block.lower():
            errors.append(
                f"{relative}:{line_number}: checkbox block lacks an expected result"
            )
        accepted_manual_actions = [
            "view_image",
            "image viewer",
            "operator authorization",
        ]
        if "rtk " not in block and not any(
            action in block.lower() for action in accepted_manual_actions
        ):
            errors.append(
                f"{relative}:{line_number}: checkbox block lacks a literal rtk/manual action"
            )
    if "C:\\Users\\oou1hc\\.codex\\RTK.md" not in text:
        errors.append(f"{relative}: missing RTK instruction reference")
    if "rtk git status --short --branch" not in text:
        errors.append(f"{relative}: missing initial/final git status command")
    if "Sheet3!E" not in text:
        errors.append(f"{relative}: missing Sheet3 cell reference")
    bare_cells = sorted(set(re.findall(
        r"(?<!Sheet3!)(?<!:)\bE(?:[3-9]|[1-5]\d|6[0-2])\b",
        text,
    )))
    if bare_cells:
        errors.append(
            f"{relative}: contains unqualified rubric cells {bare_cells}"
        )
    if "tmp/rubic-check/Coursework Tracking (Public).xlsx" not in text:
        errors.append(f"{relative}: missing exact rubric workbook path")
    if relative in {
        "local/00-workstation-toolchain-context-safety.md",
        "local/21-kind-lean-preflight.md",
    } and "kindest/node:v1.35.5@sha256:ce977ae6d65918d0b58a5f8b5e940429c2ce42fa3a5619ec2bbc60b949c0ac95" not in text:
        errors.append(f"{relative}: missing approved Kind node image digest")
    if relative in {
        "local/00-workstation-toolchain-context-safety.md",
        "local/21-kind-lean-preflight.md",
    }:
        for kind_value in [
            "tmp/edai2-kind/kubeconfig",
            "edai2-lean",
            "kind-edai2-lean",
        ]:
            if kind_value not in text:
                errors.append(f"{relative}: missing Kind convention {kind_value}")
    if "397bcc4ab091b9632fb3639d5cf020943ca40e90fe7bcc38409738a4a0d056ee" in text:
        errors.append(f"{relative}: contains unapproved Kind node digest")
    for pattern in FORBIDDEN_POSITIVE_GIT:
        if re.search(pattern, text, flags=re.IGNORECASE):
            errors.append(f"{relative}: contains forbidden positive git command: {pattern}")
    if relative.startswith("local/"):
        for pattern in FORBIDDEN_LOCAL_LIVE_GCP:
            if re.search(pattern, text):
                errors.append(f"{relative}: contains a live GCP mutation command")
    if relative.startswith("gcp/"):
        if "EDAI2_GKE_KUBECONFIG" not in text or "EDAI2_GKE_CONTEXT" not in text:
            errors.append(f"{relative}: missing dedicated GKE kubeconfig/context variables")
        if "config use-context" in text:
            errors.append(f"{relative}: attempts to switch the default Kubernetes context")
        for line_number, line in enumerate(text.splitlines(), start=1):
            if "rtk kubectl" in line and (
                "--kubeconfig" not in line or "--context" not in line
            ):
                errors.append(
                    f"{relative}:{line_number}: kubectl lacks explicit kubeconfig/context"
                )
            if "rtk helm" in line and (
                "--kubeconfig" not in line or "--kube-context" not in line
            ):
                errors.append(
                    f"{relative}:{line_number}: Helm lacks explicit kubeconfig/context"
                )
    if relative == "local/21-kind-lean-preflight.md":
        for line_number, line in enumerate(text.splitlines(), start=1):
            if "rtk kubectl" in line and (
                "--kubeconfig tmp/edai2-kind/kubeconfig" not in line
                or "--context kind-edai2-lean" not in line
            ):
                errors.append(
                    f"{relative}:{line_number}: kubectl lacks approved Kind kubeconfig/context"
                )
            if "rtk helm" in line and (
                "--kubeconfig tmp/edai2-kind/kubeconfig" not in line
                or "--kube-context kind-edai2-lean" not in line
            ):
                errors.append(
                    f"{relative}:{line_number}: Helm lacks approved Kind kubeconfig/context"
                )

    topic_number = int(Path(relative).name[:2])
    for screenshot in SCREENSHOT_OWNERS.get(topic_number, []):
        if screenshot not in text:
            errors.append(
                f"{relative}: missing owned screenshot contract for {screenshot}"
            )

topic_00 = (PACKAGE / EXPECTED[0]).read_text(encoding="utf-8")
for exact in ["kubectl", "1.34.1", "edai2-lean", "kind-edai2-lean"]:
    if exact not in topic_00:
        errors.append(f"{EXPECTED[0]}: missing workstation contract {exact}")

topic_07 = (PACKAGE / EXPECTED[7]).read_text(encoding="utf-8")
for exact in [
    "section03_config_and_training_join.png",
    "1600×900",
    "--candidate-manifest",
    "--active-manifest",
    "--spark-root",
    "--airflow-root",
    "--datahub-root",
    "same-ID content mismatch",
    "rtk git diff --check",
]:
    if exact not in topic_07:
        errors.append(f"{EXPECTED[7]}: missing canonical contract {exact}")

topic_08 = (PACKAGE / EXPECTED[8]).read_text(encoding="utf-8")
for exact in [
    "rtk uv add fastapi pydantic mcp feast psycopg pgvector sentence-transformers httpx prometheus-client opentelemetry-sdk opentelemetry-instrumentation-fastapi langfuse",
    "rtk uv add --dev pytest-asyncio pytest-cov hypothesis crosshair-tool mutmut locust playwright nbconvert",
    "test_contracts.py",
    "test_api_contracts.py",
    "test_mcp_contracts.py",
]:
    if exact not in topic_08:
        errors.append(f"{EXPECTED[8]}: missing Task 1 contract {exact}")

topic_09 = (PACKAGE / EXPECTED[9]).read_text(encoding="utf-8")
for exact in [
    "400",
    "80",
    "BAAI/bge-small-en-v1.5",
    "5c38ec7c405ec4b44b94cc5a9bb96e735b38267a",
    "384",
    "test_indexing.py",
]:
    if exact not in topic_09:
        errors.append(f"{EXPECTED[9]}: missing RAG source contract {exact}")

topic_10 = (PACKAGE / EXPECTED[10]).read_text(encoding="utf-8")
for exact in [
    "<=>",
    "test_feast_pgvector.py",
    "test_airflow_datahub.py",
    "--mode candidate",
    "--index-version test_idx_001",
    "--dry-run",
    "bootstrap",
    "canonical",
]:
    if exact not in topic_10:
        errors.append(f"{EXPECTED[10]}: missing RAG index contract {exact}")

topic_21 = (PACKAGE / EXPECTED[21]).read_text(encoding="utf-8")
for exact in [
    "<=6 CPU/16GiB",
    "<=10 CPU/22GiB",
    "<=30 pods",
    "<=8 PVC",
    "zero LoadBalancer",
]:
    if exact not in topic_21:
        errors.append(f"{EXPECTED[21]}: missing lean Kind limit {exact}")

for topic in range(28, 32):
    evidence_text = (PACKAGE / EXPECTED[topic]).read_text(encoding="utf-8")
    if "lease" not in evidence_text.lower() or "budget" not in evidence_text.lower():
        errors.append(f"{EXPECTED[topic]}: missing independent lease/budget gate")

errors.extend(validate_graph())

if errors:
    print("VALIDATION FAILED")
    for error in errors:
        print(f"- {error}")
    raise SystemExit(1)

print("VALIDATION PASSED")
print(f"- master files: 1")
print(f"- sub-plan files: {len(actual_subplans)}")
print("- planning prompts: 33")
print("- execution prompts: 33")
print("- rubric ownership: Sheet3!E3:E62 exactly once")
print("- compatible score ceiling: 99/100 with E49 Out of Scope")
print("- source hashes: unchanged")
print("- dependency graph: acyclic")
