# Skylark Drones — Monday.com BI Agent

## Phase 1: Setup & Live Monday.com Connection

### Setup
1. `python -m venv venv && source venv/bin/activate` (or `venv\Scripts\activate` on Windows)
2. `pip install -r requirements.txt`
3. `cp .env.example .env` and fill in your monday.com API token and board IDs
4. `python main.py`

### What Phase 1 does
- Loads config securely from environment variables (no hardcoded secrets)
- Authenticates with monday.com via API token
- Reads column structure (schema) of both boards
- Reads live item data from both boards, read-only, with retry/backoff on failures
- Confirms: no CSV data is loaded anywhere — all data comes from live monday.com queries

### Architecture (so far)