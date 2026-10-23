# IIQ Reply

Local AI chatbot for IT helpdesk support with auto ticket categorization and resolution. Supports Ollama (local) and OpenAI providers with a pluggable ticketing connector.

## Stack
Python, FastAPI, Ollama/OpenAI, Pydantic, Docker, uvicorn

## Commands
- `pip install -r requirements.txt` -- install dependencies
- `cp env.example .env` -- create env config
- `python main.py` -- start server at http://localhost:8000
- `docker build -t iiqreply . && docker run -p 8000:8000 --env-file .env iiqreply` -- run via Docker
