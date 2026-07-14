alter table documents
  add column if not exists source_host text,
  add column if not exists content_hash text,
  add column if not exists crawled_at timestamptz not null default now(),
  add column if not exists updated_at timestamptz not null default now(),
  add column if not exists random_key double precision not null default random();

alter table documents drop constraint if exists unique_url;

create index if not exists documents_random_key_idx on documents (random_key);
create index if not exists documents_source_host_idx on documents (source_host);

create table if not exists document_chunks (
  id bigserial primary key,
  document_id bigint not null references documents(id) on delete cascade,
  chunk_index integer not null check (chunk_index >= 0),
  content text not null,
  embedding vector(768) not null,
  embedding_model text not null,
  created_at timestamptz not null default now(),
  search_vector tsvector generated always as (
    to_tsvector('english', coalesce(content, ''))
  ) stored,
  unique (document_id, chunk_index)
);

insert into document_chunks (document_id, chunk_index, content, embedding, embedding_model)
select id, 0, coalesce(content, ''), embedding, 'legacy'
from documents
where embedding is not null
  and not exists (
    select 1 from document_chunks where document_chunks.document_id = documents.id
  );

update documents set content = null;

drop index if exists documents_embedding_hnsw_idx;
alter table documents drop column embedding;

create index if not exists document_chunks_embedding_hnsw_idx
  on document_chunks using hnsw (embedding vector_cosine_ops);

create index if not exists document_chunks_search_vector_gin_idx
  on document_chunks using gin (search_vector);

create index if not exists document_chunks_document_id_idx
  on document_chunks (document_id);

drop function if exists match_documents(vector(768), text, float, int);

create or replace function match_documents (
  query_embedding vector(768),
  query_text text,
  match_threshold float,
  result_offset int,
  result_limit int,
  vector_candidate_count int,
  text_candidate_count int
)
returns table (
  id bigint,
  url text,
  title text,
  description text,
  snippet text,
  similarity float
)
language sql stable
as $$
  with text_query as materialized (
    select websearch_to_tsquery('english', coalesce(query_text, '')) as value
  ),
  vector_chunks as materialized (
    select
      chunks.id as chunk_id,
      chunks.document_id,
      case
        when chunks.embedding <=> query_embedding = 'NaN'::float8 then 0
        else 1 - (chunks.embedding <=> query_embedding)
      end as vector_similarity
    from document_chunks chunks
    order by chunks.embedding <=> query_embedding
    limit greatest(vector_candidate_count, 1)
  ),
  vector_documents as materialized (
    select distinct on (document_id)
      document_id,
      chunk_id,
      vector_similarity
    from vector_chunks
    where vector_similarity > match_threshold
    order by document_id, vector_similarity desc, chunk_id
  ),
  text_chunks as materialized (
    select
      chunks.id as chunk_id,
      chunks.document_id,
      ts_rank_cd(chunks.search_vector, text_query.value, 32) as text_rank
    from document_chunks chunks
    cross join text_query
    where numnode(text_query.value) > 0
      and chunks.search_vector @@ text_query.value
    order by text_rank desc, chunks.id
    limit greatest(text_candidate_count, 1)
  ),
  text_chunk_documents as materialized (
    select distinct on (document_id)
      document_id,
      chunk_id,
      text_rank
    from text_chunks
    order by document_id, text_rank desc, chunk_id
  ),
  text_documents as materialized (
    select
      documents.id as document_id,
      ts_rank_cd(documents.search_vector, text_query.value, 32) as text_rank
    from documents
    cross join text_query
    where numnode(text_query.value) > 0
      and documents.search_vector @@ text_query.value
    order by text_rank desc, documents.id
    limit greatest(text_candidate_count, 1)
  ),
  candidate_documents as materialized (
    select document_id from vector_documents
    union
    select document_id from text_chunk_documents
    union
    select document_id from text_documents
  ),
  scored as materialized (
    select
      documents.id,
      documents.url,
      documents.title,
      documents.description,
      left(coalesce(vector_chunk.content, text_chunk.content, first_chunk.content, ''), 500) as snippet,
      (
        0.7 * greatest(coalesce(vector_documents.vector_similarity, 0), 0)
        + 0.3 * greatest(
          coalesce(text_chunk_documents.text_rank, 0),
          coalesce(text_documents.text_rank, 0)
        )
      )::float as similarity
    from candidate_documents
    join documents on documents.id = candidate_documents.document_id
    left join vector_documents on vector_documents.document_id = documents.id
    left join document_chunks vector_chunk on vector_chunk.id = vector_documents.chunk_id
    left join text_chunk_documents on text_chunk_documents.document_id = documents.id
    left join document_chunks text_chunk on text_chunk.id = text_chunk_documents.chunk_id
    left join text_documents on text_documents.document_id = documents.id
    left join lateral (
      select content
      from document_chunks
      where document_id = documents.id
      order by chunk_index
      limit 1
    ) first_chunk on true
  )
  select scored.id, scored.url, scored.title, scored.description, scored.snippet, scored.similarity
  from scored
  order by scored.similarity desc, scored.id
  offset greatest(result_offset, 0)
  limit greatest(result_limit, 1);
$$;

create or replace function random_documents (result_limit int)
returns table (
  id bigint,
  url text,
  title text,
  description text
)
language sql volatile
as $$
  with pivot as materialized (
    select random() as value
  ),
  after_pivot as materialized (
    select documents.id, documents.url, documents.title, documents.description, documents.random_key
    from documents
    cross join pivot
    where documents.url is not null
      and documents.url <> ''
      and documents.random_key >= pivot.value
    order by documents.random_key
    limit greatest(result_limit, 1)
  ),
  before_pivot as materialized (
    select documents.id, documents.url, documents.title, documents.description, documents.random_key
    from documents
    cross join pivot
    where documents.url is not null
      and documents.url <> ''
      and documents.random_key < pivot.value
    order by documents.random_key
    limit greatest(result_limit, 1)
  )
  select candidates.id, candidates.url, candidates.title, candidates.description
  from (
    select * from after_pivot
    union all
    select * from before_pivot
  ) candidates
  limit greatest(result_limit, 1);
$$;

---- create above / drop below ----
drop function if exists random_documents(int);
drop function if exists match_documents(vector(768), text, float, int, int, int, int);

drop index if exists document_chunks_document_id_idx;
drop index if exists document_chunks_search_vector_gin_idx;
drop index if exists document_chunks_embedding_hnsw_idx;

alter table documents add column embedding vector(768);

update documents
set embedding = chunks.embedding
from document_chunks chunks
where chunks.document_id = documents.id
  and chunks.chunk_index = 0
  and documents.embedding is null;

update documents
set content = reconstructed.content
from (
  select document_id, string_agg(content, ' ' order by chunk_index) as content
  from document_chunks
  group by document_id
) reconstructed
where reconstructed.document_id = documents.id
  and documents.content is null;

drop table if exists document_chunks;

alter table documents alter column embedding set not null;
alter table documents add constraint unique_url unique (url);
create index if not exists documents_embedding_hnsw_idx
  on documents using hnsw (embedding vector_cosine_ops);

drop index if exists documents_source_host_idx;
drop index if exists documents_random_key_idx;

alter table documents
  drop column if exists random_key,
  drop column if exists updated_at,
  drop column if exists crawled_at,
  drop column if exists content_hash,
  drop column if exists source_host;

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
