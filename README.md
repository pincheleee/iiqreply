# Local LLM Chatbot & Auto-Ticket Resolver

A local AI chatbot using Ollama and LLaMA models to answer IT questions and auto-categorize tickets. Now with OpenAI API support! Integrates with Incident IQ to auto-resolve repetitive tasks.

## Features

- Local LLM-powered IT support chatbot using Ollama
- Optional OpenAI API integration
- Web-based UI for easy interaction
- Automatic ticket categorization
- Integration with Incident IQ ticketing system
- Auto-resolution of common IT issues

## Requirements

- Python 3.8+
- [Ollama](https://ollama.ai/) installed locally with LLaMA models (for local LLM support)
- OpenAI API key (optional, for using OpenAI models)
- Incident IQ account with API access (for ticket management)

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/local-it-chatbot.git
   cd local-it-chatbot
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Set up environment variables:
   ```
   cp env.example .env
   ```
   Edit the `.env` file with your Incident IQ API credentials and other settings.

4. If using local models, make sure Ollama is running with the required model:
   ```
   ollama run llama3
   ```

## Usage

1. Start the API server:
   ```
   python main.py
   ```

2. Open your browser and navigate to `http://localhost:8000`

3. Use the web interface to:
   - Chat with the IT support bot
   - Submit and categorize support tickets
   - Switch between Ollama (local) and OpenAI (API) providers
   - Enter your OpenAI API key if desired

## LLM Provider Options

### Local (Ollama)
- Default option, uses locally running Ollama with LLaMA models
- No API key required
- Privacy-friendly (all data stays local)
- Requires more local computing resources

### OpenAI API
- Higher quality responses
- Requires OpenAI API key
- Internet connection required
- API usage costs apply

## API Endpoints

- `GET /` - Web interface
- `POST /chat` - Ask a question to the IT support chatbot
- `POST /categorize_ticket` - Auto-categorize an IT support ticket
- `POST /resolve_ticket` - Attempt to auto-resolve a ticket
- `POST /switch_provider` - Switch between Ollama and OpenAI
- `GET /status` - Get current LLM provider status

## Example API Calls

### Chat with the bot

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "How do I reset my Windows password?"}'
```

### Categorize a ticket

```bash
curl -X POST http://localhost:8000/categorize_ticket \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Can't access my email", 
    "description": "I'm unable to log into my Outlook account since this morning. I've tried resetting my password but still getting an error."
  }'
```

### Switch to OpenAI provider

```bash
curl -X POST http://localhost:8000/switch_provider \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "openai",
    "api_key": "your-openai-api-key",
    "model_name": "gpt-4"
  }'
```

## License

MIT

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request. 