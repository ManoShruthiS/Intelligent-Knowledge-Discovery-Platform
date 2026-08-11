from sentence_transformers import SentenceTransformer
from typing import List

class EmbeddingService:
    """
    Singleton service for generating embeddings using a local HuggingFace model.
    The model is loaded once upon first initialization.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(EmbeddingService, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        # We use a small, fast, CPU-friendly model
        model_name = "sentence-transformers/all-MiniLM-L6-v2"
        # Loading happens here, only once
        self.model = SentenceTransformer(model_name)
        
    def embed_text(self, text: str) -> List[float]:
        """Generate embedding for a single string."""
        if not text:
            raise ValueError("Cannot embed empty string")
        # Ensure we return standard python floats
        embedding = self.model.encode(text, convert_to_numpy=True)
        return embedding.tolist()

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a list of strings."""
        if not texts:
            return []
        embeddings = self.model.encode(texts, convert_to_numpy=True)
        return embeddings.tolist()
