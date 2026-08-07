from __future__ import annotations

from datetime import datetime

from airflow import DAG
from airflow.operators.python import PythonOperator

from vina_bim_shop.orchestration.rag_index_pipeline import run_rag_index_stage


def _run(stage: str, **context: object) -> dict[str, object]:
    return run_rag_index_stage(stage, **context)


with DAG(
    dag_id="rag_index_pipeline",
    description=(
        "Paused manual local RAG candidate contract. Each task resumes a run-scoped "
        "JSON handoff on the configured shared local handoff_root, referenced by "
        "XCom; promotion defaults to false. Deployment-supplied storage adapters "
        "remain a local integration gate."
    ),
    start_date=datetime(2026, 6, 1),
    schedule=None,
    catchup=False,
    is_paused_upon_creation=True,
    tags=["edai2", "rag", "local-contract"],
) as dag:
    parse_sources = PythonOperator(
        task_id="parse_sources",
        python_callable=_run,
        op_kwargs={"stage": "parse_sources"},
        retries=1,
    )
    chunk = PythonOperator(
        task_id="chunk",
        python_callable=_run,
        op_kwargs={"stage": "chunk"},
        retries=1,
    )
    embed = PythonOperator(
        task_id="embed",
        python_callable=_run,
        op_kwargs={"stage": "embed"},
        retries=1,
    )
    postgres_upsert_candidate_and_pgvector_index = PythonOperator(
        task_id="postgres_upsert_candidate_and_pgvector_index",
        python_callable=_run,
        op_kwargs={"stage": "postgres_upsert_candidate_and_pgvector_index"},
        retries=1,
    )
    register_feast_feature_view = PythonOperator(
        task_id="register_feast_feature_view",
        python_callable=_run,
        op_kwargs={"stage": "register_feast_feature_view"},
        retries=1,
    )
    emit_candidate_lineage = PythonOperator(
        task_id="emit_candidate_lineage",
        python_callable=_run,
        op_kwargs={"stage": "emit_candidate_lineage"},
        retries=1,
    )
    validate = PythonOperator(
        task_id="validate",
        python_callable=_run,
        op_kwargs={"stage": "validate"},
        retries=1,
    )
    promote_compare_and_swap = PythonOperator(
        task_id="promote_compare_and_swap",
        python_callable=_run,
        op_kwargs={"stage": "promote_compare_and_swap"},
        retries=0,
    )
    emit_active_lineage_and_read_back = PythonOperator(
        task_id="emit_active_lineage_and_read_back",
        python_callable=_run,
        op_kwargs={"stage": "emit_active_lineage_and_read_back"},
        retries=0,
    )

    (
        parse_sources
        >> chunk
        >> embed
        >> postgres_upsert_candidate_and_pgvector_index
        >> register_feast_feature_view
        >> emit_candidate_lineage
        >> validate
        >> promote_compare_and_swap
        >> emit_active_lineage_and_read_back
    )
