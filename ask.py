# ask.py
import openai
import faiss
import numpy as np
import sqlite3
import pickle
import os

from dotenv import load_dotenv
load_dotenv()

DB_PATH = "sec_articles.db"
INDEX_PATH = "faiss_index.idx"
METADATA_PATH = "index_metadata.pkl"

openai.api_key = os.getenv("OPENAI_API_KEY")
EMBED_MODEL = "text-embedding-ada-002"
GPT_MODEL = "gpt-4"
TOP_K = 3

def get_embedding(text):
    response = openai.Embedding.create(
        input=[text],
        model=EMBED_MODEL
    )
    return response['data'][0]['embedding']

def search_index(query_embedding):
    index = faiss.read_index(INDEX_PATH)
    with open(METADATA_PATH, "rb") as f:
        metadata = pickle.load(f)
    D, I = index.search(np.array([query_embedding]).astype("float32"), TOP_K)
    return [metadata[i] for i in I[0]]

def fetch_articles(ids):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    placeholders = ','.join(['?'] * len(ids))
    c.execute(f"SELECT title, url, summary FROM articles WHERE id IN ({placeholders})", ids)
    rows = c.fetchall()
    conn.close()
    return rows

def build_prompt(question, articles):
    content = "\n\n".join(
        f"Title: {title}\nURL: {url}\nSummary: {summary}"
        for title, url, summary in articles
    )
    return f"""You are a compliance assistant. Use the documents below to answer the question.

Question: {question}

Documents:
{content}

Answer:"""

def ask_question(question):
    query_embedding = get_embedding(question)
    top_ids = search_index(query_embedding)
    articles = fetch_articles(top_ids)
    prompt = build_prompt(question, articles)

    response = openai.ChatCompletion.create(
        model=GPT_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4
    )
    print(response['choices'][0]['message']['content'])

if __name__ == "__main__":
    user_q = input("Ask a question: ")
    ask_question(user_q)
# This script allows you to ask questions about SEC articles.
# It retrieves relevant articles from a FAISS index and uses OpenAI's GPT model to generate                 