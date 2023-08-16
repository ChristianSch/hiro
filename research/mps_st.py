

import psycopg
from pgvector.psycopg import register_vector

from sentence_transformers import SentenceTransformer
import requests
from io import StringIO
import pandas as pd
from tqdm import tqdm


"""
Postgres setup:

0. as superuser:
create extension vector;

1.
create table documents (
  id bigserial primary key,
  content text,
  embedding vector(768)
);

2.
create or replace function match_documents (
  query_embedding vector(768),
  match_threshold float,
  match_count int
)
returns table (
  id bigint,
  content text,
  similarity float
)
language sql stable
as $$
  select
    documents.id,
    documents.content,
    1 - (documents.embedding <=> query_embedding) as similarity
  from documents
  where 1 - (documents.embedding <=> query_embedding) > match_threshold
  order by similarity desc
  limit match_count;
$$;

3.
create index on documents using ivfflat (embedding vector_cosine_ops)
with
  (lists = 100);
"""

# source of some of the stuff: https://supabase.com/blog/openai-embeddings-postgres-vector

def load_data():
    res = requests.get(
        'https://raw.githubusercontent.com/brmson/dataset-sts/master/data/sts/sick2014/SICK_train.txt')
    # create dataframe
    data = pd.read_csv(StringIO(res.text), sep='\t')

    # Remove Duplicates
    data.drop_duplicates(subset="sentence_A", inplace=True)
    return data


def load_embedding_model():
    # using apple metal
    return SentenceTransformer('BAAI/bge-base-en', device='mps')


# connect to database
with psycopg.connect("dbname=hiro user=hiro password=hiro host=localhost port=5432") as conn:
    register_vector(conn)

    dataset = load_data()
    model = load_embedding_model()

    # insert data
    for i, row in tqdm(dataset.iterrows(), total=dataset.shape[0]):
        content = row['sentence_A']
        embedding = model.encode(content)
        conn.execute(
            'INSERT INTO documents (content, embedding) VALUES (%s, %s)', (content, embedding,))

    conn.commit()

    # search
    search = model.encode("ball")
    print(conn.execute('SELECT match_documents(%s, 0.78, 10)', (search,)).fetchall())
