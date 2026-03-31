"""Cross-repo operations: search all repos, service maps, batch operations.

The killer feature of this MCP server — operate across 7 repos as if they were one codebase.
"""

import json
import re
import subprocess
from collections import defaultdict
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from src.config import Config


def register_cross_repo_tools(mcp: FastMCP, config: Config):

    @mcp.tool()
    def search_all_repos(pattern: str, glob_filter: str = "", max_results: int = 50) -> str:
        """Search for a pattern across ALL cloned repos simultaneously.

        This is massively faster than searching repos one by one. Returns results
        grouped by repo with file paths and line numbers.

        Args:
            pattern: Regex pattern to search for
            glob_filter: Optional file glob filter (e.g. '*.py', '*.tsx')
            max_results: Max results per repo (default 50)
        """
        results = []
        for repo_cfg in config.repos:
            repo_path = config.get_repo_path(repo_cfg.name)
            if not repo_path.is_dir():
                continue

            cmd = ["grep", "-rn", "--include", glob_filter or "*", pattern, str(repo_path)]
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            except subprocess.TimeoutExpired:
                results.append(f"\n[{repo_cfg.name}] (search timed out)")
                continue

            if r.stdout.strip():
                lines = r.stdout.strip().split("\n")
                results.append(f"\n### {repo_cfg.name} ({len(lines)} matches)")
                for line in lines[:max_results]:
                    clean = line.replace(str(repo_path) + "/", "")
                    results.append(f"  {clean}")
                if len(lines) > max_results:
                    results.append(f"  ... and {len(lines) - max_results} more")

        if not results:
            return "No matches found across any repos."
        return "\n".join(results)

    @mcp.tool()
    def get_service_map() -> str:
        """Generate a map of how all repos/services connect to each other.

        Discovers: API URLs pointing to other services, shared environment variables,
        shared Firestore collections, shared external service integrations.
        This is critical for understanding blast radius of changes.
        """
        out = ["# Service Dependency Map\n"]

        service_urls = defaultdict(list)  # repo -> list of URLs it calls
        env_vars = defaultdict(set)  # repo -> set of env vars
        firestore_collections = defaultdict(set)  # repo -> set of collections
        external_services = defaultdict(set)  # repo -> set of external service names

        for repo_cfg in config.repos:
            repo_path = config.get_repo_path(repo_cfg.name)
            if not repo_path.is_dir():
                continue

            for f in repo_path.rglob("*"):
                if (not f.is_file() or ".git" in f.parts or "node_modules" in f.parts
                        or "__pycache__" in f.parts or "venv" in f.parts):
                    continue
                if f.suffix not in (".py", ".ts", ".tsx", ".js", ".json", ".sh", ".yml", ".yaml"):
                    continue
                try:
                    text = f.read_text(errors="replace")
                except Exception:
                    continue

                # Find URLs to other services
                urls = re.findall(r'https?://[^\s"\'<>]+', text)
                for url in urls:
                    if "github.com" not in url and "googleapis.com" not in url and "pypi.org" not in url:
                        service_urls[repo_cfg.name].append(url[:100])

                # Find env vars
                for match in re.finditer(r'(?:os\.environ|os\.getenv|process\.env)\s*[\[.]\s*["\']?(\w+)', text):
                    env_vars[repo_cfg.name].add(match.group(1))

                # Find Firestore collections
                for match in re.finditer(r'collection\(["\']([^"\']+)["\']\)', text):
                    firestore_collections[repo_cfg.name].add(match.group(1))

                # Detect external services
                service_patterns = {
                    "OpenAI": r"openai|OPENAI_API_KEY",
                    "Firebase/Firestore": r"firebase_admin|firestore",
                    "Twilio": r"twilio|TWILIO",
                    "ElevenLabs": r"elevenlabs|ELEVEN_LABS",
                    "Retell AI": r"retell|RETELL",
                    "Vapi": r"vapi|VAPI",
                    "Google Calendar": r"calendar.*google|google.*calendar",
                    "XTime": r"xtime|XTIME",
                    "Autoloop": r"autoloop|AUTOLOOP",
                    "PagerDuty": r"pagerduty|PAGERDUTY",
                    "Surge SMS": r"surge.*sms|SURGE",
                    "Instantly.ai": r"instantly|INSTANTLY",
                    "Supabase": r"supabase|SUPABASE",
                    "Sentry": r"sentry|SENTRY",
                    "Google Gemini": r"google.genai|GEMINI",
                    "Selenium/Chrome": r"selenium|webdriver|chromedriver",
                    "Dealer Inspire": r"dealer.inspire|DEALER_INSPIRE",
                }
                for service_name, pat in service_patterns.items():
                    if re.search(pat, text, re.IGNORECASE):
                        external_services[repo_cfg.name].add(service_name)

        # ── Output: External Services Matrix ───────────────────────────
        out.append("## External Services by Repo")
        for repo_name in sorted(external_services):
            services = sorted(external_services[repo_name])
            out.append(f"  **{repo_name}**: {', '.join(services)}")

        # ── Output: Shared Firestore Collections ───────────────────────
        out.append("\n## Shared Firestore Collections")
        all_collections = set()
        for cols in firestore_collections.values():
            all_collections.update(cols)
        for col in sorted(all_collections):
            repos_using = [r for r, cols in firestore_collections.items() if col in cols]
            if len(repos_using) > 1:
                out.append(f"  **{col}** → shared by: {', '.join(repos_using)}")
            else:
                out.append(f"  {col} → {repos_using[0]}")

        # ── Output: Shared Env Vars ────────────────────────────────────
        out.append("\n## Shared Environment Variables")
        all_vars = set()
        for vars_set in env_vars.values():
            all_vars.update(vars_set)
        shared_vars = {}
        for var in sorted(all_vars):
            repos_using = [r for r, vs in env_vars.items() if var in vs]
            if len(repos_using) > 1:
                shared_vars[var] = repos_using
        for var, repos in sorted(shared_vars.items()):
            out.append(f"  {var} → {', '.join(repos)}")

        # ── Output: Inter-service URLs ─────────────────────────────────
        out.append("\n## Notable Service URLs")
        for repo_name, urls in sorted(service_urls.items()):
            # Deduplicate and filter noise
            unique_urls = sorted(set(urls))[:10]
            interesting = [u for u in unique_urls if any(k in u.lower() for k in
                          ["localhost", "cloud.run", "allyai", "ngrok", "compute.app"])]
            if interesting:
                out.append(f"  **{repo_name}**:")
                for url in interesting:
                    out.append(f"    {url}")

        return "\n".join(out)

    @mcp.tool()
    def batch_git_status() -> str:
        """Get git status of ALL cloned repos in one call.

        Shows: current branch, clean/dirty status, ahead/behind remote, uncommitted files.
        """
        results = []
        for repo_cfg in config.repos:
            repo_path = config.get_repo_path(repo_cfg.name)
            if not repo_path.is_dir():
                results.append(f"  {repo_cfg.name}: (not cloned)")
                continue

            def run(*args):
                r = subprocess.run(["git", *args], cwd=str(repo_path), capture_output=True, text=True)
                return r.stdout.strip()

            branch = run("branch", "--show-current")
            status = run("status", "--porcelain")
            dirty = len(status.split("\n")) if status else 0

            line = f"  {repo_cfg.name:35s} [{branch}]"
            if dirty:
                line += f"  {dirty} uncommitted changes"
            else:
                line += "  clean"
            results.append(line)

        return "# Repo Status\n" + "\n".join(results)

    @mcp.tool()
    def batch_git_pull() -> str:
        """Pull latest changes for ALL cloned repos in one call."""
        results = []
        for repo_cfg in config.repos:
            repo_path = config.get_repo_path(repo_cfg.name)
            if not repo_path.is_dir():
                results.append(f"  {repo_cfg.name}: (not cloned)")
                continue

            r = subprocess.run(
                ["git", "pull"], cwd=str(repo_path),
                capture_output=True, text=True, timeout=30,
            )
            output = r.stdout.strip() or r.stderr.strip()
            results.append(f"  {repo_cfg.name}: {output[:100]}")

        return "# Pull Results\n" + "\n".join(results)

    @mcp.tool()
    def batch_create_branch(branch_name: str) -> str:
        """Create the same branch in ALL cloned repos at once.

        Args:
            branch_name: Branch name to create
        """
        results = []
        for repo_cfg in config.repos:
            repo_path = config.get_repo_path(repo_cfg.name)
            if not repo_path.is_dir():
                results.append(f"  {repo_cfg.name}: (not cloned)")
                continue

            r = subprocess.run(
                ["git", "checkout", "-b", branch_name],
                cwd=str(repo_path), capture_output=True, text=True,
            )
            output = r.stdout.strip() or r.stderr.strip()
            results.append(f"  {repo_cfg.name}: {output[:100]}")

        return f"# Created branch '{branch_name}'\n" + "\n".join(results)

    @mcp.tool()
    def find_shared_models() -> str:
        """Find data models/types that appear across multiple repos.

        Identifies shared concepts (User, Conversation, Task, etc.) across repos
        to understand API contracts and data consistency requirements.
        """
        models_by_name = defaultdict(list)  # model_name -> list of (repo, file, fields)

        for repo_cfg in config.repos:
            repo_path = config.get_repo_path(repo_cfg.name)
            if not repo_path.is_dir():
                continue

            if repo_cfg.language == "python":
                for f in repo_path.rglob("*.py"):
                    if ".git" in f.parts or "__pycache__" in f.parts or "venv" in f.parts:
                        continue
                    try:
                        text = f.read_text(errors="replace")
                    except Exception:
                        continue
                    for match in re.finditer(
                        r'class\s+(\w+)\s*\(\s*(?:BaseModel|BaseSettings)\s*\)\s*:\s*\n((?:[ \t]+[^\n]+\n)*)',
                        text
                    ):
                        name = match.group(1)
                        body = match.group(2)
                        fields = [l.strip().split(":")[0].strip() for l in body.split("\n")
                                  if ":" in l and not l.strip().startswith("#") and not l.strip().startswith("def")]
                        fields = [f for f in fields if f and not f.startswith('"')]
                        models_by_name[name].append({
                            "repo": repo_cfg.name,
                            "file": str(f.relative_to(repo_path)),
                            "fields": fields[:10],
                        })

        # Find models that appear in multiple repos
        shared = {name: locs for name, locs in models_by_name.items()
                  if len(set(loc["repo"] for loc in locs)) > 1}

        if not shared:
            return "No shared models found across repos."

        out = ["# Shared Models Across Repos\n"]
        for name, locations in sorted(shared.items()):
            out.append(f"## {name}")
            for loc in locations:
                out.append(f"  **{loc['repo']}** ({loc['file']}): fields = {loc['fields']}")
            out.append("")

        return "\n".join(out)

    @mcp.tool()
    def get_deployment_overview() -> str:
        """Get deployment configuration for ALL repos: Docker, ports, Cloud Run settings, deploy scripts."""
        out = ["# Deployment Overview\n"]

        for repo_cfg in config.repos:
            repo_path = config.get_repo_path(repo_cfg.name)
            if not repo_path.is_dir():
                continue

            info = [f"## {repo_cfg.name}"]

            # Dockerfile
            dockerfile = repo_path / "Dockerfile"
            if dockerfile.exists():
                text = dockerfile.read_text(errors="replace")
                port_match = re.search(r"EXPOSE\s+(\d+)", text)
                cmd_match = re.search(r"CMD\s+(.+)", text)
                base_match = re.search(r"FROM\s+(.+)", text)
                info.append(f"  Docker: base={base_match.group(1).strip() if base_match else '?'}, port={port_match.group(1) if port_match else '?'}")
                if cmd_match:
                    info.append(f"  CMD: {cmd_match.group(1).strip()}")

            # Deploy script
            for deploy_name in ["deploy.sh", "deploy_cloud_run.sh"]:
                deploy = repo_path / deploy_name
                if deploy.exists():
                    text = deploy.read_text(errors="replace")
                    region_match = re.search(r'REGION[="\s]+([^"\s]+)', text)
                    service_match = re.search(r'SERVICE_NAME[="\s]+([^"\s]+)', text)
                    project_match = re.search(r'PROJECT_ID[="\s]+([^"\s]+)', text)
                    info.append(f"  Deploy: {deploy_name}")
                    if project_match:
                        info.append(f"  GCP Project: {project_match.group(1)}")
                    if service_match:
                        info.append(f"  Service: {service_match.group(1)}")
                    if region_match:
                        info.append(f"  Region: {region_match.group(1)}")

            if len(info) > 1:
                out.extend(info)
                out.append("")

        return "\n".join(out)
