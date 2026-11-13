-- Run once on the Render PostgreSQL database before indexing documents.
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS semantic_search_documents (
    document_id  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    entity_type  text NOT NULL,
    entity_id    bigint NOT NULL,
    title        text NOT NULL,
    content      text NOT NULL,
    source_code  varchar(20),
    metadata     jsonb NOT NULL DEFAULT '{}'::jsonb,
    embedding    vector(768) NOT NULL,
    indexed_at   timestamptz NOT NULL DEFAULT now(),
    UNIQUE (entity_type, entity_id)
);

CREATE INDEX IF NOT EXISTS idx_semantic_search_documents_embedding
    ON semantic_search_documents USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS idx_semantic_search_documents_source
    ON semantic_search_documents (source_code);
