create extension if not exists vector;

create table if not exists documents (
  id bigserial primary key,
  url text unique not null,
  title text,
  content text,
  description text,
  embedding vector(768) not null,
  constraint unique_url unique (url)
);

create or replace function match_documents (
  query_embedding vector(768),
  match_threshold float,
  match_count int
)
returns table (
  id bigint,
  url text,
  title text,
  content text,
  description text,
  similarity float
)
language sql stable
as $$
  select
    documents.id,
    documents.url,
    documents.title,
    documents.content,
    documents.description,
    1 - (documents.embedding <=> query_embedding) as similarity
  from documents
  where 1 - (documents.embedding <=> query_embedding) > match_threshold
  order by similarity desc
  limit match_count;
$$;

create index if not exists documents_embedding_hnsw_idx
  on documents using hnsw (embedding vector_cosine_ops);

---- create above / drop below ----
drop index if exists documents_embedding_hnsw_idx;
drop function if exists match_documents(vector(768), float, int);
drop table if exists documents;
drop extension if exists vector;
