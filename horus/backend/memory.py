import chromadb
from chromadb.utils import embedding_functions

COLLECTION_NAME = "horus_memory"


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

    def store_fact(self, fact: str):
        """Explicitly store a user-stated fact."""
        self._id_counter += 1
        self.collection.add(
            documents=[f"[Explicit memory] {fact}"],
            ids=[f"mem_{self._id_counter}"],
        )

    def retrieve(self, query: str, n_results: int = 3) -> list[str]:
        """Retrieve the most relevant past memories for a query."""
        count = self.collection.count()
        if count == 0:
            return []
        results = self.collection.query(
            query_texts=[query],
            n_results=min(n_results, count),
        )
        return results["documents"][0] if results["documents"] else []

    def get_all(self) -> list[str]:
        """Return all stored memories (for the MemoryPanel)."""
        results = self.collection.get()
        return results["documents"] if results["documents"] else []

    def clear(self):
        self.client.delete_collection(COLLECTION_NAME)
        self.collection = self.client.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=self.ef,
        )
        self._id_counter = 0
