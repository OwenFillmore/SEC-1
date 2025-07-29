import faiss
import pickle
import os

INDEX_PATH = "faiss_index.idx"
METADATA_PATH = "index_metadata.pkl"

def inspect_index():
    if not os.path.exists(INDEX_PATH) or not os.path.exists(METADATA_PATH):
        print("❌ No saved index or metadata found.")
        return

    index = faiss.read_index(INDEX_PATH)
    with open(METADATA_PATH, "rb") as f:
        metadata = pickle.load(f)

    print("📊 FAISS Index Inspection")
    print(f"➤ Number of vectors in index: {index.ntotal}")
    print(f"➤ Number of IDs in metadata: {len(metadata)}")
    print(f"🧾 Sample of embedded IDs: {metadata[:10]}{' ...' if len(metadata) > 10 else ''}")

if __name__ == "__main__":
    inspect_index()
