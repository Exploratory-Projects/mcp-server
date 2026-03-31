import json
import re
import subprocess
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from src.config import Config

REPO_NAME = "ally-ai-production"


def _ensure_cloned(config: Config) -> Path | str:
    p = config.get_repo_path(REPO_NAME)
    if not p.is_dir():
        return f"Error: ally-ai-production not cloned. Use clone_repo('{REPO_NAME}') first."
    return p


def register_ally_ai_production_tools(mcp: FastMCP, config: Config):

    # ── React Components ───────────────────────────────────────────────

    @mcp.tool()
    def list_react_components() -> str:
        """List all React components organized by directory (src/components/)."""
        repo = _ensure_cloned(config)
        if isinstance(repo, str):
            return repo

        components_dir = repo / "src" / "components"
        results = []
        if components_dir.is_dir():
            current_dir = ""
            for f in sorted(components_dir.rglob("*.tsx")):
                parent = str(f.parent.relative_to(components_dir))
                if parent != current_dir:
                    current_dir = parent
                    results.append(f"\n  [{parent}/]")
                results.append(f"    {f.name} ({f.stat().st_size / 1024:.1f} KB)")

        # Also check for standalone tsx in src/
        for f in sorted((repo / "src").glob("*.tsx")):
            results.append(f"  [src/] {f.name} ({f.stat().st_size / 1024:.1f} KB)")

        return f"React Components:\n" + "\n".join(results) if results else "No components found."

    @mcp.tool()
    def get_component_exports(component_path: str) -> str:
        """Inspect a React component's exports, props, and hooks usage.

        Args:
            component_path: Relative path to .tsx file (e.g. 'src/components/chat/ChatWidget.tsx')
        """
        repo = _ensure_cloned(config)
        if isinstance(repo, str):
            return repo

        filepath = repo / component_path
        if not filepath.exists():
            return f"Error: {component_path} not found."

        text = filepath.read_text(errors="replace")
        results = []

        # Exports
        exports = re.findall(r'export\s+(?:default\s+)?(?:function|const|class)\s+(\w+)', text)
        if exports:
            results.append(f"Exports: {', '.join(exports)}")

        # Props/interfaces
        interfaces = re.findall(r'(?:interface|type)\s+(\w+(?:Props|Config|State))\s*(?:=|\{)', text)
        if interfaces:
            results.append(f"Types: {', '.join(interfaces)}")

        # Hooks
        hooks = set(re.findall(r'(use\w+)\s*\(', text))
        if hooks:
            results.append(f"Hooks: {', '.join(sorted(hooks))}")

        # Imports from external libs
        ext_imports = re.findall(r'from\s+["\'](@?\w[^"\']+)["\']', text)
        ext_imports = [i for i in ext_imports if not i.startswith(".") and not i.startswith("@/")]
        if ext_imports:
            results.append(f"External imports: {', '.join(sorted(set(ext_imports)))}")

        return f"Component analysis - {component_path}:\n" + "\n".join(results) if results else "Could not extract component info."

    # ── Pages & Routes ─────────────────────────────────────────────────

    @mcp.tool()
    def list_pages() -> str:
        """List all page components (src/pages/)."""
        repo = _ensure_cloned(config)
        if isinstance(repo, str):
            return repo

        pages_dir = repo / "src" / "pages"
        results = []
        if pages_dir.is_dir():
            for f in sorted(pages_dir.rglob("*.tsx")):
                results.append(f"  {f.name} ({f.stat().st_size / 1024:.1f} KB)")

        return f"Pages:\n" + "\n".join(results) if results else "No pages directory found."

    @mcp.tool()
    def get_route_config() -> str:
        """Extract React Router route configuration from App.tsx or router config."""
        repo = _ensure_cloned(config)
        if isinstance(repo, str):
            return repo

        results = []
        for candidate in ["src/App.tsx", "src/router.tsx", "src/routes.tsx"]:
            filepath = repo / candidate
            if filepath.exists():
                text = filepath.read_text(errors="replace")
                # Extract Route elements
                routes = re.findall(r'<Route\s+[^>]*path=["\']([^"\']+)["\'][^>]*/?>|path:\s*["\']([^"\']+)["\']', text)
                if routes:
                    results.append(f"=== {candidate} ===")
                    for r in routes:
                        path = r[0] or r[1]
                        results.append(f"  {path}")

                # Also look for redirects
                redirects = re.findall(r'ExternalRedirect.*?to=["\']([^"\']+)["\']|Navigate.*?to=["\']([^"\']+)["\']', text)
                for r in redirects:
                    url = r[0] or r[1]
                    results.append(f"  [redirect] -> {url}")

        return "\n".join(results) if results else "No route configuration found."

    # ── Supabase Integration ───────────────────────────────────────────

    @mcp.tool()
    def get_supabase_config() -> str:
        """Inspect Supabase client configuration and integration files."""
        repo = _ensure_cloned(config)
        if isinstance(repo, str):
            return repo

        results = []
        supabase_dir = repo / "src" / "integrations" / "supabase"
        if supabase_dir.is_dir():
            for f in sorted(supabase_dir.rglob("*")):
                if f.is_file() and f.suffix in (".ts", ".tsx", ".js"):
                    results.append(f"=== {f.relative_to(repo)} ===\n{f.read_text(errors='replace')[:3000]}")

        return "\n\n".join(results) if results else "No Supabase integration directory found."

    @mcp.tool()
    def list_supabase_edge_functions() -> str:
        """List Supabase Edge Functions (supabase/functions/)."""
        repo = _ensure_cloned(config)
        if isinstance(repo, str):
            return repo

        functions_dir = repo / "supabase" / "functions"
        results = []
        if functions_dir.is_dir():
            for d in sorted(functions_dir.iterdir()):
                if d.is_dir():
                    files = list(d.rglob("*"))
                    file_names = [f.name for f in files if f.is_file()]
                    total_size = sum(f.stat().st_size for f in files if f.is_file()) / 1024
                    results.append(f"  {d.name}/ ({total_size:.1f} KB): {', '.join(file_names)}")

        return f"Edge Functions:\n" + "\n".join(results) if results else "No edge functions found."

    @mcp.tool()
    def get_supabase_migrations() -> str:
        """List and read Supabase SQL migration files."""
        repo = _ensure_cloned(config)
        if isinstance(repo, str):
            return repo

        migrations_dir = repo / "supabase" / "migrations"
        results = []
        if migrations_dir.is_dir():
            for f in sorted(migrations_dir.rglob("*.sql")):
                text = f.read_text(errors="replace")
                results.append(f"=== {f.name} ===\n{text[:3000]}")

        return "\n\n".join(results) if results else "No migrations found."

    # ── UI Components (shadcn) ─────────────────────────────────────────

    @mcp.tool()
    def list_ui_primitives() -> str:
        """List all shadcn/ui primitive components (src/components/ui/)."""
        repo = _ensure_cloned(config)
        if isinstance(repo, str):
            return repo

        ui_dir = repo / "src" / "components" / "ui"
        results = []
        if ui_dir.is_dir():
            for f in sorted(ui_dir.rglob("*.tsx")):
                results.append(f"  {f.name}")

        return f"shadcn/ui primitives ({len(results)}):\n" + "\n".join(results) if results else "No UI primitives found."

    # ── Hooks ──────────────────────────────────────────────────────────

    @mcp.tool()
    def list_custom_hooks() -> str:
        """List custom React hooks (src/hooks/)."""
        repo = _ensure_cloned(config)
        if isinstance(repo, str):
            return repo

        hooks_dir = repo / "src" / "hooks"
        results = []
        if hooks_dir.is_dir():
            for f in sorted(hooks_dir.rglob("*.ts*")):
                size_kb = f.stat().st_size / 1024
                text = f.read_text(errors="replace")
                hook_exports = re.findall(r'export\s+(?:function|const)\s+(use\w+)', text)
                results.append(f"  {f.name} ({size_kb:.1f} KB): {', '.join(hook_exports) if hook_exports else 'N/A'}")

        return f"Custom hooks:\n" + "\n".join(results) if results else "No hooks directory found."

    # ── Chat / Voice / SMS Features ────────────────────────────────────

    @mcp.tool()
    def get_chat_agent_info() -> str:
        """Inspect the chat agent orchestrator and related components."""
        repo = _ensure_cloned(config)
        if isinstance(repo, str):
            return repo

        results = []
        chat_dir = repo / "src" / "components" / "chat"
        if chat_dir.is_dir():
            for f in sorted(chat_dir.rglob("*.ts*")):
                size_kb = f.stat().st_size / 1024
                results.append(f"  {f.name} ({size_kb:.1f} KB)")

        return f"Chat components:\n" + "\n".join(results) if results else "No chat directory found."

    @mcp.tool()
    def get_voice_integration_info() -> str:
        """Inspect Vapi/ElevenLabs voice integration components."""
        repo = _ensure_cloned(config)
        if isinstance(repo, str):
            return repo

        results = []
        voice_dir = repo / "src" / "components" / "voice"
        if voice_dir.is_dir():
            for f in sorted(voice_dir.rglob("*.ts*")):
                size_kb = f.stat().st_size / 1024
                results.append(f"  {f.name} ({size_kb:.1f} KB)")

        return f"Voice components:\n" + "\n".join(results) if results else "No voice directory found."

    # ── Build & Config ─────────────────────────────────────────────────

    @mcp.tool()
    def get_vite_config() -> str:
        """Read Vite build configuration."""
        repo = _ensure_cloned(config)
        if isinstance(repo, str):
            return repo

        for name in ["vite.config.ts", "vite.config.js"]:
            filepath = repo / name
            if filepath.exists():
                return f"=== {name} ===\n{filepath.read_text(errors='replace')}"

        return "No vite config found."

    @mcp.tool()
    def get_tailwind_config() -> str:
        """Read Tailwind CSS configuration."""
        repo = _ensure_cloned(config)
        if isinstance(repo, str):
            return repo

        for name in ["tailwind.config.ts", "tailwind.config.js"]:
            filepath = repo / name
            if filepath.exists():
                return f"=== {name} ===\n{filepath.read_text(errors='replace')}"

        return "No Tailwind config found."

    @mcp.tool()
    def get_package_json() -> str:
        """Read package.json for dependencies and scripts."""
        repo = _ensure_cloned(config)
        if isinstance(repo, str):
            return repo

        filepath = repo / "package.json"
        if not filepath.exists():
            return "No package.json found."

        data = json.loads(filepath.read_text())
        # Summarize key sections
        sections = {}
        for key in ["name", "version", "scripts", "dependencies", "devDependencies"]:
            if key in data:
                sections[key] = data[key]

        return json.dumps(sections, indent=2)

    @mcp.tool()
    def get_tsconfig() -> str:
        """Read TypeScript configuration."""
        repo = _ensure_cloned(config)
        if isinstance(repo, str):
            return repo

        for name in ["tsconfig.json", "tsconfig.app.json"]:
            filepath = repo / name
            if filepath.exists():
                return f"=== {name} ===\n{filepath.read_text(errors='replace')}"

        return "No tsconfig found."

    # ── Build & Lint ───────────────────────────────────────────────────

    @mcp.tool()
    def run_typecheck() -> str:
        """Run TypeScript type checking (tsc --noEmit)."""
        repo = _ensure_cloned(config)
        if isinstance(repo, str):
            return repo

        result = subprocess.run(
            ["npx", "tsc", "--noEmit"],
            cwd=str(repo), capture_output=True, text=True, timeout=120,
        )
        output = result.stdout + result.stderr
        return output.strip() if output.strip() else "Type checking passed with no errors."

    @mcp.tool()
    def run_build() -> str:
        """Run Vite production build to check for build errors."""
        repo = _ensure_cloned(config)
        if isinstance(repo, str):
            return repo

        result = subprocess.run(
            ["npm", "run", "build"],
            cwd=str(repo), capture_output=True, text=True, timeout=180,
        )
        output = result.stdout + result.stderr
        return output.strip()[-3000:] if output.strip() else "Build completed."

    # ── Static Data ────────────────────────────────────────────────────

    @mcp.tool()
    def list_static_data() -> str:
        """List static data files (src/data/)."""
        repo = _ensure_cloned(config)
        if isinstance(repo, str):
            return repo

        data_dir = repo / "src" / "data"
        results = []
        if data_dir.is_dir():
            for f in sorted(data_dir.rglob("*")):
                if f.is_file():
                    results.append(f"  {f.relative_to(repo)} ({f.stat().st_size / 1024:.1f} KB)")

        return f"Static data:\n" + "\n".join(results) if results else "No data directory found."
