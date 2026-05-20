alter table documents
  add column if not exists search_vector tsvector generated always as (
    setweight(to_tsvector('english', coalesce(title, '')), 'A') ||
    setweight(to_tsvector('english', coalesce(description, '')), 'B') ||
    setweight(to_tsvector('english', coalesce(content, '')), 'C')
  ) stored;

create index if not exists documents_search_vector_gin_idx
  on documents using gin (search_vector);

create or replace function match_documents (
  query_embedding vector(768),
  query_text text,
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
  with query as (
    select websearch_to_tsquery('english', coalesce(query_text, '')) as text_query
  ), scored as (
    select
      documents.id,
      documents.url,
      documents.title,
      documents.content,
      documents.description,
      case
        when vector_distance = 'NaN'::float8 then 0
        else 1 - vector_distance
      end as vector_similarity,
      case
        when numnode(query.text_query) > 0 and documents.search_vector @@ query.text_query
        then ts_rank_cd(documents.search_vector, query.text_query, 32)
        else 0
      end as text_rank
    from documents
    cross join query
    cross join lateral (
      select documents.embedding <=> query_embedding as vector_distance
    ) distance
    where
      case
        when vector_distance = 'NaN'::float8 then 0
        else 1 - vector_distance
      end > match_threshold
      or (
        numnode(query.text_query) > 0
        and documents.search_vector @@ query.text_query
      )
  )
  select
    scored.id,
    scored.url,
    scored.title,
    scored.content,
    scored.description,
    (0.7 * scored.vector_similarity + 0.3 * scored.text_rank) as similarity
  from scored
  order by similarity desc
  limit match_count;
$$;

---- create above / drop below ----
drop function if exists match_documents(vector(768), text, float, int);
drop index if exists documents_search_vector_gin_idx;
alter table documents drop column if exists search_vector;

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
