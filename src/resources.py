"""MCP Resources — auto-loaded context that gives agents instant understanding.

Resources are the single biggest advantage of this MCP server. Instead of an agent
spending 20+ tool calls exploring the codebase, it reads these resources and
immediately has full architectural context.
"""

import json
import re
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from src.config import Config


def register_resources(mcp: FastMCP, config: Config):

    @mcp.resource("repo://overview")
    def get_overview() -> str:
        """Complete overview of all Dealership AI repos, their purpose, and how they connect."""
        return """# Dealership AI / AllyAI — System Overview

## Architecture
AllyAI is an AI-powered platform for auto dealerships with 7 microservices:

### Backend Services (Python/FastAPI, deployed on GCP Cloud Run)
1. **voice-backend-v2** — Voice AI agent for phone calls (ElevenLabs + Retell AI).
   Handles inbound/outbound calls, answers inventory questions, books appointments,
   processes post-call summaries. Uses local FAISS vector search + sentence-transformers.
   Port: 8080. Largest files: prompts.py (58KB), xtime_hack.py (82KB).

2. **chatbot-backend** — Multi-tenant chatbot (OpenAI + LangChain). Per-dealership
   handlers with customized prompts. SQLite for vehicle inventory, Firestore for
   conversations. Deployed on GCE with PM2.
   Port: 8080. Key: app/stores/ (one handler per dealership).

3. **firebase-backend** — Core REST API for users, conversations, post-call AI
   processing, task management, and email campaigns. All data in Firestore.
   Port: 8000. Heaviest modules: post_call.py (41KB), tasks.py (40KB).

4. **admin-dashboard** — Admin panel API for dealership staff. Surfaces conversations,
   analytics snapshots, follow-up tasks, email/SMS campaigns, weekly reports.
   Port: 9001. Uses Instantly.ai for email, Surge for SMS.

5. **workflow-builder** — NLP-driven workflow engine. Dealership describes campaign in
   plain English → LLM generates multi-step workflow (email→SMS→voice). APScheduler
   for delayed steps with conditional branching based on customer responses.
   Port: 8080. Key: app/services/llm_service.py.

6. **selinium-browser-automation** — Selenium service that books appointments on
   dealership web schedulers. Factory pattern per dealership. Uses undetected-chromedriver
   + stealth. Cloud Tasks for async job queue, PagerDuty for failure alerts.
   Port: 8080. Key: precision_automations/ and modules/.

### Frontend (TypeScript/React)
7. **ally-ai-production** — Marketing/landing site (React 18 + Vite). Supabase backend,
   Vapi voice widget, ElevenLabs chat, shadcn/ui components. Separate SaaS app at
   app.allyai.tech handles actual login/dashboard.

## Shared Infrastructure
- **Firestore**: Central database shared across voice-backend-v2, chatbot-backend,
  firebase-backend, admin-dashboard, workflow-builder. Key collections:
  dealership_user_conversations, dealership_tasks, dealership_users.
- **GCP Project**: allyai-website (Cloud Run, Secret Manager, Cloud Tasks, Cloud Scheduler)
- **External APIs**: OpenAI, Google Gemini, ElevenLabs, Retell AI, Vapi, Twilio,
  XTime (scheduling), Autoloop (scheduling), PagerDuty, Instantly.ai, Surge SMS
- **Common env vars**: OPENAI_API_KEY, FIREBASE_CREDENTIALS, VOICE_ENDPOINT

## Inter-Service Communication
- admin-dashboard → firebase-backend (shared Firestore collections)
- chatbot-backend → voice-backend-v2 (VOICE_ENDPOINT for call handoff)
- workflow-builder → chatbot-backend (outbound campaign triggers)
- selinium-browser-automation → xtime/autoloop (web scraping appointment booking)
- admin-dashboard → Instantly.ai, Surge (campaign APIs)
- ally-ai-production → Supabase edge functions → chatbot-backend
"""

    @mcp.resource("repo://conventions")
    def get_conventions() -> str:
        """Coding conventions across all repos."""
        return """# Coding Conventions — Dealership AI

## Python Repos (6/7 repos)
- **Framework**: FastAPI with Pydantic v2 for all request/response models
- **Async**: Mix of async and sync — newer code tends to be async
- **Error handling**: try/except with HTTPException(status_code=X, detail=str(e))
- **Imports**: from X import Y style, grouped by stdlib → third-party → local
- **Naming**: snake_case for functions/variables, PascalCase for classes/models
- **Config**: pydantic-settings BaseSettings loading from .env files
- **Firebase**: firebase_admin SDK, Firestore client initialized in core/firebase.py or utils/firebase.py
- **Docker**: python:3.10-slim or 3.11-slim base, non-root user, EXPOSE 8080, uvicorn CMD
- **Deployment**: deploy.sh scripts targeting GCP Cloud Run (allyai-website project)
- **No tests in most repos** — test infrastructure is minimal

## TypeScript Repo (ally-ai-production)
- **Framework**: React 18 + Vite + React Router v6
- **Styling**: Tailwind CSS with cn() utility from shadcn/ui
- **Components**: Functional components, named exports, PascalCase files
- **State**: TanStack React Query for server state
- **Forms**: React Hook Form + Zod validation
- **UI**: shadcn/ui (Radix primitives) in src/components/ui/
- **Imports**: @/ path alias for src/

## File Organization Pattern (Python repos)
```
app/
├── main.py          # FastAPI app, CORS, router registration
├── core/
│   ├── config.py    # pydantic-settings
│   ├── firebase.py  # Firestore client
│   └── logging_config.py
├── routers/         # Route handlers (one file per domain)
├── models/          # Pydantic models (one file per domain)
├── services/        # Business logic
└── utils/           # Shared helpers
```

## Common Patterns
- Router registration: app.include_router(router, prefix="/api/X")
- Firestore access: db.collection("name").document(id).get()
- Environment: os.getenv("VAR") or Settings class
- CORS: allow_origins=["*"] (all repos)
"""

    @mcp.resource("repo://quick-start")
    def get_quick_start() -> str:
        """Quick start guide for agents working with these repos."""
        return """# Quick Start for AI Agents

## First Steps
1. Call `clone_all_repos()` to get all repos locally
2. Call `get_codebase_summary("repo-name")` for any repo you need to work on
3. Call `extract_patterns("repo-name")` before writing code to match conventions
4. Call `get_service_map()` to understand how repos connect

## Making Changes
1. Use `search_all_repos("pattern")` to find relevant code across all repos
2. Use `scaffold_fastapi_endpoint(...)` or `scaffold_react_component(...)` to generate matching boilerplate
3. Use `scaffold_from_example("repo", "existing_file", "new_name", "what to change")` for complex scaffolding
4. Use `validate_changes("repo")` before committing to catch issues

## Cross-Repo Changes
- Use `find_shared_models()` to understand data contracts between services
- Use `batch_git_status()` to see state across all repos
- Use `batch_create_branch("feature-name")` to create consistent branches

## Key Tools by Workflow
- **Understand a repo**: get_codebase_summary → extract_patterns → get_api_surface
- **Find code**: search_all_repos (all repos) or search_code (single repo)
- **Write new code**: scaffold_* tools → edit_file for customization
- **Validate**: validate_changes (modified files) or validate_repo (full check)
- **Deploy context**: get_deployment_overview
"""


