import re
import logging

logger = logging.getLogger(__name__)

class PIIRedactorService:
    """
    Service to redact Personally Identifiable Information (PII)
    from documents and prompts before external LLM processing.
    """
    _email_pattern = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
    _phone_pattern = re.compile(r'\b(?:\+?\d{1,3}[-. ]?)?\(?\d{3}\)?[ -. ]?\d{3}[ -. ]?\d{4}\b')
    _credit_card_pattern = re.compile(r'\b(?:\d[ -]*?){13,16}\b')
    _ssn_pattern = re.compile(r'\b\d{3}[- ]?\d{2}[- ]?\d{4}\b')
    _ip_address_pattern = re.compile(r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b')

    @classmethod
    def redact_text(cls, text: str) -> str:
        if not text or not isinstance(text, str):
            return text
        
        redacted = text
        redacted = cls._email_pattern.sub('[REDACTED_EMAIL]', redacted)
        redacted = cls._phone_pattern.sub('[REDACTED_PHONE]', redacted)
        redacted = cls._credit_card_pattern.sub('[REDACTED_CC]', redacted)
        redacted = cls._ssn_pattern.sub('[REDACTED_SSN]', redacted)
        redacted = cls._ip_address_pattern.sub('[REDACTED_IP]', redacted)
        return redacted

pii_redactor_service = PIIRedactorService()
