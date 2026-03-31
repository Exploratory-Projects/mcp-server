import json
import subprocess
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from src.config import Config

REPO_NAME = "admin-dashboard"


def _repo_path(config: Config) -> Path:
    return config.get_repo_path(REPO_NAME)


def _ensure_cloned(config: Config) -> Path | str:
    p = _repo_path(config)
    if not p.is_dir():
        return f"Error: admin-dashboard not cloned. Use clone_repo('{REPO_NAME}') first."
    return p


def register_admin_dashboard_tools(mcp: FastMCP, config: Config):

    # ── API Module Inspection ──────────────────────────────────────────

    @mcp.tool()
    def list_admin_api_modules() -> str:
        """List all API modules in the admin dashboard (api/, jobs/, webhook_events/, etc.)."""
        repo = _ensure_cloned(config)
        if isinstance(repo, str):
            return repo

        results = []
        for dir_name in ["api", "jobs", "webhook_events", "customer_apis", "nondealership_customer_apis", "weekly_report_apis"]:
            dir_path = repo / dir_name
            if dir_path.is_dir():
                files = sorted(f for f in dir_path.rglob("*.py") if f.name != "__init__.py")
                for f in files:
                    size_kb = f.stat().st_size / 1024
                    results.append(f"  [{dir_name}] {f.relative_to(repo)} ({size_kb:.1f} KB)")

        return f"API modules ({len(results)}):\n" + "\n".join(results) if results else "No API modules found."

    @mcp.tool()
    def list_admin_endpoints(module: str = "") -> str:
        """List all FastAPI route definitions. Optionally filter by module name.

        Args:
            module: Optional module name to filter (e.g. 'conversations', 'tasks')
        """
        repo = _ensure_cloned(config)
        if isinstance(repo, str):
            return repo

        results = []
        for py_file in sorted(repo.rglob("*.py")):
            if ".git" in py_file.parts or py_file.name == "__init__.py":
                continue
            if module and module.lower() not in py_file.name.lower():
                continue

            text = py_file.read_text(errors="replace")
            for i, line in enumerate(text.split("\n"), 1):
                stripped = line.strip()
                for decorator in ["@router.get", "@router.post", "@router.put", "@router.delete", "@router.patch"]:
                    if stripped.startswith(decorator):
                        results.append(f"  {py_file.relative_to(repo)}:L{i} {stripped}")

        return f"Endpoints ({len(results)}):\n" + "\n".join(results) if results else "No endpoints found."

    # ── Firestore Schema Inspection ────────────────────────────────────

    @mcp.tool()
    def get_firestore_collections() -> str:
        """Discover Firestore collection names referenced in the admin dashboard code."""
        repo = _ensure_cloned(config)
        if isinstance(repo, str):
            return repo

        result = subprocess.run(
            ["grep", "-rn", "--include=*.py", r"collection\|document\|\.collection(", str(repo)],
            capture_output=True, text=True,
        )

        collections = set()
        for line in result.stdout.split("\n"):
            # Extract collection names from .collection("name") patterns
            import re
            matches = re.findall(r'collection\(["\']([^"\']+)["\']\)', line)
            collections.update(matches)
            # Also .document("name")
            matches = re.findall(r'document\(["\']([^"\']+)["\']\)', line)
            collections.update(matches)

        if not collections:
            return "No Firestore collection references found."

        sorted_cols = sorted(collections)
        return f"Firestore collections referenced ({len(sorted_cols)}):\n" + "\n".join(f"  {c}" for c in sorted_cols)

    @mcp.tool()
    def get_firestore_indexes() -> str:
        """Read the Firestore composite index definitions (firestore.indexes.json)."""
        repo = _ensure_cloned(config)
        if isinstance(repo, str):
            return repo

        idx_file = repo / "firestore.indexes.json"
        if not idx_file.exists():
            return "No firestore.indexes.json found."

        return idx_file.read_text(errors="replace")

    # ── Campaign Management ────────────────────────────────────────────

    @mcp.tool()
    def get_campaign_config() -> str:
        """Inspect email and SMS campaign configuration and API integration details."""
        repo = _ensure_cloned(config)
        if isinstance(repo, str):
            return repo

        results = []
        for pattern in ["*email_campaign*", "*sms_campaign*", "*campaign*"]:
            for f in sorted(repo.rglob(pattern)):
                if ".git" not in f.parts and f.suffix in (".py", ".md", ".json"):
                    results.append(f"  {f.relative_to(repo)} ({f.stat().st_size / 1024:.1f} KB)")

        # Check docs
        docs_dir = repo / "docs"
        if docs_dir.is_dir():
            for f in sorted(docs_dir.iterdir()):
                if "campaign" in f.name.lower():
                    results.append(f"  {f.relative_to(repo)} ({f.stat().st_size / 1024:.1f} KB)")

        return f"Campaign-related files:\n" + "\n".join(results) if results else "No campaign files found."

    # ── Analytics & Snapshots ──────────────────────────────────────────

    @mcp.tool()
    def get_analytics_jobs() -> str:
        """List analytics/background job definitions (snapshot computation, RO processing, etc.)."""
        repo = _ensure_cloned(config)
        if isinstance(repo, str):
            return repo

        jobs_dir = repo / "jobs"
        results = []
        if jobs_dir.is_dir():
            for f in sorted(jobs_dir.rglob("*.py")):
                if f.name == "__init__.py":
                    continue
                text = f.read_text(errors="replace")
                funcs = [l.strip() for l in text.split("\n") if l.strip().startswith("def ") or l.strip().startswith("async def ")]
                results.append(f"  {f.relative_to(repo)} ({f.stat().st_size / 1024:.1f} KB)")
                for fn in funcs[:5]:
                    results.append(f"    {fn.split('(')[0]}")

        return f"Background jobs:\n" + "\n".join(results) if results else "No jobs directory found."

    # ── Webhook Events ─────────────────────────────────────────────────

    @mcp.tool()
    def get_webhook_handlers() -> str:
        """List webhook event handlers (Surge SMS, etc.)."""
        repo = _ensure_cloned(config)
        if isinstance(repo, str):
            return repo

        results = []
        webhook_dir = repo / "webhook_events"
        if webhook_dir.is_dir():
            for f in sorted(webhook_dir.rglob("*.py")):
                if f.name == "__init__.py":
                    continue
                size_kb = f.stat().st_size / 1024
                results.append(f"  {f.relative_to(repo)} ({size_kb:.1f} KB)")

        return f"Webhook handlers:\n" + "\n".join(results) if results else "No webhook handlers found."

    # ── Support Scripts ────────────────────────────────────────────────

    @mcp.tool()
    def list_admin_support_scripts() -> str:
        """List data migration and Firestore setup scripts (supportsscripts/)."""
        repo = _ensure_cloned(config)
        if isinstance(repo, str):
            return repo

        results = []
        scripts_dir = repo / "supportsscripts"
        if scripts_dir.is_dir():
            for f in sorted(scripts_dir.rglob("*.py")):
                results.append(f"  {f.relative_to(repo)} ({f.stat().st_size / 1024:.1f} KB)")

        return f"Support scripts:\n" + "\n".join(results) if results else "No support scripts found."

    # ── Scheduler Configuration ────────────────────────────────────────

    @mcp.tool()
    def get_scheduler_config() -> str:
        """Read Cloud Scheduler setup configuration (setup_scheduler.sh)."""
        repo = _ensure_cloned(config)
        if isinstance(repo, str):
            return repo

        scheduler_file = repo / "setup_scheduler.sh"
        if not scheduler_file.exists():
            return "No setup_scheduler.sh found."

        return scheduler_file.read_text(errors="replace")

    # ── Deployment ─────────────────────────────────────────────────────

    @mcp.tool()
    def get_admin_deployment_info() -> str:
        """Get deployment configuration (Dockerfile, deploy.sh, requirements)."""
        repo = _ensure_cloned(config)
        if isinstance(repo, str):
            return repo

        results = []
        for f_name in ["Dockerfile", "deploy.sh", "requirements.txt", "docker-compose.yml"]:
            filepath = repo / f_name
            if filepath.exists():
                text = filepath.read_text(errors="replace")
                results.append(f"=== {f_name} ===\n{text[:3000]}")

        return "\n\n".join(results) if results else "No deployment files found."

    # ── CLAUDE.md / Developer Guidance ─────────────────────────────────

    @mcp.tool()
    def get_admin_dev_guidance() -> str:
        """Read CLAUDE.md developer guidance if it exists."""
        repo = _ensure_cloned(config)
        if isinstance(repo, str):
            return repo

        claude_file = repo / "CLAUDE.md"
        if not claude_file.exists():
            return "No CLAUDE.md found."

        return claude_file.read_text(errors="replace")

    # ── Documentation ──────────────────────────────────────────────────

    @mcp.tool()
    def list_admin_docs() -> str:
        """List API documentation files in the docs/ directory."""
        repo = _ensure_cloned(config)
        if isinstance(repo, str):
            return repo

        docs_dir = repo / "docs"
        results = []
        if docs_dir.is_dir():
            for f in sorted(docs_dir.iterdir()):
                if f.is_file():
                    results.append(f"  {f.name} ({f.stat().st_size / 1024:.1f} KB)")

        return f"Documentation files:\n" + "\n".join(results) if results else "No docs directory found."

    @mcp.tool()
    def get_admin_utils() -> str:
        """Inspect utility modules (Firebase client, date helpers, etc.)."""
        repo = _ensure_cloned(config)
        if isinstance(repo, str):
            return repo

        utils_dir = repo / "utils"
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
                results.append(f"  {f.relative_to(repo)} ({size_kb:.1f} KB): {', '.join(funcs[:8])}")

        return f"Utilities:\n" + "\n".join(results) if results else "No utils directory found."
