import json
import re
import subprocess
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from src.config import Config

REPO_NAME = "chatbot-backend"


def _ensure_cloned(config: Config) -> Path | str:
    p = config.get_repo_path(REPO_NAME)
    if not p.is_dir():
        return f"Error: chatbot-backend not cloned. Use clone_repo('{REPO_NAME}') first."
    return p


def register_chatbot_backend_tools(mcp: FastMCP, config: Config):

    # ── Store / Dealership Handlers ────────────────────────────────────

    @mcp.tool()
    def list_chatbot_stores() -> str:
        """List all dealership store handler files (app/stores/)."""
        repo = _ensure_cloned(config)
        if isinstance(repo, str):
            return repo

        stores_dir = repo / "app" / "stores"
        results = []
        if stores_dir.is_dir():
            for f in sorted(stores_dir.rglob("*.py")):
                if f.name == "__init__.py":
                    continue
                size_kb = f.stat().st_size / 1024
                results.append(f"  {f.name} ({size_kb:.1f} KB)")

        return f"Store handlers ({len(results)}):\n" + "\n".join(results) if results else "No store handlers found."

    @mcp.tool()
    def get_dealership_config_json() -> str:
        """Read the dealership configuration JSON (app/dealership_config.json)."""
        repo = _ensure_cloned(config)
        if isinstance(repo, str):
            return repo

        for path in [repo / "app" / "dealership_config.json", repo / "app" / "config" / "dealership_config.json"]:
            if path.exists():
                return path.read_text(errors="replace")

        return "No dealership_config.json found."

    # ── Prompt Management ──────────────────────────────────────────────

    @mcp.tool()
    def list_chatbot_prompts() -> str:
        """List all system prompt files (app/prompts/*.txt)."""
        repo = _ensure_cloned(config)
        if isinstance(repo, str):
            return repo

        prompts_dir = repo / "app" / "prompts"
        results = []
        if prompts_dir.is_dir():
            for f in sorted(prompts_dir.iterdir()):
                if f.is_file():
                    results.append(f"  {f.name} ({f.stat().st_size / 1024:.1f} KB)")

        return f"Prompt files ({len(results)}):\n" + "\n".join(results) if results else "No prompts directory found."

    @mcp.tool()
    def read_chatbot_prompt(prompt_file: str) -> str:
        """Read a specific system prompt file.

        Args:
            prompt_file: Filename (e.g. 'dealership_001.txt') or full relative path
        """
        repo = _ensure_cloned(config)
        if isinstance(repo, str):
            return repo

        # Try direct path first, then prompts dir
        for candidate in [repo / prompt_file, repo / "app" / "prompts" / prompt_file]:
            if candidate.exists():
                return candidate.read_text(errors="replace")

        return f"Error: Prompt file '{prompt_file}' not found."

    # ── OpenAI Tool Definitions ────────────────────────────────────────

    @mcp.tool()
    def list_chatbot_tools() -> str:
        """List OpenAI function-call tool implementations (app/tools/)."""
        repo = _ensure_cloned(config)
        if isinstance(repo, str):
            return repo

        tools_dir = repo / "app" / "tools"
        results = []
        if tools_dir.is_dir():
            for f in sorted(tools_dir.rglob("*.py")):
                if f.name == "__init__.py":
                    continue
                text = f.read_text(errors="replace")
                funcs = []
                for line in text.split("\n"):
                    stripped = line.strip()
                    if stripped.startswith("def ") or stripped.startswith("async def "):
                        funcs.append(stripped.split("(")[0].replace("def ", "").replace("async ", ""))
                results.append(f"  {f.name} ({f.stat().st_size / 1024:.1f} KB): {', '.join(funcs)}")

        return f"Tool modules:\n" + "\n".join(results) if results else "No tools directory found."

    @mcp.tool()
    def get_tool_schema(tool_file: str) -> str:
        """Extract OpenAI function schemas/definitions from a tool file.

        Args:
            tool_file: Tool filename (e.g. 'sales.py') or relative path
        """
        repo = _ensure_cloned(config)
        if isinstance(repo, str):
            return repo

        for candidate in [repo / tool_file, repo / "app" / "tools" / tool_file]:
            if candidate.exists():
                text = candidate.read_text(errors="replace")
                # Look for function schema definitions
                schemas = re.findall(r'(\{[^}]*"name"\s*:\s*"[^"]+",\s*"description"[^}]*\})', text, re.DOTALL)
                if schemas:
                    return "Function schemas found:\n" + "\n---\n".join(schemas[:10])
                return text[:5000]

        return f"Error: Tool file '{tool_file}' not found."

    # ── Inventory / SQLite ─────────────────────────────────────────────

    @mcp.tool()
    def list_inventory_files() -> str:
        """List SQLite database files and inventory-related modules."""
        repo = _ensure_cloned(config)
        if isinstance(repo, str):
            return repo

        results = []
        # SQLite files
        for f in repo.rglob("*.db"):
            if ".git" not in f.parts:
                results.append(f"  [db] {f.relative_to(repo)} ({f.stat().st_size / 1024:.1f} KB)")

        # Inventory modules
        for pattern in ["*inventory*", "*vehicle_filter*", "*car_inventory*"]:
            for f in repo.rglob(pattern):
                if ".git" not in f.parts and f.suffix == ".py":
                    results.append(f"  [py] {f.relative_to(repo)} ({f.stat().st_size / 1024:.1f} KB)")

        return f"Inventory files:\n" + "\n".join(results) if results else "No inventory files found."

    @mcp.tool()
    def get_inventory_schema() -> str:
        """Extract SQL table schema from inventory processor code."""
        repo = _ensure_cloned(config)
        if isinstance(repo, str):
            return repo

        result = subprocess.run(
            ["grep", "-rn", "--include=*.py",
             r"CREATE TABLE\|INSERT INTO\|SELECT.*FROM\|inventory.*table\|\.execute(",
             str(repo)],
            capture_output=True, text=True,
        )
        output = result.stdout.replace(str(repo) + "/", "")
        lines = output.strip().split("\n")
        return "\n".join(lines[:50]) if output.strip() else "No SQL references found."

    # ── Cron Jobs / Inventory Sync ─────────────────────────────────────

    @mcp.tool()
    def list_chatbot_cron_jobs() -> str:
        """List inventory sync cron job scripts (cron_job/)."""
        repo = _ensure_cloned(config)
        if isinstance(repo, str):
            return repo

        cron_dir = repo / "cron_job"
        results = []
        if cron_dir.is_dir():
            for f in sorted(cron_dir.rglob("*.py")):
                size_kb = f.stat().st_size / 1024
                results.append(f"  {f.relative_to(repo)} ({size_kb:.1f} KB)")

        return f"Cron jobs:\n" + "\n".join(results) if results else "No cron_job directory found."

    # ── API Endpoints ──────────────────────────────────────────────────

    @mcp.tool()
    def list_chatbot_endpoints() -> str:
        """List all API endpoints in the chatbot backend."""
        repo = _ensure_cloned(config)
        if isinstance(repo, str):
            return repo

        results = []
        for py_file in sorted(repo.rglob("*.py")):
            if ".git" in py_file.parts or py_file.name == "__init__.py":
                continue
            text = py_file.read_text(errors="replace")
            for i, line in enumerate(text.split("\n"), 1):
                stripped = line.strip()
                for dec in ["@app.get", "@app.post", "@app.put", "@app.delete",
                            "@router.get", "@router.post", "@router.put", "@router.delete"]:
                    if stripped.startswith(dec):
                        results.append(f"  {py_file.relative_to(repo)}:L{i} {stripped}")

        return f"Endpoints ({len(results)}):\n" + "\n".join(results) if results else "No endpoints found."

    # ── Pydantic Models ────────────────────────────────────────────────

    @mcp.tool()
    def list_chatbot_models() -> str:
        """List Pydantic data models (app/models/)."""
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
                classes = [l.strip().split("(")[0].replace("class ", "")
                           for l in text.split("\n") if l.strip().startswith("class ")]
                results.append(f"  {f.name}: {', '.join(classes)}")

        return f"Models:\n" + "\n".join(results) if results else "No models directory found."

    # ── Utilities ──────────────────────────────────────────────────────

    @mcp.tool()
    def list_chatbot_utils() -> str:
        """List utility modules (embeddings, calendar, summarization, etc.)."""
        repo = _ensure_cloned(config)
        if isinstance(repo, str):
            return repo

        utils_dir = repo / "app" / "utils"
        results = []
        if utils_dir.is_dir():
            for f in sorted(utils_dir.rglob("*.py")):
                if f.name == "__init__.py":
                    continue
                size_kb = f.stat().st_size / 1024
                text = f.read_text(errors="replace")
                funcs = [l.strip().split("(")[0].replace("def ", "").replace("async ", "")
                         for l in text.split("\n")
                         if l.strip().startswith("def ") or l.strip().startswith("async def ")]
                results.append(f"  {f.name} ({size_kb:.1f} KB): {', '.join(funcs[:6])}")

        return f"Utilities:\n" + "\n".join(results) if results else "No utils directory found."

    # ── Deployment ─────────────────────────────────────────────────────

    @mcp.tool()
    def get_chatbot_deployment_info() -> str:
        """Get deployment configuration (Dockerfile, deploy scripts, requirements, GCE setup)."""
        repo = _ensure_cloned(config)
        if isinstance(repo, str):
            return repo

        results = []
        for f_name in ["dockerfile", "Dockerfile", "requirements.txt", "run.py", "run-local.sh", "wsgi.py"]:
            filepath = repo / f_name
            if filepath.exists():
                text = filepath.read_text(errors="replace")
                results.append(f"=== {f_name} ===\n{text[:3000]}")

        # GCE deployment
        gce_dir = repo / "gce-deployment"
        if gce_dir.is_dir():
            for f in sorted(gce_dir.iterdir()):
                if f.is_file():
                    results.append(f"=== gce-deployment/{f.name} ===\n{f.read_text(errors='replace')[:2000]}")

        return "\n\n".join(results) if results else "No deployment files found."

    # ── External API Integrations ──────────────────────────────────────

    @mcp.tool()
    def get_chatbot_external_apis() -> str:
        """Discover external API integrations (XTime, Autoloop, Dealer Inspire, etc.)."""
        repo = _ensure_cloned(config)
        if isinstance(repo, str):
            return repo

        result = subprocess.run(
            ["grep", "-rn", "--include=*.py",
             r"xtime\|autoloop\|dealer.inspire\|VOICE_ENDPOINT\|FIREBASE_ENDPOINT",
             str(repo)],
            capture_output=True, text=True,
        )
        output = result.stdout.replace(str(repo) + "/", "")
        lines = output.strip().split("\n")
        return f"External API references:\n" + "\n".join(lines[:40]) if output.strip() else "No external API references found."
