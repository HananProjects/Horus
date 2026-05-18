import chromadb
from chromadb.utils import embedding_functions

COLLECTION_NAME = "horus_memory"
RELEVANCE_THRESHOLD = 0.55  # cosine distance — lower = more similar; skip weak matches
MAX_MEMORIES = 2000          # prune oldest entries beyond this to prevent bloat


class Memory:
    def __init__(self):
        self.client = chromadb.PersistentClient(path="./chroma_data")
        self.ef = embedding_functions.DefaultEmbeddingFunction()
        self.collection = self.client.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=self.ef,
        )
        self._id_counter = self.collection.count()

    def store(self, user_text: str, assistant_text: str):
        doc = f"User: {user_text}\nHorus: {assistant_text}"
        self._id_counter += 1
        self.collection.add(
            documents=[doc],
            ids=[f"mem_{self._id_counter}"],
        )
        self._prune_if_needed()

    def store_fact(self, fact: str):
        self._id_counter += 1
        self.collection.add(
            documents=[f"[Explicit memory] {fact}"],
            ids=[f"mem_{self._id_counter}"],
        )

    def retrieve(self, query: str, n_results: int = 5) -> list[str]:
        count = self.collection.count()
        if count == 0:
            return []
        results = self.collection.query(
            query_texts=[query],
            n_results=min(n_results, count),
            include=["documents", "distances"],
        )
        docs = results["documents"][0] if results["documents"] else []
        dists = results["distances"][0] if results["distances"] else []
        # Filter out weakly-related memories
        return [doc for doc, dist in zip(docs, dists) if dist < RELEVANCE_THRESHOLD]

    def get_all(self) -> list[str]:
        results = self.collection.get()
        return results["documents"] if results["documents"] else []

    def count(self) -> int:
        return self.collection.count()

    def clear(self):
        self.client.delete_collection(COLLECTION_NAME)
        self.collection = self.client.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=self.ef,
        )
        self._id_counter = 0

    def _prune_if_needed(self):
        count = self.collection.count()
        if count <= MAX_MEMORIES:
            return
        # Delete the oldest 200 entries to make room
        results = self.collection.get(limit=200)
        if results["ids"]:
            self.collection.delete(ids=results["ids"])
