from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "tmp" / "edai2-plan" / "execution-v1" / "00-master-session-prompts.md"
REPO = r"C:\Users\oou1hc\Documents\FSDS\ecom-data-platform-submission"

SOURCE_HASHES = {
    "tmp/edai2-plan/03_data_generator_improvement.md": "3c906ae30ac0fee606e96608a7b5759cd7439ae048c4c12a84511fce5cc33ae6",
    "tmp/edai2-plan/04.2_llm_design.md": "b8be3ef5c84fe4d6fe52e8894c3c5dc1c3babc898e2a87684b2b8ff720d6d079",
    "tmp/rubic-check/Coursework Tracking (Public).xlsx": "71b2403e068081b00245bea5e15c5754f3762ad354e0a3a6576d69e4963c8657",
}

TOPICS = [
    (0, "local/00-workstation-toolchain-context-safety.md", "Local foundation", "Local-only", [], "Workstation prerequisites and kube-context isolation", "Supporting prerequisite"),
    (1, "local/01-section03-config-drift-sampler.md", "Local foundation", "Local-only", [0], "Section 03 Tasks 1-2: typed configuration and deterministic drift sampling", "Contributes to E32-E33"),
    (2, "local/02-section03-labels-psi-candidate-evidence.md", "Local foundation", "Local-only", [1], "Section 03 Tasks 3-4: labels, PSI, training join, and candidate evidence", "Contributes to E32-E34"),
    (3, "local/03-section03-dbt-gold-contracts.md", "Local foundation", "Local-only", [2], "Section 03 Task 5: leakage-safe dbt Gold contracts", "Supports E34"),
    (4, "local/04-section03-spark-gold-parity.md", "Local foundation", "Local-only", [3], "Section 03 Task 6: Spark/Iceberg outputs and three-way parity", "Supports E34"),
    (5, "local/05-section03-airflow-datahub-governance.md", "Local foundation", "Local-only", [4], "Section 03 Tasks 7-8: DP3 validation and DataHub governance", "Supports E32-E34"),
    (6, "local/06-section03-docs-schema-finalizer.md", "Local foundation", "Local-only", [5], "Section 03 Tasks 9 and Task 10 finalizer implementation", "Supports E32-E34"),
    (7, "local/07-section03-canonical-runtime-promotion.md", "Local foundation", "Local runtime", [6], "Section 03 Task 10 canonical seed-42 capture and immutable promotion", "E32-E34"),
    (8, "local/08-edai2-prerequisite-contracts.md", "Local EDAI2", "Local-only", [7], "EDAI2 Tasks 0-1: fail-closed prerequisite and repository contracts", "Supports E32-E34, E59-E60"),
    (9, "local/09-rag-source-chunking-embeddings.md", "Local EDAI2", "Local-only", [8], "EDAI2 Task 2: trusted sources, versions, 400/80 chunks, embeddings", "Supports E8-E9, E61"),
    (10, "local/10-rag-index-feast-airflow-datahub.md", "Local EDAI2", "Local integration", [9], "EDAI2 Task 2: candidate/active index, Feast, Airflow, DataHub", "Supports E8-E9"),
    (11, "local/11-retrieval-api-mcp-safety.md", "Local EDAI2", "Local-only", [10], "EDAI2 Task 3: async retrieval API, MCP, grounding, citation safety", "Supports E10-E12, E62"),
    (12, "local/12-section03-loader-drift-api-mcp.md", "Local EDAI2", "Local-only", [8], "EDAI2 Task 4: strict Section 03 loader and async drift API/MCP", "Supports E16-E18"),
    (13, "local/13-coordinator-inference-routing-telemetry.md", "Local EDAI2", "Local-only", [11, 12], "EDAI2 Task 5: observed inference, coordinator routing, telemetry", "Supports E24-E26, E50, E54-E57"),
    (14, "local/14-agent-security-registry-notebooks.md", "Local EDAI2", "Local-only", [13], "EDAI2 Task 5: SandboxAgents, registry contracts, notebooks", "Supports E13-E25"),
    (15, "local/15-evaluation-test-quality-load.md", "Local EDAI2", "Local-only", [14], "EDAI2 Task 6: evaluation, coverage, EP/BVA, mutation, properties, load", "Supports E27-E31, E61-E62"),
    (16, "local/16-images-jenkins-ci.md", "Local EDAI2", "Local-only", [15], "EDAI2 Task 6: six images, six Jenkins pipelines, change maps", "Supports E35-E40"),
    (17, "local/17-terraform-vault-iac-static.md", "Local EDAI2", "Local-only", [16], "EDAI2 Task 7 static Terraform, Vault, IAM, budget validation", "Supports E46, E48, E58"),
    (18, "local/18-platform-helm-kustomize.md", "Local EDAI2", "Local-only", [17], "EDAI2 Task 8 static platform Helm/Kustomize contracts", "Supports E3-E7, E41-E47"),
    (19, "local/19-workload-charts-streaming-keda-experiments.md", "Local EDAI2", "Local-only", [18], "EDAI2 Task 9 workload charts, streaming, KEDA, warm-up, A/B definitions", "Supports E12-E26, E35-E40, E56-E57"),
    (20, "local/20-observability-ingress-screenshot-contracts.md", "Local EDAI2", "Local-only", [19], "EDAI2 Task 10 observability, ingress, evidence-capture contracts", "Supports E41-E55"),
    (21, "local/21-kind-lean-preflight.md", "Local EDAI2", "Kind smoke only", [20], "Lean single-node Kind render/install/smoke preflight", "No GKE rubric credit"),
    (22, "gcp/22-gcp-account-budget-terraform-apply.md", "Live GCP", "GCP mutation", [21], "EDAI2 Task 7 authorized account gate, budget, Terraform plan/apply", "E48"),
    (23, "gcp/23-vault-kms-model-cache-bootstrap.md", "Live GCP", "GCP mutation", [22], "EDAI2 Task 8 Vault/KMS bootstrap and immutable model cache", "Supports E3-E4, E46, E58"),
    (24, "gcp/24-compact-platform-install.md", "Live GCP", "GCP mutation", [23], "EDAI2 Task 8 compact platform, gateway, llm-d, kagent, registry install", "E3-E4, E6"),
    (25, "gcp/25-jenkins-six-workload-deploy.md", "Live GCP", "GCP mutation", [24], "EDAI2 Task 9 six CI/CD workload deployments and Section 03 activation", "E10-E12, E16-E18"),
    (26, "gcp/26-keda-agent-ha-registry-rollbacks.md", "Live GCP", "GCP mutation", [25], "EDAI2 Task 9 KEDA, agents, HA, registry, rollback exercises", "E7, E13-E15, E19-E21, E24"),
    (27, "gcp/27-observability-https-jenkins-evidence.md", "Live GCP", "GCP evidence", [26], "EDAI2 Tasks 10-11 observability, HTTPS, and six Jenkins records", "E35-E43, E45-E47, E50-E55"),
    (28, "gcp/28-rag-inference-benchmarks.md", "Live GCP", "GCP evidence lease", [27], "EDAI2 Task 12 canonical RAG and model benchmark evidence", "E5, E8-E9, E26"),
    (29, "gcp/29-evaluation-ab-notebooks-load-test-evidence.md", "Live GCP", "GCP evidence lease", [28], "EDAI2 Task 12 evaluation, A/B, notebooks, load, runtime safety proof", "E22-E23, E25, E27-E31, E44, E56-E57, E61-E62"),
    (30, "gcp/30-persistence-vault-recovery-resume.md", "Live GCP", "GCP evidence lease", [29], "EDAI2 Task 12 persistence, Vault recovery, suspend/resume fingerprints", "E58"),
    (31, "gcp/31-final-screenshot-qa-teardown.md", "Live GCP", "GCP evidence lease/teardown", [30], "EDAI2 Task 12 final screenshot audit, manifest sealing, teardown", "Cross-cutting evidence gate"),
    (32, "final/32-documentation-rubric-finalization.md", "Final local closeout", "Local-only", [31], "EDAI2 Task 13 README, diagrams, LLD, fail-closed rubric finalization", "E49 OOS, E59-E60, Row 2"),
]

