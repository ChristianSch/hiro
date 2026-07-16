drop index if exists document_chunks_embedding_hnsw_idx;

alter table document_chunks
  alter column embedding type halfvec(768)
  using embedding::halfvec(768);

create index document_chunks_embedding_hnsw_idx
  on document_chunks using hnsw (embedding halfvec_cosine_ops);

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
        when chunks.embedding <=> query_embedding::halfvec(768) = 'NaN'::float8 then 0
        else 1 - (chunks.embedding <=> query_embedding::halfvec(768))
      end as vector_similarity
    from document_chunks chunks
    order by chunks.embedding <=> query_embedding::halfvec(768)
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

---- create above / drop below ----

-- This storage migration is intentionally forward-only. Converting the corpus
-- back to float32 would rebuild the full vector column and HNSW index.
do $$
begin
  raise exception '004_halfvec_embeddings cannot be rolled back';
end
$$;
