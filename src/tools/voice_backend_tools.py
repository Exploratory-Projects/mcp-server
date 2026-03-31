import json
import subprocess
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from src.config import Config

REPO_NAME = "voice-backend-v2"


def _repo_path(config: Config) -> Path:
    return config.get_repo_path(REPO_NAME)


def _ensure_cloned(config: Config) -> Path | str:
    p = _repo_path(config)
    if not p.is_dir():
        return f"Error: voice-backend-v2 not cloned. Use clone_repo('{REPO_NAME}') first."
    return p


def register_voice_backend_tools(mcp: FastMCP, config: Config):

    # ── Prompt Management ──────────────────────────────────────────────

    @mcp.tool()
    def list_voice_prompts() -> str:
        """List all LLM system prompts defined in the voice backend.
        Scans app/utils/prompts.py and any .txt prompt files."""
        repo = _ensure_cloned(config)
        if isinstance(repo, str):
            return repo

        results = []
        prompts_file = repo / "app" / "utils" / "prompts.py"
        if prompts_file.exists():
            text = prompts_file.read_text(errors="replace")
            # Find all top-level string assignments (prompt variables)
            for line in text.split("\n"):
                stripped = line.strip()
                if "=" in stripped and not stripped.startswith("#"):
                    var_name = stripped.split("=")[0].strip()
                    if var_name.isupper() or "prompt" in var_name.lower() or "system" in var_name.lower():
                        results.append(f"  {var_name} (in app/utils/prompts.py)")

        # Also check for .txt prompt files
        for txt in sorted(repo.rglob("*.txt")):
            if ".git" not in txt.parts and "prompt" in txt.name.lower():
                results.append(f"  {txt.relative_to(repo)}")

        return f"Found {len(results)} prompts:\n" + "\n".join(results) if results else "No prompts found."

    @mcp.tool()
    def read_voice_prompt(prompt_var: str) -> str:
        """Read a specific prompt variable from app/utils/prompts.py.

        Args:
            prompt_var: Variable name of the prompt (e.g. 'SEARCH_AGENT_SYSTEM_PROMPT')
        """
        repo = _ensure_cloned(config)
        if isinstance(repo, str):
            return repo

        prompts_file = repo / "app" / "utils" / "prompts.py"
        if not prompts_file.exists():
            return "Error: app/utils/prompts.py not found"

        text = prompts_file.read_text(errors="replace")
        # Find the variable assignment
        lines = text.split("\n")
        start_idx = None
        for i, line in enumerate(lines):
            if line.strip().startswith(f"{prompt_var}"):
                start_idx = i
                break

        if start_idx is None:
            return f"Error: Prompt variable '{prompt_var}' not found"

        # Extract until next top-level assignment or end
        extracted = [lines[start_idx]]
        for i in range(start_idx + 1, len(lines)):
            line = lines[i]
            # New top-level variable
            if line and not line[0].isspace() and "=" in line and not line.startswith("#"):
                break
            extracted.append(line)

        return "\n".join(extracted)

    # ── Agent Management ───────────────────────────────────────────────

    @mcp.tool()
    def list_voice_agents() -> str:
        """List all AI agent files in the voice backend (app/agents/)."""
        repo = _ensure_cloned(config)
        if isinstance(repo, str):
            return repo

        agents_dir = repo / "app" / "agents"
        if not agents_dir.is_dir():
            return "No agents directory found."

        results = []
        for f in sorted(agents_dir.rglob("*.py")):
            if f.name == "__init__.py":
                continue
            size_kb = f.stat().st_size / 1024
            results.append(f"  {f.relative_to(repo)} ({size_kb:.1f} KB)")

        return f"Agents ({len(results)}):\n" + "\n".join(results)

    @mcp.tool()
    def get_voice_agent_tools(agent_file: str) -> str:
        """Extract tool/function definitions from a voice agent file.

        Args:
            agent_file: Relative path to agent file (e.g. 'app/agents/alpha_search_agent.py')
        """
        repo = _ensure_cloned(config)
        if isinstance(repo, str):
            return repo

        filepath = repo / agent_file
        if not filepath.exists():
            return f"Error: {agent_file} not found"

        text = filepath.read_text(errors="replace")
        functions = []
        for i, line in enumerate(text.split("\n"), 1):
            stripped = line.strip()
            if stripped.startswith("def ") or stripped.startswith("async def "):
                functions.append(f"  L{i}: {stripped.split('(')[0].replace('def ', '').replace('async ', '')}")

        return f"Functions in {agent_file}:\n" + "\n".join(functions) if functions else "No functions found."

    # ── Vehicle Data ───────────────────────────────────────────────────

    @mcp.tool()
    def list_vehicle_models() -> str:
        """List all vehicle model JSON data files in the voice backend."""
        repo = _ensure_cloned(config)
        if isinstance(repo, str):
            return repo

        results = []
        for f in sorted(repo.glob("*_models.json")):
            size_kb = f.stat().st_size / 1024
            try:
                data = json.loads(f.read_text())
                count = len(data) if isinstance(data, list) else "N/A"
            except Exception:
                count = "parse error"
            results.append(f"  {f.name} ({size_kb:.1f} KB, {count} entries)")

        return f"Vehicle data files:\n" + "\n".join(results) if results else "No vehicle model files found."

    @mcp.tool()
    def query_vehicle_models(brand: str, search_term: str = "") -> str:
        """Query vehicle model data from a brand's JSON file.

        Args:
            brand: Brand name (honda, acura, mercedes, volkswagen, volvo)
            search_term: Optional text to filter results
        """
        repo = _ensure_cloned(config)
        if isinstance(repo, str):
            return repo

        json_file = repo / f"{brand.lower()}_models.json"
        if not json_file.exists():
            available = [f.stem.replace("_models", "") for f in repo.glob("*_models.json")]
            return f"Error: No data for '{brand}'. Available: {available}"

        try:
            data = json.loads(json_file.read_text())
        except json.JSONDecodeError as e:
            return f"Error parsing JSON: {e}"

        if search_term and isinstance(data, list):
            filtered = [item for item in data if search_term.lower() in json.dumps(item).lower()]
            return json.dumps(filtered[:20], indent=2)

        if isinstance(data, list):
            return json.dumps(data[:20], indent=2) + f"\n\n... ({len(data)} total entries)"
        return json.dumps(data, indent=2)[:5000]

    # ── API Endpoints ──────────────────────────────────────────────────

    @mcp.tool()
    def list_voice_endpoints() -> str:
        """List all API endpoints defined in the voice backend."""
        repo = _ensure_cloned(config)
        if isinstance(repo, str):
            return repo

        results = []
        endpoints_dir = repo / "app" / "api" / "endpoints"
        if endpoints_dir.is_dir():
            for f in sorted(endpoints_dir.rglob("*.py")):
                if f.name == "__init__.py":
                    continue
                text = f.read_text(errors="replace")
                for line in text.split("\n"):
                    stripped = line.strip()
                    for decorator in ["@router.get", "@router.post", "@router.put", "@router.delete", "@router.patch", "@router.websocket"]:
                        if stripped.startswith(decorator):
                            results.append(f"  {f.name}: {stripped}")

        # Also check main.py
        main_file = repo / "app" / "main.py"
        if main_file.exists():
            text = main_file.read_text(errors="replace")
            for line in text.split("\n"):
                stripped = line.strip()
                if "include_router" in stripped or "app.add_api_route" in stripped:
                    results.append(f"  main.py: {stripped}")

        return f"Endpoints:\n" + "\n".join(results) if results else "No endpoints found."

    # ── Service Center Data ────────────────────────────────────────────

    @mcp.tool()
    def list_service_center_data() -> str:
        """List service center knowledge base files used by voice agents."""
        repo = _ensure_cloned(config)
        if isinstance(repo, str):
            return repo

        results = []
        for pattern in ["**/service-center-data/**", "**/service_center*"]:
            for f in sorted(repo.glob(pattern)):
                if ".git" not in f.parts:
                    results.append(f"  {f.relative_to(repo)} ({f.stat().st_size / 1024:.1f} KB)")

        return f"Service center data:\n" + "\n".join(results) if results else "No service center data found."

    # ── Config & Environment ───────────────────────────────────────────

    @mcp.tool()
    def get_voice_config() -> str:
        """Read the voice backend configuration (config.py, env template, Docker settings)."""
        repo = _ensure_cloned(config)
        if isinstance(repo, str):
            return repo

        results = []
        for config_file in ["app/config.py", ".env.example", ".env.template", "env.example"]:
            filepath = repo / config_file
            if filepath.exists():
                text = filepath.read_text(errors="replace")
                results.append(f"=== {config_file} ===\n{text[:3000]}")

        return "\n\n".join(results) if results else "No config files found."

    # ── Deployment ─────────────────────────────────────────────────────

    @mcp.tool()
    def get_voice_deployment_info() -> str:
        """Get deployment configuration (Dockerfile, deploy scripts, requirements)."""
        repo = _ensure_cloned(config)
        if isinstance(repo, str):
            return repo

        results = []
        for f_name in ["Dockerfile", "deploy.sh", "requirements.txt", "docker-compose.yml", "deployment.txt"]:
            filepath = repo / f_name
            if filepath.exists():
                text = filepath.read_text(errors="replace")
                results.append(f"=== {f_name} ===\n{text[:3000]}")

        return "\n\n".join(results) if results else "No deployment files found."

    @mcp.tool()
    def run_voice_backend_tests() -> str:
        """Run tests for the voice backend if any exist."""
        repo = _ensure_cloned(config)
        if isinstance(repo, str):
            return repo

        # Check for test files
        test_files = list(repo.rglob("test_*.py")) + list(repo.rglob("*_test.py"))
        tests_dir = repo / "tests"

        if not test_files and not tests_dir.exists():
            return "No test files found in the voice backend."

        result = subprocess.run(
            ["python", "-m", "pytest", "-v", "--tb=short"],
            cwd=str(repo), capture_output=True, text=True, timeout=120,
        )
        return result.stdout + result.stderr

    # ── XTime Integration ──────────────────────────────────────────────

    @mcp.tool()
    def get_xtime_integration_info() -> str:
        """Get info about XTime dealership scheduling integration files."""
        repo = _ensure_cloned(config)
        if isinstance(repo, str):
            return repo

        results = []
        for f in sorted(repo.rglob("*xtime*")):
            if ".git" not in f.parts:
                size_kb = f.stat().st_size / 1024
                results.append(f"  {f.relative_to(repo)} ({size_kb:.1f} KB)")

        return f"XTime integration files:\n" + "\n".join(results) if results else "No XTime files found."

    # ── Notification & Integration Services ────────────────────────────

    @mcp.tool()
    def list_voice_services() -> str:
        """List all service modules (notifications, monitoring, PagerDuty, etc.)."""
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
                results.append(f"  {f.relative_to(repo)} ({size_kb:.1f} KB)")

        return f"Services:\n" + "\n".join(results) if results else "No services directory found."
