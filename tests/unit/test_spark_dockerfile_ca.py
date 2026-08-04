from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DOCKERFILE_PATH = REPO_ROOT / "infra" / "spark" / "Dockerfile"


def test_spark_dockerfile_installs_verified_bosch_ca_before_maven_downloads() -> None:
    dockerfile = DOCKERFILE_PATH.read_text(encoding="utf-8")

    ca_install = dockerfile.index("apt-get install -y --no-install-recommends ca-certificates")
    ca_update = dockerfile.index("update-ca-certificates")
    first_maven_download = dockerfile.index("curl -fsSL")

    assert ca_install < ca_update < first_maven_download
    assert "COPY infra/spark/certs/RB_RootCA_RSA_G01-pem.cer /usr/local/share/ca-certificates/" in dockerfile
    assert "-k" not in dockerfile
    assert "--insecure" not in dockerfile
    assert "--proxy-insecure" not in dockerfile


def test_spark_bosch_root_certificate_is_in_build_context() -> None:
    certificate = REPO_ROOT / "infra" / "spark" / "certs" / "RB_RootCA_RSA_G01-pem.cer"

    assert certificate.is_file()
    certificate_text = certificate.read_text(encoding="ascii")
    assert certificate_text.startswith("-----BEGIN CERTIFICATE-----")
    assert certificate_text.rstrip().endswith("-----END CERTIFICATE-----")
