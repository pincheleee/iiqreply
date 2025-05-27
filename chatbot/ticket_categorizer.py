from typing import Dict, List, Optional, Any
import os
from langchain.llms import Ollama
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from langchain_openai import ChatOpenAI

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
        self.known_patterns = {
            "password reset": "Password Reset",
            "can't login": "Account Access",
            "printer not working": "Printer Issue",
            "wifi": "Network Problem",
            "outlook": "Email Problem",
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
        
        return {"status": "success", "provider": provider, "model": model}
        
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
        combined_text = f"{title} {description}".lower()
        
        # First check for known patterns for efficiency
        for pattern, category in self.known_patterns.items():
            if pattern in combined_text:
                return {
                    "category": category,
                    "confidence": 0.95,
                    "method": "pattern_matching"
                }
        
        # If no pattern match, use LLM for categorization
        try:
            llm_category = self.categorization_chain.run(
                title=title, 
                description=description
            ).strip()
            
            return {
                "category": llm_category,
                "confidence": 0.85,  # Simplified confidence score
                "method": "llm_analysis"
            }
            
        except Exception as e:
            # Fallback for any errors
            return {
                "category": "Other",
                "confidence": 0.0,
                "method": "fallback",
                "error": str(e)
            } 