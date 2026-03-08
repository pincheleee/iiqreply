import os
import re
import json
import logging
from typing import Dict, List, Optional, Any
import ollama
from langchain.llms import Ollama
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain

# Add OpenAI imports
from langchain_openai import ChatOpenAI

logger = logging.getLogger("iiqreply.llm_manager")


class LLMManager:
    """
    Manages interactions with LLMs using either Ollama (local) or OpenAI (cloud).
    Handles response generation and ticket analysis for auto-resolution.
    """

    def __init__(self, provider: str = None, model_name: str = None):
        """
        Initialize the LLM Manager.

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

        # Define common templates
        self.it_chat_template = PromptTemplate(
            input_variables=["question"],
            template="""You are an IT support assistant. Please answer the following question
            professionally and concisely:

            {question}

            If you don't know the answer, say so and suggest escalating to a human IT specialist.
            """
        )

        self.ticket_analysis_template = PromptTemplate(
            input_variables=["title", "description"],
            template="""Analyze this IT support ticket and determine if it can be automatically resolved.

            Title: {title}
            Description: {description}

            1. Can this ticket be automatically resolved? (Yes/No)
            2. If yes, provide the exact steps to resolve it.
            3. If no, explain why human intervention is needed.

            You MUST respond with valid JSON only, no other text. Use this exact format:
            {{"can_auto_resolve": true, "resolution": "steps here", "reason": ""}}
            or
            {{"can_auto_resolve": false, "resolution": "", "reason": "explanation here"}}
            """
        )

        # Initialize chains
        self.chat_chain = LLMChain(llm=self.llm, prompt=self.it_chat_template)
        self.analysis_chain = LLMChain(llm=self.llm, prompt=self.ticket_analysis_template)

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

        # Update chains with new LLM
        self.chat_chain = LLMChain(llm=self.llm, prompt=self.it_chat_template)
        self.analysis_chain = LLMChain(llm=self.llm, prompt=self.ticket_analysis_template)

        # Update internal state
        self.provider = provider
        self.model_name = model

        logger.info("Switched provider to %s, model=%s", provider, model)
        return {"status": "success", "provider": provider, "model": model}

    def generate_response(self, message: str, context: Optional[Dict] = None) -> str:
        """
        Generate a response to the user's IT question.

        Args:
            message: The user's question or message
            context: Additional context about the user or their system

        Returns:
            The LLM's response
        """
        # Add context to the prompt if available
        if context:
            enhanced_message = f"{message}\n\nAdditional context: {context}"
        else:
            enhanced_message = message

        logger.debug("Generating response for message: %s", message[:100])
        response = self.chat_chain.run(question=enhanced_message)
        return response

    def _parse_json_response(self, raw_response: str) -> Optional[Dict[str, Any]]:
        """
        Attempt to parse JSON from an LLM response, handling common issues
        like markdown code fences, extra text before/after JSON, etc.

        Args:
            raw_response: The raw string from the LLM

        Returns:
            Parsed dict or None if parsing fails
        """
        # Try direct parse first
        try:
            return json.loads(raw_response.strip())
        except json.JSONDecodeError:
            pass

        # Try extracting JSON from markdown code fences
        fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw_response, re.DOTALL)
        if fence_match:
            try:
                return json.loads(fence_match.group(1))
            except json.JSONDecodeError:
                pass

        # Try finding any JSON object in the response
        brace_match = re.search(r"\{[^{}]*\}", raw_response, re.DOTALL)
        if brace_match:
            try:
                return json.loads(brace_match.group(0))
            except json.JSONDecodeError:
                pass

        return None

    def analyze_for_auto_resolution(
        self,
        title: Optional[str],
        description: str,
        ticket_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Analyze a ticket to determine if it can be automatically resolved.

        Args:
            title: The ticket title
            description: The ticket description
            ticket_id: The ticket ID from the ticketing system

        Returns:
            Dict containing analysis results including whether the ticket can be auto-resolved
        """
        title = title or "No title provided"
        max_retries = 2

        for attempt in range(max_retries + 1):
            try:
                # Get the raw response from the LLM
                logger.debug("Analyzing ticket (attempt %d/%d): %s", attempt + 1, max_retries + 1, title)
                response = self.analysis_chain.run(title=title, description=description)

                result = self._parse_json_response(response)
                if result is not None:
                    # Ensure required keys exist
                    result.setdefault("can_auto_resolve", False)
                    result.setdefault("resolution", "")
                    result.setdefault("reason", "")
                    result["ticket_id"] = ticket_id
                    return result

                # JSON parse failed -- retry if attempts remain
                logger.warning(
                    "Failed to parse LLM JSON (attempt %d/%d): %s",
                    attempt + 1, max_retries + 1, response[:200],
                )

            except Exception as e:
                logger.exception("Error analyzing ticket (attempt %d/%d)", attempt + 1, max_retries + 1)
                if attempt == max_retries:
                    return {
                        "can_auto_resolve": False,
                        "ticket_id": ticket_id,
                        "resolution": "",
                        "reason": f"Error analyzing ticket: {str(e)}"
                    }

        # All retries exhausted with JSON parse failures
        return {
            "can_auto_resolve": False,
            "ticket_id": ticket_id,
            "resolution": "",
            "reason": "Failed to parse LLM response after multiple attempts"
        }
