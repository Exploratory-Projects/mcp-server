import json
import re
import subprocess
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from src.config import Config

REPO_NAME = "workflow-builder"


def _ensure_cloned(config: Config) -> Path | str:
    p = config.get_repo_path(REPO_NAME)
    if not p.is_dir():
        return f"Error: workflow-builder not cloned. Use clone_repo('{REPO_NAME}') first."
    return p


def register_workflow_builder_tools(mcp: FastMCP, config: Config):

    # ── Workflow Models ────────────────────────────────────────────────

    @mcp.tool()
    def get_workflow_models() -> str:
        """Inspect Pydantic workflow, step, and condition models (app/models/)."""
        repo = _ensure_cloned(config)
        if isinstance(repo, str):
            return repo

        models_dir = repo / "app" / "models"
        results = []
        if models_dir.is_dir():
            for f in sorted(models_dir.rglob("*.py")):
                if f.name == "__init__.py":
                    continue
                text = f.read_text(errors="replace")
                items = []
                for i, line in enumerate(text.split("\n"), 1):
                    stripped = line.strip()
                    if stripped.startswith("class "):
                        items.append(f"  L{i}: {stripped}")
                    elif ":" in stripped and not stripped.startswith("#") and not stripped.startswith("def "):
                        # Likely a Pydantic field
                        if any(t in stripped for t in ["str", "int", "bool", "list", "dict", "Optional", "List", "datetime"]):
                            items.append(f"    L{i}: {stripped}")
                results.append(f"=== {f.name} ({f.stat().st_size / 1024:.1f} KB) ===\n" + "\n".join(items))

        return "\n\n".join(results) if results else "No models directory found."

    # ── LLM Service / Workflow Generation ──────────────────────────────

    @mcp.tool()
    def get_llm_service_info() -> str:
        """Inspect the LLM service that generates workflows from natural language prompts."""
        repo = _ensure_cloned(config)
        if isinstance(repo, str):
            return repo

        filepath = repo / "app" / "services" / "llm_service.py"
        if not filepath.exists():
            return "No llm_service.py found."

        text = filepath.read_text(errors="replace")
        results = []
        for i, line in enumerate(text.split("\n"), 1):
            stripped = line.strip()
            if (stripped.startswith("def ") or stripped.startswith("async def ") or
                    stripped.startswith("class ") or "system" in stripped.lower() and "prompt" in stripped.lower()):
                results.append(f"  L{i}: {stripped[:120]}")

        return f"LLM Service (llm_service.py, {filepath.stat().st_size / 1024:.1f} KB):\n" + "\n".join(results)

    @mcp.tool()
    def get_workflow_generation_prompt() -> str:
        """Extract the LLM system prompt used for workflow generation."""
        repo = _ensure_cloned(config)
        if isinstance(repo, str):
            return repo

        filepath = repo / "app" / "services" / "llm_service.py"
        if not filepath.exists():
            return "No llm_service.py found."

        text = filepath.read_text(errors="replace")
        # Find system prompt strings
        prompt_matches = re.findall(r'(?:system_prompt|SYSTEM_PROMPT|system_message)\s*=\s*(?:f?"""(.+?)"""|f?"(.+?)")', text, re.DOTALL)
        if prompt_matches:
            return "System prompt(s) found:\n" + "\n---\n".join(m[0] or m[1] for m in prompt_matches)

        # Fallback: return relevant sections
        lines = text.split("\n")
        relevant = []
        for i, line in enumerate(lines):
            if "prompt" in line.lower() or "system" in line.lower() or "instruction" in line.lower():
                start = max(0, i - 2)
                end = min(len(lines), i + 5)
                relevant.extend(f"  L{j+1}: {lines[j]}" for j in range(start, end))
                relevant.append("  ...")

        return "\n".join(relevant) if relevant else "Could not extract prompt. Read the file directly."

    # ── Service Modules ────────────────────────────────────────────────

    @mcp.tool()
    def list_workflow_services() -> str:
        """List all service modules (workflow orchestration, email, SMS, voice)."""
        repo = _ensure_cloned(config)
        if isinstance(repo, str):
            return repo

        services_dir = repo / "app" / "services"
        results = []
        if services_dir.is_dir():
            for f in sorted(services_dir.rglob("*.py")):
                if f.name == "__init__.py":
                    continue
                size_kb = f.stat().st_size / 1024
                text = f.read_text(errors="replace")
                funcs = [l.strip().split("(")[0].replace("def ", "").replace("async ", "")
                         for l in text.split("\n")
                         if l.strip().startswith("def ") or l.strip().startswith("async def ")]
                results.append(f"  {f.name} ({size_kb:.1f} KB): {', '.join(funcs[:8])}")

        return f"Services:\n" + "\n".join(results) if results else "No services directory found."

    @mcp.tool()
    def get_workflow_orchestrator() -> str:
        """Inspect the workflow orchestration engine (workflow_service.py) - step scheduling, APScheduler."""
        repo = _ensure_cloned(config)
        if isinstance(repo, str):
            return repo

        filepath = repo / "app" / "services" / "workflow_service.py"
        if not filepath.exists():
            return "No workflow_service.py found."

        text = filepath.read_text(errors="replace")
        results = []
        for i, line in enumerate(text.split("\n"), 1):
            stripped = line.strip()
            if (stripped.startswith("def ") or stripped.startswith("async def ") or
                    stripped.startswith("class ") or "scheduler" in stripped.lower()):
                results.append(f"  L{i}: {stripped[:120]}")

        return f"Workflow Orchestrator ({filepath.stat().st_size / 1024:.1f} KB):\n" + "\n".join(results)

    # ── Channel Services ───────────────────────────────────────────────

    @mcp.tool()
    def get_email_service_info() -> str:
        """Inspect the Gmail email service for campaign sends."""
        repo = _ensure_cloned(config)
        if isinstance(repo, str):
            return repo

        filepath = repo / "app" / "services" / "email_service.py"
        if not filepath.exists():
            return "No email_service.py found."

        text = filepath.read_text(errors="replace")
        funcs = [f"  L{i}: {l.strip()}" for i, l in enumerate(text.split("\n"), 1)
                 if l.strip().startswith("def ") or l.strip().startswith("async def ")]
        return f"Email Service ({filepath.stat().st_size / 1024:.1f} KB):\n" + "\n".join(funcs)

    @mcp.tool()
    def get_sms_service_info() -> str:
        """Inspect the Surge SMS service for campaign sends."""
        repo = _ensure_cloned(config)
        if isinstance(repo, str):
            return repo

        filepath = repo / "app" / "services" / "sms_service.py"
        if not filepath.exists():
            return "No sms_service.py found."

        text = filepath.read_text(errors="replace")
        funcs = [f"  L{i}: {l.strip()}" for i, l in enumerate(text.split("\n"), 1)
                 if l.strip().startswith("def ") or l.strip().startswith("async def ")]
        return f"SMS Service ({filepath.stat().st_size / 1024:.1f} KB):\n" + "\n".join(funcs)

    @mcp.tool()
    def get_voice_service_info() -> str:
        """Inspect the ElevenLabs voice service for outbound call dispatch."""
        repo = _ensure_cloned(config)
        if isinstance(repo, str):
            return repo

        filepath = repo / "app" / "services" / "voice_service.py"
        if not filepath.exists():
            return "No voice_service.py found."

        text = filepath.read_text(errors="replace")
        funcs = [f"  L{i}: {l.strip()}" for i, l in enumerate(text.split("\n"), 1)
                 if l.strip().startswith("def ") or l.strip().startswith("async def ")]
        return f"Voice Service ({filepath.stat().st_size / 1024:.1f} KB):\n" + "\n".join(funcs)

    # ── API Routers ────────────────────────────────────────────────────

    @mcp.tool()
    def list_workflow_endpoints() -> str:
        """List all API endpoints (workflows CRUD, contacts, webhooks)."""
        repo = _ensure_cloned(config)
        if isinstance(repo, str):
            return repo

        routers_dir = repo / "app" / "routers"
        results = []
        if routers_dir.is_dir():
            for f in sorted(routers_dir.rglob("*.py")):
                if f.name == "__init__.py":
                    continue
                text = f.read_text(errors="replace")
                for i, line in enumerate(text.split("\n"), 1):
                    stripped = line.strip()
                    for dec in ["@router.get", "@router.post", "@router.put", "@router.delete", "@router.patch"]:
                        if stripped.startswith(dec):
                            results.append(f"  {f.name}:L{i} {stripped}")

        return f"Endpoints ({len(results)}):\n" + "\n".join(results) if results else "No endpoints found."

    # ── Webhook Handlers ───────────────────────────────────────────────

    @mcp.tool()
    def get_webhook_handlers() -> str:
        """Inspect webhook handlers for email/SMS/voice response tracking."""
        repo = _ensure_cloned(config)
        if isinstance(repo, str):
            return repo

        filepath = repo / "app" / "routers" / "webhooks.py"
        if not filepath.exists():
            return "No webhooks.py found."

        text = filepath.read_text(errors="replace")
        results = []
        for i, line in enumerate(text.split("\n"), 1):
            stripped = line.strip()
            if (stripped.startswith("def ") or stripped.startswith("async def ") or
                    stripped.startswith("@router.")):
                results.append(f"  L{i}: {stripped}")

        return f"Webhook Handlers ({filepath.stat().st_size / 1024:.1f} KB):\n" + "\n".join(results)

    # ── Contact Models ─────────────────────────────────────────────────

    @mcp.tool()
    def get_contact_models() -> str:
        """Inspect Contact and Vehicle Pydantic models."""
        repo = _ensure_cloned(config)
        if isinstance(repo, str):
            return repo

        filepath = repo / "app" / "models" / "contact.py"
        if not filepath.exists():
            return "No contact.py model found."

        return filepath.read_text(errors="replace")

    # ── Configuration ──────────────────────────────────────────────────

    @mcp.tool()
    def get_workflow_config() -> str:
        """Read app configuration (app/core/config.py, env.example)."""
        repo = _ensure_cloned(config)
        if isinstance(repo, str):
            return repo

        results = []
        for path in ["app/core/config.py", "env.example", ".env.example"]:
            filepath = repo / path
            if filepath.exists():
                results.append(f"=== {path} ===\n{filepath.read_text(errors='replace')}")

        return "\n\n".join(results) if results else "No config files found."

    # ── Deployment ─────────────────────────────────────────────────────

    @mcp.tool()
    def get_workflow_deployment_info() -> str:
        """Get deployment configuration (Dockerfile, deploy.sh, requirements)."""
        repo = _ensure_cloned(config)
        if isinstance(repo, str):
            return repo

        results = []
        for f_name in ["Dockerfile", "deploy.sh", "requirements.txt"]:
            filepath = repo / f_name
            if filepath.exists():
                text = filepath.read_text(errors="replace")
                results.append(f"=== {f_name} ===\n{text[:3000]}")

        return "\n\n".join(results) if results else "No deployment files found."

    # ── Firestore Collections ──────────────────────────────────────────

    @mcp.tool()
    def get_workflow_firestore_collections() -> str:
        """Discover Firestore collections used by the workflow builder."""
        repo = _ensure_cloned(config)
        if isinstance(repo, str):
            return repo

        result = subprocess.run(
            ["grep", "-rn", "--include=*.py", r"collection(", str(repo)],
            capture_output=True, text=True,
        )

        collections = set()
        for line in result.stdout.split("\n"):
            matches = re.findall(r'collection\(["\']([^"\']+)["\']\)', line)
            collections.update(matches)

        if not collections:
            return "No Firestore collection references found."

        return f"Collections ({len(collections)}):\n" + "\n".join(f"  {c}" for c in sorted(collections))
