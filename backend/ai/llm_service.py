import os
import logging
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

class LLMService:
    """
    Service for interacting with Google Gemini API using google-genai SDK.
    """
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        
        if not self.api_key:
            logger.warning("GEMINI_API_KEY is not set in environment variables.")
            self.client = None
        else:
            try:
                # Initialize the new google-genai client
                self.client = genai.Client(api_key=self.api_key)
                logger.info(f"Initialized Gemini client with model: {self.model_name}")
            except Exception as e:
                logger.error(f"Failed to initialize Gemini client: {e}")
                self.client = None

    def generate_response(self, prompt: str) -> str:
        """
        Sends a prompt to Gemini and returns the text response.
        Handles API errors, rate limits, and configuration issues.
        """
        if not self.client:
            raise ValueError("Gemini API key is not configured or client failed to initialize.")
            
        if not prompt or not prompt.strip():
            raise ValueError("Prompt cannot be empty.")
            
        try:
            # We configure safety settings or generation config if needed, but defaults are usually fine.
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )
            return response.text
        except Exception as e:
            # Log the specific error for debugging but raise a clean error for the frontend
            error_str = str(e).lower()
            logger.error(f"Gemini API Error: {e}")
            if "429" in error_str or "quota" in error_str or "rate limit" in error_str:
                raise RuntimeError("The AI service is currently experiencing high traffic (rate limited). Please try again later.")
            elif "timeout" in error_str:
                raise RuntimeError("The AI service timed out. Please try again.")
            else:
                raise RuntimeError("Failed to generate a response from the AI service.")

# Expose a singleton instance for the app
llm_service = LLMService()
