-- 重建 embeddings 向量表
-- 执行前请确认：会删除所有向量数据，需通过 reindex-all 重新索引
BEGIN;
DROP TABLE IF EXISTS embeddings CASCADE;
CREATE TABLE embeddings (
    id SERIAL PRIMARY KEY,
    document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
    chunk_text TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    embedding vector(512),
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX embeddings_vector_idx ON embeddings
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);
CREATE INDEX idx_embeddings_document_id ON embeddings(document_id);
COMMIT;