def register_prompts(mcp: FastMCP, config: Config):

    @mcp.prompt()
    def implement_feature(repo_name: str, feature_description: str) -> str:
        """Guided prompt for implementing a new feature in a repo."""
        return f"""I need to implement a feature in the {repo_name} repository.

Feature: {feature_description}

Before writing any code, please:
1. Call get_codebase_summary("{repo_name}") to understand the architecture
2. Call extract_patterns("{repo_name}") to match coding conventions
3. Call search_all_repos with relevant keywords to find similar existing implementations
4. Call get_api_surface("{repo_name}") if adding API endpoints

Then implement the feature following the existing patterns exactly.
After implementation, call validate_changes("{repo_name}") to verify."""

    @mcp.prompt()
    def fix_bug(repo_name: str, bug_description: str) -> str:
        """Guided prompt for fixing a bug."""
        return f"""I need to fix a bug in the {repo_name} repository.

Bug: {bug_description}

Please:
1. Call get_codebase_summary("{repo_name}") for architecture context
2. Search for relevant code with search_code or search_all_repos
3. Call get_function_context for the suspected function
4. Fix the bug, matching existing code patterns
5. Call validate_changes("{repo_name}") to verify the fix"""

    @mcp.prompt()
    def add_endpoint(repo_name: str, endpoint_description: str) -> str:
        """Guided prompt for adding a new API endpoint."""
        return f"""I need to add a new API endpoint to {repo_name}.

Endpoint: {endpoint_description}

Please:
1. Call get_api_surface("{repo_name}") to see existing endpoints
2. Call extract_patterns("{repo_name}") for conventions
3. Use scaffold_fastapi_endpoint to generate matching boilerplate
4. Create any needed Pydantic models with scaffold_pydantic_model
5. Wire up the router in main.py if it's a new router file
6. Call validate_changes("{repo_name}") to verify"""

    @mcp.prompt()
    def cross_repo_change(change_description: str) -> str:
        """Guided prompt for changes that span multiple repos."""
        return f"""I need to make a change that affects multiple repos.

Change: {change_description}

Please:
1. Call get_service_map() to understand service dependencies
2. Call find_shared_models() to see data contracts
3. Call search_all_repos with relevant keywords to find all affected code
4. Plan the change order (backend first, then consumers)
5. Use batch_create_branch("feature-name") to create consistent branches
6. Make changes in dependency order, validating each repo
7. Call batch_git_status() to review all changes"""
