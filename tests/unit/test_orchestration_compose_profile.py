from pathlib import Path

from compose_model import load_compose_model


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_root_compose_declares_orchestration_services_and_ports() -> None:
    compose = load_compose_model(_repo_root())

    services = compose["services"]
    expected = {"airflow-webserver", "airflow-scheduler", "airflow-init", "gx-docs"}
    assert expected.issubset(services)

    for service_name in expected:
        assert services[service_name]["profiles"] == ["orchestration", "all"]

    assert "8082:8080" in services["airflow-webserver"]["ports"]
    assert "8088:80" in services["gx-docs"]["ports"]


def test_orchestration_services_reuse_shared_postgres_and_repo_workspace() -> None:
    compose = load_compose_model(_repo_root())
    services = compose["services"]

    assert "orchestration" in services["lakehouse-postgres"]["profiles"]
    assert "airflow-init" in services["airflow-webserver"]["depends_on"]
    assert "airflow-init" in services["airflow-scheduler"]["depends_on"]

    for service_name in ["airflow-webserver", "airflow-scheduler", "airflow-init"]:
        service = services[service_name]
        assert service["build"] == {
            "context": ".",
            "dockerfile": "./infra/orchestration/airflow/Dockerfile",
        }
        assert "./infra/orchestration/airflow/dags:/opt/airflow/dags:ro" in service["volumes"]
        assert "./src:/workspace/src:ro" in service["volumes"]
        assert "airflow_logs:/opt/airflow/logs" in service["volumes"]
        assert "/var/run/docker.sock:/var/run/docker.sock" not in service["volumes"]

    assert "airflow_logs" in compose["volumes"]


def test_airflow_services_include_socket_free_spark_runtime() -> None:
    compose = load_compose_model(_repo_root())
    for service_name in ["airflow-webserver", "airflow-scheduler", "airflow-init"]:
        environment = compose["services"][service_name]["environment"]
        assert environment["VBS_SPARK_SUBMIT_BIN"] == "/opt/spark/bin/spark-submit"
        assert environment["VBS_SPARK_DEPLOY_MODE"] == "client"
        assert environment["VBS_SPARK_DRIVER_SERVICE_URL"] == "http://spark-driver:8090/run"
        assert environment["VBS_SPARK_DRIVER_SERVICE_TIMEOUT_SECONDS"] == "2400"
        assert environment["SPARK_HOME"] == "/opt/spark"
        assert environment["JAVA_HOME"] == "/opt/java/openjdk"


def test_env_example_documents_orchestration_urls_and_credentials() -> None:
    env_example = (_repo_root() / ".env.example").read_text(encoding="utf-8")

    for expected_line in [
        "VBS_AIRFLOW_UI_URL=http://localhost:8082",
        "VBS_GX_DOCS_URL=http://localhost:8088",
        "VBS_AIRFLOW_ADMIN_USERNAME=airflow",
        "VBS_AIRFLOW_ADMIN_PASSWORD=airflow",
    ]:
        assert expected_line in env_example


def test_airflow_services_bypass_inherited_proxy_for_internal_runtime() -> None:
    compose = load_compose_model(_repo_root())
    internal_hosts = {
        "minio",
        "trino",
        "kafka",
        "datahub-gms",
        "spark-master",
        "spark-history-server",
        "lakehouse-postgres",
        "localhost",
        "127.0.0.1",
        "::1",
    }

    for service_name in ["airflow-webserver", "airflow-scheduler", "airflow-init"]:
        environment = compose["services"][service_name]["environment"]
        assert environment["HTTP_PROXY"] == ""
        assert environment["HTTPS_PROXY"] == ""
        assert environment["ALL_PROXY"] == ""
        assert environment["http_proxy"] == ""
        assert environment["https_proxy"] == ""
        assert environment["all_proxy"] == ""
        assert set(environment["NO_PROXY"].split(",")) >= internal_hosts
        assert set(environment["no_proxy"].split(",")) >= internal_hosts


def test_airflow_runtime_assets_exist() -> None:
    repo_root = _repo_root()
    assert (repo_root / "infra" / "orchestration" / "airflow" / "Dockerfile").is_file()
    assert (repo_root / "infra" / "orchestration" / "airflow" / "dags").is_dir()
    dockerfile = (repo_root / "infra" / "orchestration" / "airflow" / "Dockerfile").read_text(encoding="utf-8")
    assert "/usr/local/bin/mc" in dockerfile
    assert '"numpy==1.26.4"' in dockerfile
    assert '"scipy==1.14.1"' in dockerfile
    assert "FROM vina-bim-shop/spark:4.0.0-iceberg-1.10.1 AS spark-runtime" in dockerfile
    assert "COPY --from=spark-runtime /opt/spark /opt/spark" in dockerfile
    assert "COPY --from=spark-runtime /opt/java/openjdk /opt/java/openjdk" in dockerfile


def test_airflow_init_mounts_and_runs_coursework_metadata_seed() -> None:
    compose = load_compose_model(_repo_root())
    init = compose["services"]["airflow-init"]

    assert "./infra/orchestration/airflow/bootstrap:/opt/airflow/bootstrap:ro" in init["volumes"]
    assert "seed_coursework_metadata.py" in str(init["command"])
    assert init["command"][0] == "bash"
    assert "AIRFLOW_CONN_DATAHUB_REST_DEFAULT" in init["environment"]
    assert "VBS_KAFKA_BOOTSTRAP_SERVERS" in init["environment"]
    assert "VBS_MINIO_INTERNAL_ENDPOINT" in init["environment"]
