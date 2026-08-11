import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class AIConfig:
    def __init__(self):
        self._gemini_api_key = os.getenv("GEMINI_API_KEY")
    
    @property
    def is_gemini_configured(self) -> bool:
        """Returns True if the Gemini API key is configured."""
        return bool(self._gemini_api_key)
        
    def get_gemini_api_key(self) -> str:
        """
        Retrieves the Gemini API key.
        Raises a configuration error if it is missing.
        """
        if not self._gemini_api_key:
            raise ValueError("GEMINI_API_KEY is not configured in the environment.")
        return self._gemini_api_key

# Singleton instance to be used across the backend
ai_config = AIConfig()
