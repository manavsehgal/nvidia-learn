-- pgvector schema for the 1024-d Nemotron Retriever corpus.
-- Article #2 keeps the embedder dim-agnostic thanks to Matryoshka truncation;
-- article #3 commits to 1024-d here because pgvector columns are typed at
-- CREATE TABLE time. 1024-d gives a ~50% storage cut vs native 2048 at the
-- cost of ~4 recall points per the model card — the quality/storage sweet spot
-- for a personal corpus.

CREATE EXTENSION IF NOT EXISTS vector;

DROP TABLE IF EXISTS chunks;

CREATE TABLE chunks (
    id         BIGINT PRIMARY KEY,
    label      TEXT   NOT NULL,
    text       TEXT   NOT NULL,
    embedding  vector(1024) NOT NULL
);

CREATE INDEX chunks_label_idx ON chunks (label);
