FROM python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN groupadd --gid 10001 edai2 && useradd --uid 10001 --gid 10001 --create-home --shell /usr/sbin/nologin edai2
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir .
COPY configs ./configs
COPY data/knowledge ./data/knowledge
COPY scripts ./scripts
USER edai2

FROM runtime AS rag_index
CMD ["python", "scripts/llm/build_index.py"]

FROM runtime AS retrieval_agent
CMD ["uvicorn", "vina_bim_shop.llm.api.retrieval:app", "--host", "0.0.0.0", "--port", "8080"]

FROM runtime AS drift_agent
CMD ["uvicorn", "vina_bim_shop.llm.api.drift:app", "--host", "0.0.0.0", "--port", "8080"]

FROM runtime AS coordinator
CMD ["uvicorn", "vina_bim_shop.llm.api.chat:app", "--host", "0.0.0.0", "--port", "8080"]

FROM runtime AS feast_offline_writer
CMD ["python", "scripts/feast/run_offline_writer.py"]

FROM runtime AS feast_online_writer
CMD ["python", "scripts/feast/run_online_writer.py"]