POINTS = {
    **{n: 2 for n in range(3, 10)},
    10: 1, 11: 1, 12: 2, 13: 2, 14: 1, 15: 2,
    16: 1, 17: 1, 18: 2, 19: 2, 20: 1, 21: 2,
    22: 2, 23: 2, 24: 2, 25: 2, 26: 2, 27: 1,
    28: 2, 29: 2, 30: 2, 31: 2, 32: 1, 33: 1, 34: 2,
    35: 2, 36: 2, 37: 2, 38: 2, 39: 2, 40: 2,
    41: 2, 42: 2, 43: 2, 44: 2, 45: 2, 46: 2,
    47: 1, 48: 1, 49: 1, 50: 1, 51: 1, 52: 1,
    53: 1, 54: 2, 55: 2, 56: 1, 57: 1, 58: 1,
    59: 2, 60: 1, 61: 2, 62: 2,
}

OWNERS = {
    3: 24, 4: 24, 5: 28, 6: 24, 7: 26, 8: 28, 9: 28,
    10: 25, 11: 25, 12: 25, 13: 26, 14: 26, 15: 26,
    16: 25, 17: 25, 18: 25, 19: 26, 20: 26, 21: 26,
    22: 29, 23: 29, 24: 26, 25: 29, 26: 28,
    27: 29, 28: 29, 29: 29, 30: 29, 31: 29,
    32: 7, 33: 7, 34: 7,
    35: 27, 36: 27, 37: 27, 38: 27, 39: 27, 40: 27,
    41: 27, 42: 27, 43: 27, 44: 29, 45: 27, 46: 27, 47: 27,
    48: 22, 49: 32,
    50: 27, 51: 27, 52: 27, 53: 27, 54: 27, 55: 27,
    56: 29, 57: 29, 58: 30, 59: 32, 60: 32, 61: 29, 62: 29,
}

