# IT Support Bot -- Local LLM Chatbot & Auto-Ticket Resolver

A local AI chatbot using Ollama and LLaMA models to answer IT questions and auto-categorize/resolve tickets. Supports OpenAI as an alternative provider. Designed to integrate with any ticketing system (Incident IQ, Spiceworks, Jira Service Management, Zendesk, etc.) by swapping the API connector.

> **Connector note:** The included Incident IQ connector (`chatbot/incident_iq.py`) is the reference implementation. To integrate with a different ticketing platform, implement the same interface against your platform's API. The rest of the codebase (LLM, categorizer, UI) is ticketing-system-agnostic and works unchanged.

## Features

- **LLM-powered IT support chatbot** -- chat interface for end-user IT questions
- **Dual LLM providers** -- Ollama (local, privacy-friendly) or OpenAI (cloud, higher quality); switchable at runtime
- **Automatic ticket categorization** -- pattern matching for common issues (with real confidence scores) plus LLM fallback for everything else
- **Auto-resolution analysis** -- LLM determines whether a ticket can be self-resolved and provides step-by-step instructions
- **Ticketing system integration** -- pluggable connector architecture; ships with an Incident IQ connector and can be adapted to Spiceworks, Jira Service Management, Zendesk, or any REST API
- **Robust JSON parsing** -- retries and multiple extraction strategies for LLM responses (direct parse, code-fence extraction, brace matching)
- **Rate limiting** -- per-IP sliding-window rate limiter (default 30 req/min, configurable)
- **Input validation** -- max message/description length (default 5000 chars), empty-input rejection via Pydantic validators
- **Web UI** -- single-page frontend with chat tab and ticket-creation tab, loading spinners, provider toggle, and status display
- **Docker support** -- production-ready Dockerfile (python:3.11-slim, uvicorn)

## Project Structure

```
iiqreply/
  main.py                  # FastAPI app, routes, middleware
  requirements.txt         # Python dependencies
  Dockerfile               # Container image definition
  env.example              # Sample environment variables
  static/
    index.html             # Web UI (chat + ticket tabs)
  chatbot/
    __init__.py
    llm_manager.py         # LLM provider management, chat, auto-resolution analysis
    ticket_categorizer.py  # Pattern matching + LLM ticket categorization
    incident_iq.py         # Incident IQ API connector (reference implementation)
```

## Requirements

- Python 3.11+ (3.8+ may work but 3.11 is tested)
- [Ollama](https://ollama.ai/) installed locally with a model pulled (for local LLM mode)
- OpenAI API key (optional, for cloud LLM mode)
- Ticketing system API access (optional; Incident IQ connector included, others can be added)

## Installation

1. Clone the repository:
   ```bash
   git clone <repo-url>
   cd iiqreply
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up environment variables:
   ```bash
   cp env.example .env
   ```
   Edit `.env` with your credentials and settings (see Environment Variables below).

5. If using Ollama, make sure it is running with a model pulled:
   ```bash
   ollama pull llama3
   ```

## Usage

Start the API server:
```bash
python main.py
```

Open your browser to `http://localhost:8000` to use the web UI.

### Web UI

- **Chat tab** -- ask IT support questions; responses stream from the configured LLM
- **Ticket tab** -- enter a title, description, and optional IIQ ticket ID; the system categorizes the ticket and attempts auto-resolution
- **Provider toggle** -- switch between Ollama and OpenAI at runtime from the config panel

## Docker

Build and run:
```bash
docker build -t iiqreply .
docker run -p 8000:8000 --env-file .env iiqreply
```

The container uses `python:3.11-slim` and runs uvicorn on port 8000.

If you need Ollama access from inside the container, set `OLLAMA_HOST` to the host machine address (e.g., `http://host.docker.internal:11434` on Docker Desktop).

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `LLM_PROVIDER` | `ollama` | LLM provider: `ollama` or `openai` |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | `llama3` | Ollama model name |
| `OPENAI_API_KEY` | (none) | OpenAI API key (required if provider is `openai`) |
| `OPENAI_MODEL` | `gpt-4` | OpenAI model name |
| `INCIDENT_IQ_API_KEY` | (none) | Incident IQ API key (omit to disable IIQ connector) |
| `INCIDENT_IQ_BASE_URL` | `https://api.incidentiq.com/v1` | Incident IQ API base URL (reference connector) |
| `PORT` | `8000` | Server port |
| `LOG_LEVEL` | `INFO` | Python logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `RATE_LIMIT_RPM` | `30` | Max requests per minute per IP |
| `MAX_MESSAGE_LENGTH` | `5000` | Max characters for chat messages and ticket descriptions |

## API Endpoints

### `GET /` -- Web UI
Serves the single-page frontend.

### `POST /chat` -- Chat with the IT support bot
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "How do I reset my Windows password?"}'
```
Request body:
- `message` (string, required) -- the question (max `MAX_MESSAGE_LENGTH` chars)
- `user_id` (string, optional) -- caller identifier
- `context` (object, optional) -- additional context passed to the LLM

### `POST /categorize_ticket` -- Categorize a support ticket
```bash
curl -X POST http://localhost:8000/categorize_ticket \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Can'\''t access my email",
    "description": "Unable to log into Outlook since this morning.",
    "ticket_id": "IIQ-12345"
  }'
```
Request body:
- `description` (string, required) -- ticket description
- `title` (string, optional) -- ticket title
- `ticket_id` (string, optional) -- ticketing system ticket ID; if provided and a connector is configured, the ticket is updated in the external system
- `user_id` (string, optional)

Response includes `category`, `confidence` (0.0--0.99), and `method` (`pattern_matching` or `llm_analysis`).

### `POST /resolve_ticket` -- Attempt auto-resolution
```bash
curl -X POST http://localhost:8000/resolve_ticket \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Password reset needed",
    "description": "User forgot their Active Directory password.",
    "ticket_id": "IIQ-12345"
  }'
```
Request body: same as `/categorize_ticket`.

Response includes `auto_resolved` (boolean), `resolution` or `reason`, and optionally `iiq_result` if the ticket was resolved in the connected ticketing system.

### `POST /switch_provider` -- Switch LLM provider at runtime
```bash
curl -X POST http://localhost:8000/switch_provider \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "openai",
    "api_key": "sk-...",
    "model_name": "gpt-4"
  }'
```

### `GET /status` -- API and provider status
```bash
curl http://localhost:8000/status
```
Returns current provider, model, and whether a ticketing connector is active.

## Ticket Categories

The categorizer recognizes these categories (via pattern matching or LLM):

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
- Other

Pattern matching uses keyword-based rules with real confidence scores (0.82--0.99) that account for title vs. description placement and multiple-pattern bonuses. When no pattern matches, the LLM categorizes with a base confidence of 0.80, adjusted by validation quality.

## LLM Provider Options

### Ollama (Local)
- Default provider; uses locally running Ollama
- No API key required
- Privacy-friendly -- all data stays on your machine
- Requires local compute resources and a pulled model

### OpenAI (Cloud)
- Higher quality responses (GPT-4, GPT-3.5 Turbo)
- Requires an OpenAI API key
- Internet connection required
- API usage costs apply

## License

MIT

## Contributing

Contributions are welcome. Please feel free to submit a Pull Request.
