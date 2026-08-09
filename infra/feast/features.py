"""Declarative Feast contract for the PostgreSQL-owned RAG retrieval features.

This file deliberately performs no registry apply.  Topic 10 validates its shape with
fake-backed contracts because the local host lacks the libpq runtime needed for a real
PostgreSQL/Feast registration.
"""

DOCUMENT_ENTITY = {
    "name": "document",
    "join_key": "document_id",
    "description": "Versioned e-commerce knowledge document identifier.",
}

POSTGRES_DOCUMENT_SOURCE = {
    "name": "edai2_rag_document_source",
    "table": "edai2_rag_feast_document_feature",
    "type": "postgres",
    "timestamp_field": "event_timestamp",
}

DOCUMENT_FEATURE_VIEW = {
    "name": "ecommerce_knowledge_document_features",
    "entities": ["document"],
    "source": "edai2_rag_document_source",
    "features": [
        {"name": "chunk_id", "dtype": "string"},
        {"name": "category", "dtype": "string"},
        {"name": "embedding", "dtype": "float32[]", "dimension": 384},
    ],
}

RETRIEVAL_SERVICE = {
    "name": "ecommerce_knowledge_retrieval",
    "features": [
        "ecommerce_knowledge_document_features:chunk_id",
        "ecommerce_knowledge_document_features:category",
        "ecommerce_knowledge_document_features:embedding",
    ],
    "pgvector_owner": "postgres",
}

CUSTOMER_ENTITY = {"name": "customer", "join_key": "id"}
SECTION03_TRAINING_SOURCE = {"name": "edai2_section03_training_source", "table": "edai2_section03_training_active", "type": "postgres", "timestamp_field": "event_timestamp"}
SECTION03_HEALTH_SOURCE = {"name": "edai2_section03_health_source", "table": "edai2_section03_health_active", "type": "postgres", "timestamp_field": "monitoring_date"}
SECTION03_FEATURE_SERVICE = {"name": "customer_order_drift", "features": ["ml_customer_purchase_training:label", "agg_feature_health_daily:psi_vs_baseline"]}