SCREENSHOTS = {
    22: ["terraform_apply.png", "gcp_billing_spend.png"],
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

SOURCE_TASK_OWNERS = [
    ("Section 03", 1, "01", "Typed configuration and validation"),
    ("Section 03", 2, "01", "Deterministic timestamp drift sampler"),
    ("Section 03", 3, "02", "Labels, point-in-time features, PSI, alerts"),
    ("Section 03", 4, "02", "Candidate artifacts and immutable lifecycle"),
    ("Section 03", 5, "03", "dbt Gold outputs and contracts"),
    ("Section 03", 6, "04", "Spark/Iceberg outputs and parity"),
    ("Section 03", 7, "05", "Airflow DP3 validation"),
    ("Section 03", 8, "05", "DataHub lineage and assertions"),
    ("Section 03", 9, "06", "Docs, schemas, CLI, Make"),
    ("Section 03", 10, "06 + 07", "Finalizer plus canonical runtime promotion"),
    ("EDAI2", 0, "08", "Verified Section 03 prerequisite gate"),
    ("EDAI2", 1, "08", "Dependencies, contracts, repository boundaries"),
    ("EDAI2", 2, "09 + 10", "RAG sources through governed active index"),
    ("EDAI2", 3, "11", "Retrieval API/MCP and grounding safety"),
    ("EDAI2", 4, "12", "Section 03 loader and drift API/MCP"),
    ("EDAI2", 5, "13 + 14", "Inference/coordinator plus agents/registry/notebooks"),
    ("EDAI2", 6, "15 + 16", "Evaluation quality gates plus images/Jenkins CI"),
    ("EDAI2", 7, "17 + 22", "Static IaC then authorized GCP apply"),
    ("EDAI2", 8, "18 + 23 + 24", "Static platform, Vault/cache, compact install"),
    ("EDAI2", 9, "19 + 25 + 26", "Workload definitions, deployment, KEDA/rollback"),
    ("EDAI2", 10, "20 + 27", "Observability/ingress contracts and live evidence"),
    ("EDAI2", 11, "27", "Six Jenkins records without rebuilding"),
    ("EDAI2", 12, "28 + 29 + 30 + 31", "Four bounded live evidence leases and teardown"),
    ("EDAI2", 13, "32", "Documentation and fail-closed rubric finalization"),
]


def topic_by_number(number: int) -> tuple:
    return next(topic for topic in TOPICS if topic[0] == number)


def prompt_predecessors(numbers: list[int]) -> str:
    if not numbers:
        return "None; this is the first topic."
    return ", ".join(
        f"`tmp/edai2-plan/execution-v1/{topic_by_number(n)[1]}` Completion Record"
        for n in numbers
    )


def planning_prompt(topic: tuple) -> str:
    number, path, phase, classification, predecessors, purpose, rubric = topic
    gcp_rule = (
        "This topic may inspect GCP read-only during planning, but make no cloud mutation. "
        "Identify every required project, billing, IAM, budget, trial, recovery-sink, DNS, and spend input; "
        "the execution phase must stop safely if any required input is absent."
        if classification.startswith("GCP")
        else "This is a local planning topic: do not mutate GCP or describe local Kind output as GKE evidence."
    )
    return f"""You are planning EDAI2 Topic {number:02d} in the existing Codex task workflow.

Repository: `{REPO}`
Authoritative topic file: `tmp/edai2-plan/execution-v1/{path}`
Purpose: {purpose}
Classification: {classification}
Primary rubric responsibility: {rubric}
Required predecessor records: {prompt_predecessors(predecessors)}

This is the read-only planning phase in a two-phase Codex chat. Before any repository inspection, read `C:\\Users\\oou1hc\\.codex\\RTK.md` and use relevant available skills. Run shell commands only through `rtk`. Read the entire topic file, the applicable parts of both source plans, and `tmp/rubic-check/Coursework Tracking (Public).xlsx`/Sheet3. Verify the three locked SHA-256 values recorded in the topic file and start with `rtk git status --short --branch`. Stay in the current checkout and branch. Do not create/switch branches, create worktrees, edit files, stage, commit, push, deploy, install, or change local/cloud runtime state in this phase. Preserve unrelated user work.

Read every predecessor Completion Record listed above and inspect current repository/runtime state read-only so the handoff reflects changes made by earlier sessions. {gcp_rule} Every Kubernetes command proposed must name the intended kubeconfig and context; the current default context may be a nonlocal corporate cluster.

Return a decision-complete execution handoff in chat with: assumptions verified; current-state delta; exact files and interfaces; ordered test-first edits; exact commands and expected results; evidence/screenshot ownership; resource/budget gates; cleanup; rollback/recovery; rubric disposition; and stop conditions. Resolve uncertainty through inspection. Do not execute the handoff and do not update the Completion Record yet."""


def execution_prompt(topic: tuple) -> str:
    number, path, phase, classification, predecessors, purpose, rubric = topic
    gcp_rule = (
        "Before the first cloud mutation, re-run every external-input, cost, lease, IAM, billing, and target-context gate from the topic. "
        "If any gate is unavailable or ambiguous, record the exact blocker and stop without partial provisioning."
        if classification.startswith("GCP")
        else "Do not perform live GCP mutations. Any Kind result must be labelled `local preflight` and must not be claimed as GKE rubric evidence."
    )
    screenshot_names = SCREENSHOTS.get(number, [])
    screenshot_rule = (
        "This topic owns these final captures: "
        + ", ".join(f"`{name}`" for name in screenshot_names)
        + ". Apply the topic's full PNG integrity, viewport, selector, manifest, redaction, and original-resolution visual-QA gate."
        if screenshot_names
        else "Do not manufacture screenshots. Record only evidence this topic actually owns; successor topics own final UI captures where specified."
    )
    return f"""Continue this same Codex chat with EDAI2 Topic {number:02d}; now execute the approved handoff.

Repository: `{REPO}`
Authoritative topic file: `tmp/edai2-plan/execution-v1/{path}`
Purpose: {purpose}
Required predecessor records: {prompt_predecessors(predecessors)}

Re-read the topic file and your planning handoff. Recompute the three locked source hashes and run `rtk git status --short --branch` before edits. Stay in the existing checkout and branch. Do not create/switch branches or worktrees, and do not stage, commit, push, or open a PR. Preserve unrelated changes. Use `apply_patch` for repository text edits; `uv add` is the sole dependency-manager write exception and its diff must be inspected. Make recipes invoke `uv run`; operator-facing Make commands use `rtk make`.

Execute the topic in its written order using test-first changes: establish the failing check, make the minimum scoped change, run the focused check, then the prescribed regression gate. Use one runtime slice at a time. Every Kubernetes command must specify the intended kubeconfig and context; never rely on the current default context. Never prune Docker data or stop unrelated containers automatically. {gcp_rule}

{screenshot_rule} Machine evidence is authoritative. Never fabricate a pass, score, measurement, screenshot, or hash. After one bounded tuning retry, leave a failed empirical criterion Partial/Missing with its measured result.

Finish by updating only this topic file's Completion Record with status, affected files, exact commands and exit codes, evidence paths and SHA-256 values, screenshot QA, cleanup/runtime release, limitations, and successor handoff. Re-run the topic acceptance checks and `rtk git status --short --branch`, then report the truthful outcome."""


def build() -> str:
    assert len(TOPICS) == 33
    assert set(OWNERS) == set(range(3, 63))
    assert sum(POINTS.values()) == 100
    assert sum(POINTS[cell] for cell in range(3, 63) if cell != 49) == 99
    flat_shots = [name for names in SCREENSHOTS.values() for name in names]
    assert len(flat_shots) == 33 and len(set(flat_shots)) == 33

    lines: list[str] = []
    lines.extend([
        "# EDAI2 Master Session Prompts",
        "",
        "## Purpose and operating model",
        "",
        "This is the copy/paste control plane for 33 topic-specific Codex chats. Each topic uses one chat in two phases: paste its planning prompt, review the decision-complete handoff, then paste its execution prompt into the same chat. Execute topics serially in numeric order and complete the topic's Completion Record before beginning the next execution phase.",
        "",
        "This package creates planning artifacts only. The later topic chats implement EDAI2 on the checkout already open at package creation (`feature/implement-edai2`). They must never create a worktree or branch, switch branches, stage, commit, push, or open a PR unless the user separately asks.",
        "",
        "## Locked sources",
        "",
        "| Source | Required SHA-256 |",
        "|---|---|",
    ])
    for source, digest in SOURCE_HASHES.items():
        lines.append(f"| `{source}` | `{digest}` |")
    lines.extend([
        "",
        "Every session must fail closed before edits if any digest differs. The rubric source is `tmp/rubic-check/Coursework Tracking (Public).xlsx`, with scored cells `Sheet3!E3:E62`; Row 2 is mandatory but unscored.",
        "",
        "## Pinned workstation baseline",
        "",
        "| Tool | Winget ID | Required version/reference |",
        "|---|---|---|",
        "| Kind | `Kubernetes.kind` | [0.32.0](https://github.com/kubernetes-sigs/kind/releases/tag/v0.32.0) |",
        "| Kind node | — | `kindest/node:v1.35.5@sha256:ce977ae6d65918d0b58a5f8b5e940429c2ce42fa3a5619ec2bbc60b949c0ac95` |",
        "| Helm | `Helm.Helm` | [3.20.0](https://github.com/helm/helm/releases/tag/v3.20.0) |",
        "| Terraform | `Hashicorp.Terraform` | [1.15.8](https://developer.hashicorp.com/terraform/install) |",
        "| Google Cloud CLI | `Google.CloudSDK` | [577.0.0](https://docs.cloud.google.com/sdk/docs/install-sdk) |",
        "| kubectl | existing client | 1.34.1; within one minor of the Kind 1.35.5 node under the [version-skew policy](https://kubernetes.io/releases/version-skew-policy/) |",
        "",
        "## Shared execution rules",
        "",
        "1. Read the complete topic file and predecessor Completion Records before acting.",
        "2. Start and finish with `rtk git status --short --branch`; preserve unrelated work.",
        "3. Use the current checkout/branch only. No branch, worktree, staging, commit, push, or PR.",
        "4. Planning phase is read-only. Execution begins only after the same chat has produced its decision-complete handoff.",
        "5. Use `apply_patch` for repository text edits. `uv add` is permitted only as the dependency-manager exception; inspect both `pyproject.toml` and `uv.lock` diffs. Make recipes use `uv run`; operators use `rtk make`.",
        "6. Run one execution/runtime topic at a time. Never auto-prune Docker data or stop unrelated containers.",
        "7. Every Kubernetes command names an explicit kubeconfig and context. Never use the current default corporate context.",
        "8. Kind output is labelled `local preflight` and earns no GKE rubric credit.",
        "9. GCP work stops before mutation if project, billing, IAM, trial-expiry, current-spend, recovery-sink, DNS, lease, or other required inputs are missing.",
        "10. `tmp/edai2-gcp/coursework.auto.tfvars` stays untracked and is selected through `EDAI2_TFVARS_PATH`.",
        "11. Machine-readable evidence governs. After one bounded tuning retry, failed empirical gates remain Partial/Missing; compatible maximum is 99 because E49 is permanently Out of Scope.",
        "",
        "## Locked reconciliation rules",
        "",
        "- Upload and verify Section 03 before drift deployment; the drift Helm/Jenkins path owns activation, with no duplicate post-deploy import.",
        "- Derive Section 03 runtime timestamps from generator configuration, never from copied literals.",
        "- Reuse an identical immutable bundle only after full hash/schema verification; reject a same-ID content mismatch.",
        "- Keep the CI bootstrap RAG index distinct from the later canonical evidence index.",
        "- Five `SandboxAgent` resources represent exactly three logical identities: retrieval, drift, and coordinator.",
        "- Scale the inactive model to zero during the other model's two-replica factorial cells.",
        "- Topics 28-31 each receive a separate at-most-six-hour evidence lease and budget gate.",
        "- Capture six distinct Jenkins job pages in one browser session without rebuilding.",
        "",
        "## Local Kind guardrail",
        "",
        "Topic 21 uses one control-plane node named `edai2-lean`, kubeconfig `tmp/edai2-kind/kubeconfig`, context `kind-edai2-lean`, and the pinned node image digest above. Do not run the broad Compose platform and Kind simultaneously. Namespace aggregate requests are at most 6 CPU/16 GiB, limits at most 10 CPU/22 GiB, with at most 30 pods, 8 PVCs/20 GiB, and zero `LoadBalancer` services. KEDA maximum is one locally; scale-to-two is render/static validation only. Skip full llm-d, Jenkins, observability, Vault recovery, and every GKE-specific proof.",
        "",
        "## Screenshot acceptance gate",
        "",
        "Section 03 remains 1600×900. Browser evidence uses a fixed 1600×1000 viewport and primary captures are full contextual viewport images, not element crops. A capture is accepted only when target selectors are fully inside the viewport, the application is stable, and title/context are visible. Write to a temporary path, verify the PNG signature, decode and fully load it, then atomically replace the final path. Record dimensions, UTC, URL/source, commit/revision, visible selectors, SHA-256, linked machine evidence, and what the image proves/does not prove. Reject blank/near-uniform, clipped, loading, login-only, generic-home, error, stale, secret-bearing, or PII-bearing images. Inspect every accepted image at original resolution.",
        "",
        "## Schedule and dependency catalog",
        "",
        "| # | Topic file | Phase | Class | Direct prerequisites | Purpose | Rubric role |",
        "|---:|---|---|---|---|---|---|",
    ])
    for number, path, phase, classification, predecessors, purpose, rubric in TOPICS:
        predecessor_text = ", ".join(f"{n:02d}" for n in predecessors) or "—"
        lines.append(
            f"| {number:02d} | [`{path}`]({path}) | {phase} | {classification} | {predecessor_text} | {purpose} | {rubric} |"
        )
    lines.extend([
        "",
        "```mermaid",
        "flowchart LR",
        "  subgraph L1[\"Local foundation\"]",
        "    T00 --> T01 --> T02 --> T03 --> T04 --> T05 --> T06 --> T07",
        "  end",
        "  subgraph L2[\"Local EDAI2 and Kind\"]",
        "    T07 --> T08 --> T09 --> T10 --> T11",
        "    T08 --> T12",
        "    T11 --> T13",
        "    T12 --> T13 --> T14 --> T15 --> T16 --> T17 --> T18 --> T19 --> T20 --> T21",
        "  end",
        "  subgraph G[\"Live GCP\"]",
        "    T21 --> T22 --> T23 --> T24 --> T25 --> T26 --> T27 --> T28 --> T29 --> T30 --> T31",
        "  end",
        "  T31 --> T32[\"Final local closeout\"]",
        "```",
        "",
        "## Source-plan task ownership",
        "",
        "| Source plan | Task | Owning topic(s) | Boundary |",
        "|---|---:|---|---|",
    ])
    for source, task, owners, boundary in SOURCE_TASK_OWNERS:
        lines.append(f"| {source} | {task} | {owners} | {boundary} |")
    lines.extend([
        "",
        "## Primary rubric ownership",
        "",
        "A primary owner is the session that must close the cell's final evidence gate. Earlier implementation sessions may contribute but cannot duplicate ownership. E49 retains workbook value 1, earns 0, and must remain `Out of Scope`.",
        "",
        "| Cell | Pts | Primary topic | Disposition |",
        "|---|---:|---:|---|",
    ])
    for cell in range(3, 63):
        disposition = "Out of Scope; earned 0" if cell == 49 else "Evidence gate owned here"
        lines.append(f"| `Sheet3!E{cell}` | {POINTS[cell]} | {OWNERS[cell]:02d} | {disposition} |")
    lines.extend([
        "",
        "| Total workbook points | Compatible earned ceiling |",
        "|---:|---:|",
        "| 100 | 99 |",
        "",
        "Row 2 is mandatory and owned by Topic 32 without points. Topics 07 and 32 must keep Section 03 prerequisite points and direct EDAI2 points separate in the final manifest.",
        "",
        "## Screenshot ownership",
        "",
        "| Topic | Final PNGs |",
        "|---:|---|",
    ])
    for number in sorted(SCREENSHOTS):
        lines.append(
            f"| {number:02d} | " + ", ".join(f"`{name}`" for name in SCREENSHOTS[number]) + " |"
        )
    lines.extend([
        "",
        "The table contains the source plan's 32 EDAI2 PNGs plus `gcp_billing_spend.png`. Section 03's separate `section03_config_and_training_join.png` is owned by Topic 07.",
        "",
        "## Copy/paste prompt pairs",
        "",
        "Paste the planning prompt first. After reviewing the handoff in that same chat, paste the execution prompt immediately below it. Do not have two execution prompts active at once.",
        "",
    ])
    for topic in TOPICS:
        number, path, *_ = topic
        lines.extend([
            f"### Topic {number:02d} planning prompt",
            "",
            "```text",
            planning_prompt(topic),
            "```",
            "",
            f"### Topic {number:02d} execution prompt",
            "",
            "```text",
            execution_prompt(topic),
            "```",
            "",
        ])
    return "\n".join(lines).rstrip() + "\n"


OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(build(), encoding="utf-8", newline="\n")
