import json
import re
import subprocess
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from src.config import Config

REPO_NAME = "firebase-backend"


def _ensure_cloned(config: Config) -> Path | str:
    p = config.get_repo_path(REPO_NAME)
    if not p.is_dir():
        return f"Error: firebase-backend not cloned. Use clone_repo('{REPO_NAME}') first."
    return p


def register_firebase_backend_tools(mcp: FastMCP, config: Config):

    # ── Router / API Inspection ────────────────────────────────────────

    @mcp.tool()
    def list_firebase_routers() -> str:
        """List all API router modules (app/routers/) with their endpoints."""
        repo = _ensure_cloned(config)
        if isinstance(repo, str):
            return repo

        routers_dir = repo / "app" / "routers"
        results = []
        if routers_dir.is_dir():
            for f in sorted(routers_dir.rglob("*.py")):
                if f.name == "__init__.py":
                    continue
                size_kb = f.stat().st_size / 1024
                text = f.read_text(errors="replace")
                endpoints = []
                for line in text.split("\n"):
                    stripped = line.strip()
                    for dec in ["@router.get", "@router.post", "@router.put", "@router.delete", "@router.patch"]:
                        if stripped.startswith(dec):
                            endpoints.append(stripped)

                results.append(f"  {f.name} ({size_kb:.1f} KB, {len(endpoints)} endpoints)")
                for ep in endpoints:
                    results.append(f"    {ep}")

        return f"Routers:\n" + "\n".join(results) if results else "No routers directory found."

    @mcp.tool()
    def get_firebase_router_detail(router_name: str) -> str:
        """Get detailed info about a specific router module including all function signatures.

        Args:
            router_name: Router filename (e.g. 'post_call.py', 'tasks.py')
        """
        repo = _ensure_cloned(config)
        if isinstance(repo, str):
            return repo

        filepath = repo / "app" / "routers" / router_name
        if not filepath.exists():
            return f"Error: Router '{router_name}' not found."

        text = filepath.read_text(errors="replace")
        results = []
        for i, line in enumerate(text.split("\n"), 1):
            stripped = line.strip()
            if (stripped.startswith("def ") or stripped.startswith("async def ") or
                    stripped.startswith("@router.")):
                results.append(f"  L{i}: {stripped}")

        return f"Router detail - {router_name}:\n" + "\n".join(results)

    # ── Pydantic Models ────────────────────────────────────────────────

    @mcp.tool()
    def list_firebase_models() -> str:
        """List all Pydantic data models (app/models/) with their class definitions."""
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
                classes = []
                for line in text.split("\n"):
                    if line.strip().startswith("class ") and "(" in line:
                        classes.append(line.strip().split("(")[0].replace("class ", ""))
                results.append(f"  {f.name} ({f.stat().st_size / 1024:.1f} KB): {', '.join(classes)}")

        return f"Models:\n" + "\n".join(results) if results else "No models directory found."

    @mcp.tool()
    def get_model_fields(model_file: str) -> str:
        """Extract Pydantic model class definitions with their fields.

        Args:
            model_file: Model filename (e.g. 'post_call.py', 'user.py')
        """
        repo = _ensure_cloned(config)
        if isinstance(repo, str):
            return repo

        filepath = repo / "app" / "models" / model_file
        if not filepath.exists():
            return f"Error: Model file '{model_file}' not found."

        text = filepath.read_text(errors="replace")
        results = []
        in_class = False
        current_class = ""
        for line in text.split("\n"):
            stripped = line.strip()
            if stripped.startswith("class "):
                in_class = True
                current_class = stripped
                results.append(f"\n{stripped}")
            elif in_class and ":" in stripped and not stripped.startswith("#") and not stripped.startswith("def "):
                if stripped and not stripped.startswith("\"\"\"") and not stripped.startswith("class "):
                    results.append(f"    {stripped}")
            elif in_class and stripped == "":
                in_class = False

        return "\n".join(results) if results else "No model classes found."

    # ── Firestore Collections ──────────────────────────────────────────

    @mcp.tool()
    def get_firebase_collections() -> str:
        """Discover all Firestore collection references in the codebase."""
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

        return f"Firestore collections ({len(collections)}):\n" + "\n".join(f"  {c}" for c in sorted(collections))

    # ── Core Configuration ─────────────────────────────────────────────

    @mcp.tool()
    def get_firebase_core_config() -> str:
        """Read core configuration files (app/core/config.py, firebase.py, logging_config.py)."""
        repo = _ensure_cloned(config)
        if isinstance(repo, str):
            return repo

        core_dir = repo / "app" / "core"
        results = []
        if core_dir.is_dir():
            for f in sorted(core_dir.rglob("*.py")):
                if f.name == "__init__.py":
                    continue
                results.append(f"=== {f.name} ===\n{f.read_text(errors='replace')}")

        return "\n\n".join(results) if results else "No core directory found."

    @mcp.tool()
    def get_firebase_env_template() -> str:
        """Read the environment variable template (env.example)."""
        repo = _ensure_cloned(config)
        if isinstance(repo, str):
            return repo

        for name in ["env.example", ".env.example", ".env.template"]:
            filepath = repo / name
            if filepath.exists():
                return f"=== {name} ===\n{filepath.read_text(errors='replace')}"

        return "No environment template found."

    # ── Email Utilities ────────────────────────────────────────────────

    @mcp.tool()
    def get_email_integration() -> str:
        """Inspect Gmail API integration code (app/utils/email.py, routers/email_campaigns.py)."""
        repo = _ensure_cloned(config)
        if isinstance(repo, str):
            return repo

        results = []
        for path in ["app/utils/email.py", "app/routers/email_campaigns.py"]:
            filepath = repo / path
            if filepath.exists():
                text = filepath.read_text(errors="replace")
                # Extract function signatures
                funcs = []
                for i, line in enumerate(text.split("\n"), 1):
                    stripped = line.strip()
                    if stripped.startswith("def ") or stripped.startswith("async def "):
                        funcs.append(f"  L{i}: {stripped.split(':')[0]}")
                results.append(f"=== {path} ({filepath.stat().st_size / 1024:.1f} KB) ===\n" + "\n".join(funcs))

        return "\n\n".join(results) if results else "No email integration files found."

    # ── Post-Call AI Processing ────────────────────────────────────────

    @mcp.tool()
    def get_post_call_processing_info() -> str:
        """Inspect the post-call AI processing pipeline (the largest and most complex module)."""
        repo = _ensure_cloned(config)
        if isinstance(repo, str):
            return repo

        results = []
        for path in ["app/routers/post_call.py", "app/models/post_call.py"]:
            filepath = repo / path
            if filepath.exists():
                text = filepath.read_text(errors="replace")
                funcs = []
                classes = []
                for i, line in enumerate(text.split("\n"), 1):
                    stripped = line.strip()
                    if stripped.startswith("def ") or stripped.startswith("async def "):
                        funcs.append(f"  L{i}: {stripped.split(':')[0]}")
                    elif stripped.startswith("class "):
                        classes.append(f"  L{i}: {stripped.split(':')[0]}")

                results.append(f"=== {path} ({filepath.stat().st_size / 1024:.1f} KB) ===")
                if classes:
                    results.append("Classes:\n" + "\n".join(classes))
                if funcs:
                    results.append("Functions:\n" + "\n".join(funcs))

        return "\n\n".join(results) if results else "No post-call files found."

    # ── Task Management ────────────────────────────────────────────────

    @mcp.tool()
    def get_task_management_info() -> str:
        """Inspect the task management module (routers/tasks.py, models/tasks.py)."""
        repo = _ensure_cloned(config)
        if isinstance(repo, str):
            return repo

        results = []
        for path in ["app/routers/tasks.py", "app/models/tasks.py"]:
            filepath = repo / path
            if filepath.exists():
                text = filepath.read_text(errors="replace")
                items = []
                for i, line in enumerate(text.split("\n"), 1):
                    stripped = line.strip()
                    if (stripped.startswith("def ") or stripped.startswith("async def ") or
                            stripped.startswith("class ") or stripped.startswith("@router.")):
                        items.append(f"  L{i}: {stripped}")

                results.append(f"=== {path} ({filepath.stat().st_size / 1024:.1f} KB) ===\n" + "\n".join(items))

        return "\n\n".join(results) if results else "No task management files found."

    # ── Deployment ─────────────────────────────────────────────────────

    @mcp.tool()
    def get_firebase_deployment_info() -> str:
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

    # ── Phone Utilities ────────────────────────────────────────────────

    @mcp.tool()
    def get_phone_utils() -> str:
        """Inspect phone number utility functions."""
        repo = _ensure_cloned(config)
        if isinstance(repo, str):
            return repo

        filepath = repo / "app" / "utils" / "phone.py"
        if not filepath.exists():
            return "No phone.py utility found."

        return filepath.read_text(errors="replace")
