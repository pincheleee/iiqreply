from typing import Dict, List, Optional, Any
import os
import logging
from langchain.llms import Ollama
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from langchain_openai import ChatOpenAI

logger = logging.getLogger("iiqreply.ticket_categorizer")

# Valid categories for validation
VALID_CATEGORIES = {
    "Hardware Issue",
    "Software Issue",
    "Network Problem",
    "Account Access",
    "Password Reset",
    "Email Problem",
    "Printer Issue",
    "Application Error",
    "Data Recovery",
    "Security Concern",
    "Other",
}


class TicketCategorizer:
    """
    Analyzes and categorizes IT support tickets using LLM.
    """

    def __init__(self, provider: str = None, model_name: str = None):
        """
        Initialize the ticket categorizer.

        Args:
            provider: LLM provider to use ("ollama" or "openai"), defaults to env var
            model_name: The name of the model to use, defaults to env var
        """
        # Get provider and model from env vars if not specified
        self.provider = provider or os.getenv("LLM_PROVIDER", "ollama")

        # Set up the appropriate LLM based on provider
        if self.provider.lower() == "openai":
            openai_api_key = os.getenv("OPENAI_API_KEY")
            self.model_name = model_name or os.getenv("OPENAI_MODEL", "gpt-4")

            if not openai_api_key:
                raise ValueError("OpenAI API key not found. Set OPENAI_API_KEY in environment.")

            self.llm = ChatOpenAI(
                model=self.model_name,
                openai_api_key=openai_api_key,
                temperature=0.2
            )
        else:  # Default to ollama
            self.model_name = model_name or os.getenv("OLLAMA_MODEL", "llama3")
            ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
            self.llm = Ollama(model=self.model_name, base_url=ollama_host)

        # Define category template
        self.categorization_template = PromptTemplate(
            input_variables=["title", "description"],
            template="""Categorize this IT support ticket into one of the following categories:
            - Hardware Issue
            - Software Issue
            - Network Problem
            - Account Access
            - Password Reset
            - Email Problem
            - Printer Issue
            - Application Error
            - Data Recovery
            - Security Concern
            - Other (specify)

            Title: {title}
            Description: {description}

            Provide your answer as a single category name from the list above.
            If it's "Other", include a brief suggested category in parentheses.
            """
        )

        # Initialize categorization chain
        self.categorization_chain = LLMChain(
            llm=self.llm,
            prompt=self.categorization_template
        )

        # Known issue patterns for fast categorization without LLM
        # Each entry maps a keyword pattern to (category, base_confidence).
        # Confidence is boosted when multiple patterns or both title+description match.
        self.known_patterns = {
            "password reset": ("Password Reset", 0.92),
            "forgot password": ("Password Reset", 0.90),
            "change password": ("Password Reset", 0.88),
            "can't login": ("Account Access", 0.90),
            "cannot login": ("Account Access", 0.90),
            "locked out": ("Account Access", 0.88),
            "account locked": ("Account Access", 0.90),
            "printer not working": ("Printer Issue", 0.92),
            "printer jam": ("Printer Issue", 0.90),
            "print queue": ("Printer Issue", 0.85),
            "wifi": ("Network Problem", 0.85),
            "internet down": ("Network Problem", 0.90),
            "no internet": ("Network Problem", 0.90),
            "vpn": ("Network Problem", 0.82),
            "outlook": ("Email Problem", 0.85),
            "email not working": ("Email Problem", 0.90),
            "can't send email": ("Email Problem", 0.90),
            "blue screen": ("Hardware Issue", 0.85),
            "bsod": ("Hardware Issue", 0.88),
            "broken screen": ("Hardware Issue", 0.92),
            "virus": ("Security Concern", 0.88),
            "malware": ("Security Concern", 0.90),
            "phishing": ("Security Concern", 0.88),
        }

    def switch_provider(self, provider: str, api_key: Optional[str] = None, model_name: Optional[str] = None):
        """
        Switch the LLM provider at runtime.

        Args:
            provider: The provider to switch to ("ollama" or "openai")
            api_key: API key for OpenAI (required if switching to "openai")
            model_name: Model name to use
        """
        if provider.lower() == "openai":
            # Use provided API key or fall back to env var
            openai_api_key = api_key or os.getenv("OPENAI_API_KEY")
            model = model_name or os.getenv("OPENAI_MODEL", "gpt-4")

            if not openai_api_key:
                raise ValueError("OpenAI API key not provided and not found in environment")

            self.llm = ChatOpenAI(
                model=model,
                openai_api_key=openai_api_key,
                temperature=0.2
            )
        else:  # Switch to ollama
            model = model_name or os.getenv("OLLAMA_MODEL", "llama3")
            ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
            self.llm = Ollama(model=model, base_url=ollama_host)

        # Update chain with new LLM
        self.categorization_chain = LLMChain(llm=self.llm, prompt=self.categorization_template)

        # Update internal state
        self.provider = provider
        self.model_name = model

        logger.info("Switched provider to %s, model=%s", provider, model)
        return {"status": "success", "provider": provider, "model": model}

    def _calculate_pattern_confidence(self, title: str, description: str) -> Optional[Dict[str, Any]]:
        """
        Check known patterns and calculate a real confidence score based on:
        - Number of matching patterns
        - Whether match is in title (higher weight) vs description only
        - Base confidence of the matching pattern

        Returns:
            Category result dict, or None if no patterns match
        """
        title_lower = (title or "").lower()
        description_lower = (description or "").lower()
        combined = f"{title_lower} {description_lower}"

        matches = []
        for pattern, (category, base_conf) in self.known_patterns.items():
            if pattern in combined:
                # Boost if pattern appears in the title (more specific)
                in_title = pattern in title_lower
                boost = 0.05 if in_title else 0.0
                matches.append((category, base_conf + boost))

        if not matches:
            return None

        # Group by category and pick the one with most/strongest matches
        category_scores: Dict[str, list] = {}
        for cat, score in matches:
            category_scores.setdefault(cat, []).append(score)

        # Pick category with highest average score, break ties by count
        best_category = None
        best_avg = 0.0
        for cat, scores in category_scores.items():
            avg = sum(scores) / len(scores)
            # Bonus for multiple pattern matches (up to +0.05)
            multi_bonus = min(0.05, (len(scores) - 1) * 0.02)
            avg += multi_bonus
            if avg > best_avg:
                best_avg = avg
                best_category = cat

        # Cap at 0.99
        final_confidence = min(0.99, round(best_avg, 2))

        return {
            "category": best_category,
            "confidence": final_confidence,
            "method": "pattern_matching",
        }

    def _validate_llm_category(self, raw_category: str) -> tuple:
        """
        Validate and normalize the LLM-returned category against known categories.
        Returns (normalized_category, confidence_modifier).
        """
        stripped = raw_category.strip().strip('"').strip("'")

        # Exact match
        if stripped in VALID_CATEGORIES:
            return stripped, 0.0

        # Case-insensitive match
        for valid in VALID_CATEGORIES:
            if stripped.lower() == valid.lower():
                return valid, 0.0

        # Substring match (e.g. LLM returned "It's a Network Problem")
        for valid in VALID_CATEGORIES:
            if valid.lower() in stripped.lower():
                return valid, -0.05

        # No match -- treat as Other
        return f"Other ({stripped})", -0.10

    def categorize(self, title: Optional[str], description: str) -> Dict[str, Any]:
        """
        Categorize a ticket based on its title and description.

        Args:
            title: The ticket title
            description: The ticket description

        Returns:
            Dict containing the category and confidence score
        """
        title = title or ""

        # First check for known patterns for efficiency
        pattern_result = self._calculate_pattern_confidence(title, description)
        if pattern_result:
            logger.info("Pattern match: category=%s confidence=%.2f", pattern_result["category"], pattern_result["confidence"])
            return pattern_result

        # If no pattern match, use LLM for categorization
        try:
            logger.debug("Using LLM for categorization: title=%s", title[:80])
            llm_category = self.categorization_chain.run(
                title=title,
                description=description
            ).strip()

            # Validate and score the LLM result
            validated_category, confidence_mod = self._validate_llm_category(llm_category)

            # Base LLM confidence: 0.80, modified by validation result
            confidence = round(max(0.50, min(0.95, 0.80 + confidence_mod)), 2)

            logger.info("LLM categorized: raw=%s validated=%s confidence=%.2f", llm_category, validated_category, confidence)
            return {
                "category": validated_category,
                "confidence": confidence,
                "method": "llm_analysis"
            }

        except Exception as e:
            logger.exception("Error during LLM categorization")
            # Fallback for any errors
            return {
                "category": "Other",
                "confidence": 0.0,
                "method": "fallback",
                "error": str(e)
            }
