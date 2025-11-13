import os
from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Dict, List, Optional

from chatbot.llm_manager import LLMManager
from chatbot.ticket_categorizer import TicketCategorizer
from chatbot.incident_iq import IncidentIQConnector

# Load environment variables
load_dotenv()

app = FastAPI(title="Local LLM IT Chatbot & Auto-Ticket Resolver")

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

class ChatRequest(BaseModel):
    message: str
    user_id: Optional[str] = None
    context: Optional[Dict] = None

class TicketRequest(BaseModel):
    description: str
    title: Optional[str] = None
    user_id: Optional[str] = None
    ticket_id: Optional[str] = None
    attachments: Optional[List[str]] = None

class LLMProviderRequest(BaseModel):
    provider: str
    api_key: Optional[str] = None
    model_name: Optional[str] = None

@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the frontend UI"""
    with open("static/index.html") as f:
        return HTMLResponse(f.read())

@app.post("/chat")
async def chat(request: ChatRequest):
    """Process user questions and provide answers using the configured LLM"""
    response = llm_manager.generate_response(request.message, request.context)
    return JSONResponse(content={"response": response})

@app.post("/categorize_ticket")
async def categorize_ticket(request: TicketRequest):
    """Analyze ticket content and categorize it"""
    category = ticket_categorizer.categorize(request.title, request.description)
    return JSONResponse(content={"category": category})

@app.post("/resolve_ticket")
async def resolve_ticket(request: TicketRequest):
    """Attempt to auto-resolve a ticket if it matches known patterns"""
    if not request.ticket_id:
        raise HTTPException(status_code=400, detail="ticket_id is required for auto-resolution")

    resolution_result = llm_manager.analyze_for_auto_resolution(
        request.title,
        request.description
    )

    if resolution_result["can_auto_resolve"]:
        # Send resolution to Incident IQ using the provided ticket_id
        incident_iq.resolve_ticket(
            ticket_id=request.ticket_id,
            resolution=resolution_result["resolution"]
        )
        return JSONResponse(content={
            "auto_resolved": True,
            "ticket_id": request.ticket_id,
            "resolution": resolution_result["resolution"]
        })
    else:
        return JSONResponse(content={
            "auto_resolved": False,
            "ticket_id": request.ticket_id,
            "reason": resolution_result["reason"]
        })

@app.post("/switch_provider")
async def switch_provider(request: LLMProviderRequest):
    """
    Switch between different LLM providers (Ollama/OpenAI)
    """
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
        
        return JSONResponse(content={
            "status": "success",
            "message": f"Switched to {request.provider} provider",
            "provider": request.provider,
            "model": llm_result.get("model")
        })
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
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
    uvicorn.run(app, host="0.0.0.0", port=port) 