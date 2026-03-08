# Changelog

All notable changes to this project will be documented in this file.

## [0.2.0] - 2026-03-08

### Fixed
- Hardcoded mock `ticket_id` bug -- resolve/categorize endpoints were always using "mock-ticket-id" instead of the actual ticket ID from the request
- Incident IQ connector was dead code -- wired it up so it actually calls the IIQ API when a ticket_id is provided and an API key is configured
- Frontend `categoryData` nesting bug -- response shape from `/categorize_ticket` wraps category info in a `category` key; frontend now handles both nested and flat shapes correctly
- Ticket categorization confidence scores were hardcoded (0.95/0.85) -- replaced with real pattern-based scoring (0.82--0.99) that accounts for title vs. description placement and multi-pattern bonuses; LLM path uses validated base confidence of 0.80

### Added
- Proper Python `logging` module throughout (replaced all `print()` calls); log level configurable via `LOG_LEVEL` env var
- Robust JSON parsing for LLM responses (`_parse_json_response`) with three fallback strategies: direct parse, markdown code-fence extraction, brace matching
- Retry logic (up to 3 attempts) for auto-resolution LLM analysis when JSON parsing fails
- Rate limiting middleware -- 30 requests/minute per IP (sliding window), configurable via `RATE_LIMIT_RPM` env var
- Input validation -- max message/description length of 5000 characters (configurable via `MAX_MESSAGE_LENGTH`), empty-input rejection via Pydantic field validators
- Loading spinner in the web UI for both chat and ticket submission
- Frontend input validation (API key length check, empty-message guard)
- Dockerfile (`python:3.11-slim`, uvicorn, port 8000)

### Changed
- LLM category validation now checks against a defined `VALID_CATEGORIES` set with exact, case-insensitive, and substring matching; unrecognized categories fall back to "Other (raw)"
- `analyze_for_auto_resolution` now accepts and passes through the real `ticket_id` from the request instead of a hardcoded value

## [0.1.0] - 2026-03-07

### Added
- Initial project scaffold
- FastAPI server with chat, categorize, resolve, switch_provider, and status endpoints
- Ollama (local) and OpenAI (cloud) LLM provider support with runtime switching
- Ticket categorization via LangChain LLMChain
- Incident IQ connector module (initial implementation)
- Web UI with chat and ticket tabs, provider toggle
- CORS middleware
- Environment variable configuration via `.env`
