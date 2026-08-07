CREATE TABLE edai2_rag_source (
    source_sha256 CHAR(64) PRIMARY KEY,
    source_path TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE edai2_rag_document_version (
    document_id TEXT NOT NULL,
    version TEXT NOT NULL,
    source_sha256 CHAR(64) NOT NULL REFERENCES edai2_rag_source(source_sha256),
    category TEXT NOT NULL,
    effective_from TIMESTAMPTZ NOT NULL,
    effective_to TIMESTAMPTZ NULL,
    content TEXT NOT NULL,
    content_sha256 CHAR(64) NOT NULL,
    PRIMARY KEY (document_id, version),
    CHECK (effective_to IS NULL OR effective_from < effective_to),
    CHECK (content_sha256 ~ '^[0-9a-f]{64}$')
);

CREATE TABLE edai2_rag_chunk (
    chunk_id CHAR(64) PRIMARY KEY,
    document_id TEXT NOT NULL,
    version TEXT NOT NULL,
    source_sha256 CHAR(64) NOT NULL,
    category TEXT NOT NULL,
    effective_from TIMESTAMPTZ NOT NULL,
    effective_to TIMESTAMPTZ NULL,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    token_start INTEGER NOT NULL CHECK (token_start >= 0),
    token_end INTEGER NOT NULL CHECK (token_end > token_start),
    content TEXT NOT NULL,
    content_sha256 CHAR(64) NOT NULL,
    tokenizer_model TEXT NOT NULL,
    tokenizer_revision CHAR(40) NOT NULL,
    FOREIGN KEY (document_id, version)
        REFERENCES edai2_rag_document_version(document_id, version),
    CHECK (effective_to IS NULL OR effective_from < effective_to),
    CHECK (content_sha256 ~ '^[0-9a-f]{64}$')
);

CREATE TABLE edai2_rag_embedding (
    chunk_id CHAR(64) PRIMARY KEY REFERENCES edai2_rag_chunk(chunk_id),
    embedding vector(384) NOT NULL,
    embedding_sha256 CHAR(64) NOT NULL,
    embedding_model TEXT NOT NULL,
    embedding_revision CHAR(40) NOT NULL,
    CHECK (embedding_sha256 ~ '^[0-9a-f]{64}$')
);

CREATE TABLE edai2_rag_candidate_version (
    index_version TEXT PRIMARY KEY,
    candidate_sha256 CHAR(64) NOT NULL UNIQUE,
    document_count INTEGER NOT NULL CHECK (document_count = 8),
    document_version_count INTEGER NOT NULL CHECK (document_version_count = 9),
    chunk_count INTEGER NOT NULL CHECK (chunk_count > 0),
    embedding_dimension INTEGER NOT NULL CHECK (embedding_dimension = 384),
    validation_sha256 CHAR(64) NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    validated_at TIMESTAMPTZ NULL,
    CHECK (candidate_sha256 ~ '^[0-9a-f]{64}$'),
    CHECK (validation_sha256 IS NULL OR validation_sha256 ~ '^[0-9a-f]{64}$')
);

CREATE TABLE edai2_rag_candidate_chunk (
    index_version TEXT NOT NULL REFERENCES edai2_rag_candidate_version(index_version),
    chunk_id CHAR(64) NOT NULL REFERENCES edai2_rag_chunk(chunk_id),
    PRIMARY KEY (index_version, chunk_id)
);

CREATE TABLE edai2_rag_active_alias (
    alias_name TEXT PRIMARY KEY CHECK (alias_name = 'active'),
    index_version TEXT NULL REFERENCES edai2_rag_candidate_version(index_version),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO edai2_rag_active_alias (alias_name, index_version)
VALUES ('active', NULL)
ON CONFLICT (alias_name) DO NOTHING;

CREATE VIEW edai2_rag_feast_document_feature AS
SELECT
    candidate.index_version,
    chunk.chunk_id,
    chunk.document_id,
    chunk.category,
    chunk.version,
    chunk.effective_from,
    chunk.effective_to,
    embedding.embedding,
    candidate.created_at AS event_timestamp
FROM edai2_rag_active_alias active
JOIN edai2_rag_candidate_version candidate
  ON candidate.index_version = active.index_version
JOIN edai2_rag_candidate_chunk member
  ON member.index_version = candidate.index_version
JOIN edai2_rag_chunk chunk ON chunk.chunk_id = member.chunk_id
JOIN edai2_rag_embedding embedding ON embedding.chunk_id = chunk.chunk_id
WHERE active.alias_name = 'active';

CREATE INDEX edai2_rag_chunk_category_effective_btree
    ON edai2_rag_chunk USING btree (category, effective_from, effective_to);
CREATE INDEX edai2_rag_candidate_chunk_version_btree
    ON edai2_rag_candidate_chunk USING btree (index_version, chunk_id);
CREATE INDEX edai2_rag_chunk_version_ordinal_btree
    ON edai2_rag_chunk USING btree (document_id, version, ordinal);

CREATE FUNCTION edai2_rag_prevent_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'immutable EDAI2 RAG candidate rows cannot be updated or deleted';
END;
$$;

CREATE TRIGGER edai2_rag_source_prevent_mutation
BEFORE UPDATE OR DELETE ON edai2_rag_source
FOR EACH ROW EXECUTE FUNCTION edai2_rag_prevent_mutation();
CREATE TRIGGER edai2_rag_document_version_prevent_mutation
BEFORE UPDATE OR DELETE ON edai2_rag_document_version
FOR EACH ROW EXECUTE FUNCTION edai2_rag_prevent_mutation();
CREATE TRIGGER edai2_rag_chunk_prevent_mutation
BEFORE UPDATE OR DELETE ON edai2_rag_chunk
FOR EACH ROW EXECUTE FUNCTION edai2_rag_prevent_mutation();
CREATE TRIGGER edai2_rag_embedding_prevent_mutation
BEFORE UPDATE OR DELETE ON edai2_rag_embedding
FOR EACH ROW EXECUTE FUNCTION edai2_rag_prevent_mutation();
CREATE TRIGGER edai2_rag_candidate_chunk_prevent_mutation
BEFORE UPDATE OR DELETE ON edai2_rag_candidate_chunk
FOR EACH ROW EXECUTE FUNCTION edai2_rag_prevent_mutation();
