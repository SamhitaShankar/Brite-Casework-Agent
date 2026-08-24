# Brite Casework Agent

A fully autonomous, policy-driven AI casework assistant with strict deterministic safety guardrails, built for the "Policy as Data" Hackathon.

## Prerequisites
- **Node.js** (v18+)
- **Python** (3.9+)

## Setup Instructions

This project is built to run flawlessly in a clean environment out-of-the-box. 

1. **Install Frontend Dependencies:**
   In the root directory, install the Node packages:
   ```bash
   npm install
   ```

2. **Configure Environment:**
   Rename the `.env.example` file to `.env.local` and insert your Gemini API key:
   ```env
   GEMINI_API_KEY="your_api_key_here"
   ```

3. **Run the Application:**
   Start the local development server. This single command will automatically boot both the React frontend and the Python backend concurrently:
   ```bash
   npm run dev
   ```

4. **Access the Agent:**
   Open your browser and navigate to `http://localhost:3000`.

## Architecture Notes for Evaluators
- **Zero Python Dependencies Required:** The Python backend is engineered to run purely on the standard library. If SQLAlchemy or Pydantic are not installed in the environment, a custom `compat.py` layer mocks them out and falls back to an in-memory datastore.
- **SQLite Default:** The application defaults to a local SQLite database (`brite_casework.db`), requiring no PostgreSQL server configuration to run.
- **LLM Independence:** The Gemini service includes a direct REST API fallback that uses `urllib.request` natively, meaning the `google-genai` SDK is not strictly required.
- **Policy as Data:** The system's authority boundary is driven by `data/policy_rules.json`, completely decoupled from the application logic.

## Documentation
Please refer to the enclosed `DECISIONS.md` file for an explanation of the agent's structural guardrails and incapability to perform irreversible actions.
