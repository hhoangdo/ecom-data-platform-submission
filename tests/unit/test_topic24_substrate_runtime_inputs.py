from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from scripts.gke.topic24_postrender import render


ROOT = Path(__file__).resolve().parents[2]
API_IMAGE = "us-central1-docker.pkg.dev/example/edai2/substrate-api@sha256:" + "a" * 64
GSA_EMAIL = "edai2-coordinator@example.iam.gserviceaccount.com"


def substrate_api() -> dict:
    return {"apiVersion": "apps/v1", "kind": "Deployment",
            "metadata": {"name": "ate-api-server-deployment", "namespace": "edai2"},
            "spec": {"template": {"spec": {"containers": [
                {"name": "ate-api-server", "image": "ghcr.io/kagent-dev/substrate/ateapi:0.0.6", "args": []},
                {"name": "bootstrap", "image": "busybox:1.36"},
            ]}}}}


def atelet_service_account() -> dict:
    return {"apiVersion": "v1", "kind": "ServiceAccount",
            "metadata": {"name": "atelet", "namespace": "edai2"}}


def test_optional_substrate_image_changes_only_ateapi_container() -> None:
    original = [substrate_api(), atelet_service_account()]
    adapted = render(original, substrate_api_image=API_IMAGE)
    containers = adapted[0]["spec"]["template"]["spec"]["containers"]
    assert containers[0]["image"] == API_IMAGE
    assert containers[1]["image"] == "busybox:1.36"
    assert original == [substrate_api(), atelet_service_account()]


def test_optional_substrate_image_is_a_noop_when_not_provided() -> None:
    api = substrate_api()
    adapted = render([api])
    assert adapted[0]["spec"]["template"]["spec"]["containers"][0]["image"] == api["spec"]["template"]["spec"]["containers"][0]["image"]


def test_optional_substrate_image_requires_the_pinned_api_container() -> None:
    with pytest.raises(ValueError, match="expected one ate-api-server container"):
        render([], substrate_api_image=API_IMAGE)


@pytest.mark.parametrize("image", [
    "us-central1-docker.pkg.dev/example/edai2/substrate-api:latest",
    "us-central1-docker.pkg.dev/example/edai2/substrate-api@sha256:abc",
    "not an image@sha256:" + "a" * 64,
])
def test_optional_substrate_image_requires_sha256_digest_reference(image: str) -> None:
    with pytest.raises(ValueError, match="sha256 digest"):
        render([substrate_api()], substrate_api_image=image)


def test_optional_atelet_wi_annotation_applies_only_to_existing_service_account() -> None:
    original = [atelet_service_account(), {"apiVersion": "apps/v1", "kind": "DaemonSet",
        "metadata": {"name": "atelet", "namespace": "edai2"},
        "spec": {"template": {"metadata": {"labels": {"app": "atelet"}}, "spec": {}}}}]
    adapted = render(original, atelet_wi_annotation=GSA_EMAIL)
    assert adapted[0]["metadata"]["annotations"] == {"iam.gke.io/gcp-service-account": GSA_EMAIL}
    assert "annotations" not in adapted[1]["spec"]["template"]["metadata"]
    assert original[0]["metadata"] == {"name": "atelet", "namespace": "edai2"}


def test_atelet_wi_annotation_is_optional_and_requires_existing_service_account() -> None:
    assert render([atelet_service_account()])[0] == atelet_service_account()
    with pytest.raises(ValueError, match="atelet ServiceAccount"):
        render([], atelet_wi_annotation=GSA_EMAIL)
    with pytest.raises(ValueError, match="service-account email"):
        render([atelet_service_account()], atelet_wi_annotation="principal://bad")


def test_substrate_values_use_chart_supported_gcs_backend_without_ignored_fields() -> None:
    values = yaml.safe_load((ROOT / "infra/helm/edai2/values/substrate.yaml").read_text(encoding="utf-8"))
    assert values["atelet"]["storageBackend"] == "gcs"
    assert "gcsPrefix" not in values["atelet"]
    assert "image" not in values["atelet"]

