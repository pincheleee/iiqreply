import os
import logging
import time
from collections import defaultdict
from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, field_validator
from typing import Dict, List, Optional

from chatbot.llm_manager import LLMManager
from chatbot.ticket_categorizer import TicketCategorizer
from chatbot.incident_iq import IncidentIQConnector

# Load environment variables
load_dotenv()

# Configure logging
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("iiqreply")

app = FastAPI(title="Local LLM IT Chatbot & Auto-Ticket Resolver")

# --- Rate limiting middleware ---
MAX_REQUESTS_PER_MINUTE = int(os.getenv("RATE_LIMIT_RPM", "30"))
_rate_store: Dict[str, list] = defaultdict(list)

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Simple in-memory per-IP rate limiter."""
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    window = 60  # seconds

    # Prune old timestamps
    _rate_store[client_ip] = [t for t in _rate_store[client_ip] if now - t < window]

    if len(_rate_store[client_ip]) >= MAX_REQUESTS_PER_MINUTE:
        logger.warning("Rate limit exceeded for %s", client_ip)
        return JSONResponse(
            status_code=429,
            content={"detail": "Too many requests. Please try again later."},
        )

    _rate_store[client_ip].append(now)
    return await call_next(request)

# Add CORS middleware to allow frontend to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify the allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize components
llm_manager = LLMManager()
ticket_categorizer = TicketCategorizer()
incident_iq = IncidentIQConnector(
    api_key=os.getenv("INCIDENT_IQ_API_KEY"),
    base_url=os.getenv("INCIDENT_IQ_BASE_URL")
)

# Create static directory if it doesn't exist
os.makedirs("static", exist_ok=True)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# --- Max message / description length ---
MAX_MESSAGE_LENGTH = int(os.getenv("MAX_MESSAGE_LENGTH", "5000"))


class ChatRequest(BaseModel):
    message: str
    user_id: Optional[str] = None
    context: Optional[Dict] = None

    @field_validator("message")
    @classmethod
    def validate_message_length(cls, v: str) -> str:
        if len(v) > MAX_MESSAGE_LENGTH:
            raise ValueError(f"Message exceeds maximum length of {MAX_MESSAGE_LENGTH} characters")
        if not v.strip():
            raise ValueError("Message cannot be empty")
        return v


class TicketRequest(BaseModel):
    description: str
    title: Optional[str] = None
    user_id: Optional[str] = None
    ticket_id: Optional[str] = None
    attachments: Optional[List[str]] = None

    @field_validator("description")
    @classmethod
    def validate_description_length(cls, v: str) -> str:
        if len(v) > MAX_MESSAGE_LENGTH:
            raise ValueError(f"Description exceeds maximum length of {MAX_MESSAGE_LENGTH} characters")
        if not v.strip():
            raise ValueError("Description cannot be empty")
        return v


class LLMProviderRequest(BaseModel):
    provider: str
    api_key: Optional[str] = None
    model_name: Optional[str] = None


@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the frontend UI"""
    return HTMLResponse(open("static/index.html").read())


@app.post("/chat")
async def chat(request: ChatRequest):
    """Process user questions and provide answers using the configured LLM"""
    logger.info("Chat request from user=%s, message_len=%d", request.user_id, len(request.message))
    response = llm_manager.generate_response(request.message, request.context)
    return JSONResponse(content={"response": response})


@app.post("/categorize_ticket")
async def categorize_ticket(request: TicketRequest):
    """Analyze ticket content and categorize it"""
    logger.info("Categorize request: ticket_id=%s, title=%s", request.ticket_id, request.title)
    category = ticket_categorizer.categorize(request.title, request.description)

    # If ticket_id provided and IIQ is configured, update the ticket category
    if request.ticket_id and incident_iq.api_key:
        logger.info("Updating IIQ ticket %s with category %s", request.ticket_id, category.get("category"))
        iiq_result = incident_iq.update_ticket(
            ticket_id=request.ticket_id,
            updates={"category": category.get("category", "Other")}
        )
        category["iiq_update"] = iiq_result

    return JSONResponse(content={"category": category})


@app.post("/resolve_ticket")
async def resolve_ticket(request: TicketRequest):
    """Attempt to auto-resolve a ticket if it matches known patterns"""
    logger.info("Resolve request: ticket_id=%s, title=%s", request.ticket_id, request.title)

    resolution_result = llm_manager.analyze_for_auto_resolution(
        title=request.title,
        description=request.description,
        ticket_id=request.ticket_id,
    )

    if resolution_result["can_auto_resolve"]:
        # If ticket_id provided and IIQ is configured, resolve in IIQ
        iiq_result = None
        if request.ticket_id and incident_iq.api_key:
            logger.info("Resolving IIQ ticket %s", request.ticket_id)
            iiq_result = incident_iq.resolve_ticket(
                ticket_id=request.ticket_id,
                resolution=resolution_result["resolution"]
            )

        response_content = {
            "auto_resolved": True,
            "resolution": resolution_result["resolution"],
        }
        if iiq_result:
            response_content["iiq_result"] = iiq_result
        return JSONResponse(content=response_content)
    else:
        return JSONResponse(content={
            "auto_resolved": False,
            "reason": resolution_result["reason"]
        })


@app.post("/switch_provider")
async def switch_provider(request: LLMProviderRequest):
    """
    Switch between different LLM providers (Ollama/OpenAI)
    """
    logger.info("Switching provider to %s", request.provider)
    try:
        # Update LLM provider in both manager and categorizer
        llm_result = llm_manager.switch_provider(
            provider=request.provider,
            api_key=request.api_key,
            model_name=request.model_name
        )

        categorizer_result = ticket_categorizer.switch_provider(
            provider=request.provider,
            api_key=request.api_key,
            model_name=request.model_name
        )

        logger.info("Provider switched successfully to %s, model=%s", request.provider, llm_result.get("model"))
        return JSONResponse(content={
            "status": "success",
            "message": f"Switched to {request.provider} provider",
            "provider": request.provider,
            "model": llm_result.get("model")
        })
    except ValueError as e:
        logger.error("Invalid provider switch request: %s", e)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Error switching providers")
        raise HTTPException(status_code=500, detail=f"Error switching providers: {str(e)}")


@app.get("/status")
async def get_status():
    """Get the current status of the API and LLM configuration"""
    return JSONResponse(content={
        "status": "online",
        "llm_provider": llm_manager.provider,
        "llm_model": llm_manager.model_name,
        "incident_iq_connected": bool(incident_iq.api_key)
    })


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    logger.info("Starting server on port %d", port)
    uvicorn.run(app, host="0.0.0.0", port=port)
