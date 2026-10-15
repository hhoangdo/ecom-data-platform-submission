"""A repeated preflight may reuse an identical private command contract."""
import json
import pytest
from scripts.gke import check_budget as budget


def test_identical_contract_is_reused_without_rewriting(tmp_path, monkeypatch):
    contract = {"environment": {"TF_DATA_DIR": "private"}, "backend_bucket_proof_sha256": "a" * 64}
    path = tmp_path / "topic22-terraform-runtime.json"
    original = json.dumps(contract, indent=2).encode()
    path.write_bytes(original)
    monkeypatch.setattr(budget, "build_terraform_runtime_contract", lambda **kwargs: contract)
    result = budget.write_terraform_runtime_contract(backend_config="unused", tfvars="unused", tf_data_dir=tmp_path,
                                                   workspace=tmp_path, backend_bucket_proof_sha256="a" * 64)
    assert result == path and path.read_bytes() == original


def test_changed_contract_is_rejected_without_overwriting(tmp_path, monkeypatch):
    path = tmp_path / "topic22-terraform-runtime.json"
    path.write_text('{"backend_bucket_proof_sha256":"old"}')
    original = path.read_bytes()
    monkeypatch.setattr(budget, "build_terraform_runtime_contract", lambda **kwargs: {"backend_bucket_proof_sha256": "new"})
    with pytest.raises(FileExistsError):
        budget.write_terraform_runtime_contract(backend_config="unused", tfvars="unused", tf_data_dir=tmp_path,
                                                workspace=tmp_path, backend_bucket_proof_sha256="a" * 64)
    assert path.read_bytes() == original
