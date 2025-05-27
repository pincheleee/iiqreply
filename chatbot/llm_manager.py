import os
from typing import Dict, List, Optional, Any
import ollama
from langchain.llms import Ollama
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain

# Add OpenAI imports
from langchain_openai import ChatOpenAI

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
            
            Format your response as JSON with keys: can_auto_resolve (boolean), resolution (string), reason (string)
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
            
        response = self.chat_chain.run(question=enhanced_message)
        return response
    
    def analyze_for_auto_resolution(self, title: Optional[str], description: str) -> Dict[str, Any]:
        """
        Analyze a ticket to determine if it can be automatically resolved.
        
        Args:
            title: The ticket title
            description: The ticket description
            
        Returns:
            Dict containing analysis results including whether the ticket can be auto-resolved
        """
        title = title or "No title provided"
        
        try:
            # Get the raw response from the LLM
            response = self.analysis_chain.run(title=title, description=description)
            
            # Parse the response - in a real implementation, we'd use proper JSON parsing
            # For simplicity, we're mocking the response parsing here
            import json
            try:
                result = json.loads(response)
            except json.JSONDecodeError:
                # Fallback if the LLM doesn't produce valid JSON
                result = {
                    "can_auto_resolve": False,
                    "resolution": "",
                    "reason": "Failed to parse LLM response"
                }
                
            # Add ticket_id field for consistency with the API
            result["ticket_id"] = "mock-ticket-id"  # In real implementation, this would come from the request
            
            return result
            
        except Exception as e:
            # Fallback for any errors
            return {
                "can_auto_resolve": False,
                "ticket_id": "mock-ticket-id",
                "resolution": "",
                "reason": f"Error analyzing ticket: {str(e)}"
            } 