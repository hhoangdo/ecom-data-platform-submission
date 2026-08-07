FROM vina-bim-shop/spark:4.0.0-iceberg-1.10.1 AS spark-runtime

FROM apache/airflow:2.10.5-python3.12

ENV SPARK_HOME=/opt/spark \
    JAVA_HOME=/opt/java/openjdk \
    PATH=/opt/spark/bin:/opt/spark/sbin:/opt/java/openjdk/bin:${PATH}

USER root

COPY --from=spark-runtime /opt/spark /opt/spark
COPY --from=spark-runtime /opt/java/openjdk /opt/java/openjdk

RUN apt-get update \
  && apt-get install -y --no-install-recommends docker.io docker-compose-plugin curl \
  && curl -fsSL https://dl.min.io/client/mc/release/linux-amd64/mc -o /usr/local/bin/mc \
  && chmod +x /usr/local/bin/mc \
  && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md /opt/vina-bim-shop/
COPY src /opt/vina-bim-shop/src

USER airflow

RUN python -m pip install --no-cache-dir /opt/vina-bim-shop \
  && python -m pip install --no-cache-dir \
    "numpy==1.26.4" \
    "scipy==1.14.1" \
    "great-expectations==1.17.2" \
  && python -m pip install --no-cache-dir \
    "acryl-datahub[datahub-rest,kafka,trino,dbt]==1.6.0" \
    "acryl-datahub-airflow-plugin==1.6.0"
