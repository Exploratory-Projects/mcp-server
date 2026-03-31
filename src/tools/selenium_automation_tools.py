import json
import re
import subprocess
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from src.config import Config

REPO_NAME = "selinium-browser-automation"


def _ensure_cloned(config: Config) -> Path | str:
    p = config.get_repo_path(REPO_NAME)
    if not p.is_dir():
        return f"Error: selinium-browser-automation not cloned. Use clone_repo('{REPO_NAME}') first."
    return p


def register_selenium_automation_tools(mcp: FastMCP, config: Config):

    # ── Dealership Module Inspection ───────────────────────────────────

    @mcp.tool()
    def list_dealership_modules() -> str:
        """List all dealership-specific automation modules (modules/dealerships/, modules/bayside_volkswagen/, etc.)."""
        repo = _ensure_cloned(config)
        if isinstance(repo, str):
            return repo

        results = []
        modules_dir = repo / "modules"
        if modules_dir.is_dir():
            for d in sorted(modules_dir.iterdir()):
                if d.is_dir() and d.name != "__pycache__":
                    files = list(d.rglob("*.py"))
                    results.append(f"  {d.name}/ ({len(files)} Python files)")
                    for f in sorted(files)[:10]:
                        if f.name != "__init__.py":
                            results.append(f"    {f.name} ({f.stat().st_size / 1024:.1f} KB)")

        return f"Dealership modules:\n" + "\n".join(results) if results else "No dealership modules found."

    @mcp.tool()
    def get_dealership_config() -> str:
        """Get dealership ID to URL mappings from precision_automations/config.py."""
        repo = _ensure_cloned(config)
        if isinstance(repo, str):
            return repo

        config_file = repo / "precision_automations" / "config.py"
        if not config_file.exists():
            return "No precision_automations/config.py found."

        return config_file.read_text(errors="replace")

    # ── Automation Flow Inspection ─────────────────────────────────────

    @mcp.tool()
    def list_automation_flows() -> str:
        """List all automation flow files (step modules, flow orchestrators)."""
        repo = _ensure_cloned(config)
        if isinstance(repo, str):
            return repo

        results = []

        # Precision automations
        precision_dir = repo / "precision_automations"
        if precision_dir.is_dir():
            results.append("=== Precision Automations ===")
            for f in sorted(precision_dir.rglob("*.py")):
                if f.name != "__init__.py":
                    results.append(f"  {f.relative_to(repo)} ({f.stat().st_size / 1024:.1f} KB)")

        # Classic modules
        modules_dir = repo / "modules"
        if modules_dir.is_dir():
            results.append("\n=== Classic Modules ===")
            for f in sorted(modules_dir.rglob("*.py")):
                if f.name != "__init__.py" and "pycache" not in str(f):
                    results.append(f"  {f.relative_to(repo)} ({f.stat().st_size / 1024:.1f} KB)")

        return "\n".join(results) if results else "No automation flows found."

    @mcp.tool()
    def get_automation_steps(flow_path: str) -> str:
        """Extract step functions and Selenium selectors from an automation flow file.

        Args:
            flow_path: Relative path to the flow file (e.g. 'precision_automations/flow.py')
        """
        repo = _ensure_cloned(config)
        if isinstance(repo, str):
            return repo

        filepath = repo / flow_path
        if not filepath.exists():
            return f"Error: {flow_path} not found."

        text = filepath.read_text(errors="replace")
        results = []

        # Extract function definitions
        for i, line in enumerate(text.split("\n"), 1):
            stripped = line.strip()
            if stripped.startswith("def ") or stripped.startswith("async def "):
                results.append(f"  L{i}: {stripped.split(':')[0]}")

        # Extract CSS/XPath selectors
        selectors = set()
        for match in re.findall(r'By\.\w+,\s*["\']([^"\']+)["\']', text):
            selectors.add(match)
        for match in re.findall(r'find_element[s]?\([^)]*["\']([^"\']+)["\']', text):
            selectors.add(match)

        output = f"Functions in {flow_path}:\n" + "\n".join(results)
        if selectors:
            output += f"\n\nSelectors ({len(selectors)}):\n" + "\n".join(f"  {s}" for s in sorted(selectors))
        return output

    # ── API Endpoints ──────────────────────────────────────────────────

    @mcp.tool()
    def list_selenium_endpoints() -> str:
        """List all API endpoints defined in main.py."""
        repo = _ensure_cloned(config)
        if isinstance(repo, str):
            return repo

        main_file = repo / "main.py"
        if not main_file.exists():
            return "No main.py found."

        text = main_file.read_text(errors="replace")
        results = []
        for i, line in enumerate(text.split("\n"), 1):
            stripped = line.strip()
            for dec in ["@app.get", "@app.post", "@app.put", "@app.delete", "@router.get", "@router.post"]:
                if stripped.startswith(dec):
                    results.append(f"  L{i}: {stripped}")

        return f"Endpoints:\n" + "\n".join(results) if results else "No endpoints found."

    # ── PagerDuty Integration ──────────────────────────────────────────

    @mcp.tool()
    def get_pagerduty_config() -> str:
        """Inspect PagerDuty alerting integration for automation failures."""
        repo = _ensure_cloned(config)
        if isinstance(repo, str):
            return repo

        results = []
        for pattern in ["*pagerduty*", "*pager_duty*"]:
            for f in sorted(repo.rglob(pattern)):
                if ".git" not in f.parts and f.suffix == ".py":
                    results.append(f"=== {f.relative_to(repo)} ===\n{f.read_text(errors='replace')[:3000]}")

        return "\n\n".join(results) if results else "No PagerDuty integration found."

    # ── Cloud Tasks / GCP Configuration ────────────────────────────────

    @mcp.tool()
    def get_cloud_tasks_config() -> str:
        """Inspect Google Cloud Tasks queue configuration and task creation logic."""
        repo = _ensure_cloned(config)
        if isinstance(repo, str):
            return repo

        result = subprocess.run(
            ["grep", "-rn", "--include=*.py", "-i", "cloud.tasks\|CloudTasksClient\|create_task\|enqueue", str(repo)],
            capture_output=True, text=True,
        )
        output = result.stdout.replace(str(repo) + "/", "")
        return output.strip() if output.strip() else "No Cloud Tasks references found."

    @mcp.tool()
    def get_gcp_deployment_scripts() -> str:
        """Read all GCP deployment and infrastructure scripts (.sh files)."""
        repo = _ensure_cloned(config)
        if isinstance(repo, str):
            return repo

        results = []
        for f in sorted(repo.glob("*.sh")):
            results.append(f"=== {f.name} ===\n{f.read_text(errors='replace')}")

        return "\n\n".join(results) if results else "No shell scripts found."

    # ── Selenium / Chrome Configuration ────────────────────────────────

    @mcp.tool()
    def get_chrome_driver_config() -> str:
        """Inspect Chrome/ChromeDriver configuration, options, and stealth settings."""
        repo = _ensure_cloned(config)
        if isinstance(repo, str):
            return repo

        result = subprocess.run(
            ["grep", "-rn", "--include=*.py",
             r"ChromeOptions\|webdriver\.Chrome\|stealth\|undetected\|pyvirtualdisplay\|chrome_options",
             str(repo)],
            capture_output=True, text=True,
        )
        output = result.stdout.replace(str(repo) + "/", "")
        return f"Chrome/Driver config references:\n{output}" if output.strip() else "No Chrome config found."

    # ── Deployment ─────────────────────────────────────────────────────

    @mcp.tool()
    def get_selenium_deployment_info() -> str:
        """Get deployment configuration (Dockerfile, deploy scripts, requirements)."""
        repo = _ensure_cloned(config)
        if isinstance(repo, str):
            return repo

        results = []
        for f_name in ["Dockerfile", "deploy_cloud_run.sh", "requirements.txt", "create_secrets.sh", "fix_cloud_tasks_permissions.sh"]:
            filepath = repo / f_name
            if filepath.exists():
                text = filepath.read_text(errors="replace")
                results.append(f"=== {f_name} ===\n{text[:3000]}")

        return "\n\n".join(results) if results else "No deployment files found."

    # ── Archived Code ──────────────────────────────────────────────────

    @mcp.tool()
    def list_archived_code() -> str:
        """List files in the archived[do-not-delete]/ directory."""
        repo = _ensure_cloned(config)
        if isinstance(repo, str):
            return repo

        results = []
        for d in repo.iterdir():
            if d.is_dir() and "archived" in d.name.lower():
                for f in sorted(d.rglob("*")):
                    if f.is_file() and ".git" not in f.parts:
                        results.append(f"  {f.relative_to(repo)} ({f.stat().st_size / 1024:.1f} KB)")

        return f"Archived files:\n" + "\n".join(results) if results else "No archived directory found."

    # ── XTime Integration ──────────────────────────────────────────────

    @mcp.tool()
    def get_xtime_urls() -> str:
        """Extract Xtime consumer URLs configured for each dealership."""
        repo = _ensure_cloned(config)
        if isinstance(repo, str):
            return repo

        results = []
        for f in repo.rglob("*.py"):
            if ".git" in f.parts:
                continue
            text = f.read_text(errors="replace")
            urls = re.findall(r'https?://[^\s"\']+xtime[^\s"\']*', text, re.IGNORECASE)
            for url in urls:
                results.append(f"  {f.relative_to(repo)}: {url}")

        return f"XTime URLs:\n" + "\n".join(set(results)) if results else "No XTime URLs found."
