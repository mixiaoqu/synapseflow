-- 将 embeddings 表从 vector(1536) 迁移到 vector(512)（BGE 中文嵌入）
-- 仅对已存在 vector(1536) 的数据库执行
-- 执行前请备份数据
BEGIN;
-- 清空旧向量（维度不兼容无法直接 ALTER）
TRUNCATE embeddings;
ALTER TABLE embeddings ALTER COLUMN embedding TYPE vector(512);
COMMIT;
