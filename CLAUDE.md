# IIQ Reply

Local AI chatbot and auto-ticket resolver for IT helpdesks. Chat interface for end-user IT questions, automatic ticket categorization (pattern matching + LLM fallback), and auto-resolution analysis. Supports Ollama (local) and OpenAI (cloud) LLM providers with runtime switching. Ships with an Incident IQ ticketing connector as the reference implementation.

## Architecture

FastAPI backend with a single-page HTML frontend. Three core modules handle LLM interaction, ticket categorization, and ticketing system integration.

### File structure

```
iiqreply/
  main.py                      # FastAPI app: routes, middleware, request models, server entry
  requirements.txt             # Python dependencies (11 packages)
  Dockerfile                   # python:3.11-slim, uvicorn on port 8000
  env.example                  # Environment variable template
  static/
    index.html                 # Web UI: chat tab, ticket tab, provider config panel
  chatbot/
    __init__.py
    llm_manager.py             # LLM provider management, chat generation, auto-resolution analysis
    ticket_categorizer.py      # Pattern matching (keyword -> category) + LLM fallback categorization
    incident_iq.py             # Incident IQ REST API connector (reference ticketing implementation)
  CHANGELOG.md                 # Version history
```

### Request flow

```
Browser (static/index.html)
  |
  v
FastAPI (main.py)
  ├── rate limit middleware (per-IP sliding window)
  ├── CORS middleware
  |
  ├── POST /chat          -> LLMManager.generate_response()    -> LLM (Ollama or OpenAI)
  ├── POST /categorize    -> TicketCategorizer.categorize()     -> pattern match or LLM
  │                           └── IncidentIQConnector.update()  -> IIQ API (if configured)
  ├── POST /resolve       -> LLMManager.analyze_for_auto_resolution() -> LLM
  │                           └── IncidentIQConnector.resolve() -> IIQ API (if configured)
  ├── POST /switch_provider -> hot-swap LLM provider at runtime
  └── GET  /status          -> current provider, model, IIQ connection status
```

### Module responsibilities

- **`main.py`** -- FastAPI app creation, middleware (rate limiting, CORS), Pydantic request/response models with field validators, route handlers, static file serving, uvicorn startup
- **`llm_manager.py`** -- LangChain `LLMChain` wrappers for chat and ticket analysis prompts. Supports Ollama (via `langchain.llms.Ollama`) and OpenAI (via `langchain_openai.ChatOpenAI`). Robust JSON parsing with 3 strategies: direct parse, code-fence extraction, brace matching. Retries up to 3 times on parse failure.
- **`ticket_categorizer.py`** -- Two-tier categorization: fast keyword pattern matching (22 patterns across 11 categories) with real confidence scores, then LLM fallback with validated category normalization. Pattern confidence accounts for title vs description placement and multi-pattern bonuses.
- **`incident_iq.py`** -- REST client for Incident IQ API. Methods: `get_ticket`, `create_ticket`, `update_ticket`, `resolve_ticket`, `add_comment`. Gracefully disabled when no API key is configured.

## Stack

- **Python 3.11+**
- **FastAPI** 0.105.0 -- async web framework
- **uvicorn** 0.24.0 -- ASGI server
- **LangChain** 0.1.0 + **langchain-community** 0.0.16 -- LLM orchestration (PromptTemplate, LLMChain)
- **langchain-openai** 0.0.5 -- ChatOpenAI wrapper
- **ollama** 0.1.7 -- Ollama Python client
- **openai** 1.3.0 -- OpenAI API client
- **Pydantic** 2.5.2 -- request validation
- **requests** 2.31.0 -- HTTP client for IIQ connector
- **python-dotenv** 1.0.0 -- `.env` loading
- **python-docx** 0.8.11 -- (dependency, not actively used in current code)

## Key patterns

- **Dual LLM providers** -- Ollama and OpenAI are interchangeable at runtime via `/switch_provider`. Both LLMManager and TicketCategorizer maintain their own LLM instance and rebuild LangChain chains on switch.
- **Two-tier categorization** -- pattern matching (0.82-0.99 confidence) is tried first for speed and determinism; LLM is only called when no pattern matches (base 0.80 confidence, adjusted by validation quality).
- **Robust JSON parsing** -- `_parse_json_response()` handles the common LLM failure modes: raw JSON, markdown-fenced JSON, and brace-extracted JSON. Three retry attempts before giving up.
- **Rate limiting** -- in-memory per-IP sliding window (default 30 req/min). Simple `defaultdict(list)` of timestamps, pruned on each request.
- **Input validation** -- Pydantic `field_validator` on message and description fields enforces max length (default 5000 chars) and non-empty input.
- **Pluggable ticketing** -- the Incident IQ connector is the reference implementation, but the architecture is connector-agnostic. Any ticketing system can be integrated by implementing the same interface.
- **Inline frontend** -- `static/index.html` is a self-contained SPA with chat and ticket tabs, provider config panel, loading spinners, and status display.

## Commands

- `pip install -r requirements.txt` -- install dependencies
- `cp env.example .env` -- create environment config
- `python main.py` -- start server at http://localhost:8000
- `docker build -t iiqreply . && docker run -p 8000:8000 --env-file .env iiqreply` -- build and run via Docker

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | `ollama` | `ollama` or `openai` |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | `llama3` | Ollama model name |
| `OPENAI_API_KEY` | (none) | Required if provider is `openai` |
| `OPENAI_MODEL` | `gpt-4` | OpenAI model name |
| `INCIDENT_IQ_API_KEY` | (none) | IIQ API key (omit to disable connector) |
| `INCIDENT_IQ_BASE_URL` | `https://api.incidentiq.com/v1` | IIQ API base URL |
| `PORT` | `8000` | Server port |
| `LOG_LEVEL` | `INFO` | Python logging level |
| `RATE_LIMIT_RPM` | `30` | Max requests per minute per IP |
| `MAX_MESSAGE_LENGTH` | `5000` | Max chars for messages and descriptions |

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Serve web UI |
| `POST` | `/chat` | Chat with IT support bot |
| `POST` | `/categorize_ticket` | Categorize a support ticket |
| `POST` | `/resolve_ticket` | Attempt auto-resolution |
| `POST` | `/switch_provider` | Switch LLM provider at runtime |
| `GET` | `/status` | API and provider status |
