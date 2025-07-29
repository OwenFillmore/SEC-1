import sqlite3
import faiss
import numpy as np
import os
import pickle
import sys
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI()

DB_PATH = "sec_articles.db"
INDEX_PATH = "faiss_index.idx"
METADATA_PATH = "index_metadata.pkl"

EMBED_MODEL = "text-embedding-3-small"
GPT_MODEL = "gpt-4o-mini"
DIM = 1536
BATCH_SIZE = 5  # adjust as needed based on speed/cost preferences


def get_embedding(text):
    response = client.embeddings.create(
        input=[text],
        model=EMBED_MODEL
    )
    return response.data[0].embedding


def summarize(text):
    prompt = f"Summarize this SEC document in plain English:\n\n{text[:3000]}"
    response = client.chat.completions.create(
        model=GPT_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4
    )
    return response.choices[0].message.content


def ensure_summary_column():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(sec_articles);")
    columns = [row[1] for row in cur.fetchall()]
    if 'summary' not in columns:
        cur.execute("ALTER TABLE sec_articles ADD COLUMN summary TEXT;")
        conn.commit()
    conn.close()


def load_existing_index():
    if os.path.exists(INDEX_PATH) and os.path.exists(METADATA_PATH):
        print("🔁 Resuming from existing index...")
        index = faiss.read_index(INDEX_PATH)
        with open(METADATA_PATH, "rb") as f:
            metadata = pickle.load(f)
    else:
        print("🆕 Starting new index.")
        index = faiss.IndexFlatL2(DIM)
        metadata = []
    return index, metadata


def embed_and_index(limit=None):
    ensure_summary_column()
    index, metadata = load_existing_index()
    already_indexed_ids = set(metadata)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    query = "SELECT id, clean_text FROM sec_articles WHERE summary IS NULL"
    if limit:
        query += f" LIMIT {limit}"
    cur.execute(query)
    rows = cur.fetchall()

    new_metadata = []
    vectors = []

    for i, (row_id, text) in enumerate(rows):
        if row_id in already_indexed_ids:
            continue
        if not text or not text.strip():
            print(f"⚠️ Skipping ID {row_id}: Empty text")
            continue

        try:
            summary = summarize(text)
            vector = get_embedding(summary)

            vectors.append(np.array(vector).astype("float32"))
            new_metadata.append(row_id)

            cur.execute("UPDATE sec_articles SET summary = ? WHERE id = ?", (summary, row_id))
            conn.commit()

            print(f"✅ Indexed ID {row_id}")
        except Exception as e:
            print(f"❌ Error on ID {row_id}: {e}")
            continue

        # Batch write to index every BATCH_SIZE documents
        if len(vectors) >= BATCH_SIZE:
            index.add(np.vstack(vectors))
            vectors.clear()

    # Final flush for remaining
    if vectors:
        index.add(np.vstack(vectors))

    conn.close()

    # Save updated index and metadata
    if new_metadata:
        full_metadata = metadata + new_metadata
        faiss.write_index(index, INDEX_PATH)
        with open(METADATA_PATH, "wb") as f:
            pickle.dump(full_metadata, f)
        print(f"\n✅ Completed embedding and indexing {len(new_metadata)} new documents.")
    else:
        print("\n⚠️ No new documents were indexed.")


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else "all"
    if arg == "1":
        embed_and_index(limit=1)
    elif arg == "2":
        embed_and_index(limit=2)
    else:
        embed_and_index()
