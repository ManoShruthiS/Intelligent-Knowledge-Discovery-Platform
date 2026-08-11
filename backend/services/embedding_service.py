import logging
import warnings

# Suppress some noisy warnings from huggingface and torch
warnings.filterwarnings("ignore", category=FutureWarning)

from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

class EmbeddingService:
    def __init__(self, model_name="all-MiniLM-L6-v2"):
        self.model_name = model_name
        self.model = None
        logger.info(f"Initializing EmbeddingService with model: {self.model_name}")
        self._load_model()

    def _load_model(self):
        try:
            # This will download the model to the local cache if not already present
            self.model = SentenceTransformer(self.model_name)
            logger.info("SentenceTransformer model loaded successfully.")
        except Exception as e:
            logger.error(f"Error loading model {self.model_name}: {e}")
            raise

    def generate_embeddings(self, texts: list[str]) -> list[list[float]]:
        """
        Generate embeddings for a list of texts.
        Returns a list of lists of floats.
        """
        if not self.model:
            raise RuntimeError("Embedding model is not loaded.")
        
        if not texts:
            return []

        try:
            # model.encode returns a numpy array or torch tensor, convert to list of floats
            embeddings = self.model.encode(texts, convert_to_numpy=True)
            # numpy array to list
            return embeddings.tolist()
        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            raise

# Instantiate a global instance to be used across the application
embedding_service = EmbeddingService()
