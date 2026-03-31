"""Deep codebase analysis tools that give agents instant understanding of a repo.

These tools replace the 20+ file reads an agent would normally need to understand
a codebase's architecture, patterns, and conventions.
"""

import ast
import json
import os
import re
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from src.config import Config


def _ensure_cloned(config: Config, repo_name: str) -> Path | str:
    p = config.get_repo_path(repo_name)
    if not p.is_dir():
        return f"Error: '{repo_name}' not cloned. Use clone_repo('{repo_name}') first."
    return p


def _run_cmd(cwd: str, *args, timeout: int = 30) -> str:
    try:
        r = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip()
    except Exception as e:
        return f"(error: {e})"


def register_context_tools(mcp: FastMCP, config: Config):

    @mcp.tool()
    def get_codebase_summary(repo_name: str) -> str:
        """Generate a comprehensive architecture summary of a repo in one call.

        Returns: framework, entry points, all endpoints/routes, all models/types,
        directory structure, external dependencies, environment vars, and key files
        ranked by importance. This replaces 20+ manual file reads.

        Args:
            repo_name: Name of the repo to analyze
        """
        repo = _ensure_cloned(config, repo_name)
        if isinstance(repo, str):
            return repo

        out = []
        repo_cfg = config.get_repo(repo_name)

        # ── Language & Framework Detection ─────────────────────────────
        lang = repo_cfg.language if repo_cfg else "unknown"
        framework = "unknown"
        deps = {}

        if lang == "python":
            req_file = repo / "requirements.txt"
            if req_file.exists():
                deps = {}
                for line in req_file.read_text().splitlines():
                    line = line.strip()
                    if line and not line.startswith("#"):
                        pkg = re.split(r"[><=!~\[]", line)[0].strip()
                        deps[pkg.lower()] = line

            if "fastapi" in deps:
                framework = "FastAPI"
            elif "flask" in deps:
                framework = "Flask"
            elif "django" in deps:
                framework = "Django"

            pyproject = repo / "pyproject.toml"
            if pyproject.exists():
                text = pyproject.read_text()
                if "fastapi" in text.lower():
                    framework = "FastAPI"

        elif lang == "typescript":
            pkg_file = repo / "package.json"
            if pkg_file.exists():
                try:
                    pkg = json.loads(pkg_file.read_text())
                    all_deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
                    deps = all_deps
                    if "next" in all_deps:
                        framework = "Next.js"
                    elif "vite" in all_deps and "react" in all_deps:
                        framework = "React + Vite"
                    elif "react" in all_deps:
                        framework = "React"
                    elif "express" in all_deps:
                        framework = "Express"
                except json.JSONDecodeError:
                    pass

        out.append(f"# {repo_name}")
        out.append(f"**Language:** {lang} | **Framework:** {framework}")
        if repo_cfg:
            out.append(f"**Description:** {repo_cfg.description}")

        # ── Directory Structure (depth 2) ──────────────────────────────
        out.append("\n## Directory Structure")
        tree_lines = []
        for root, dirs, files in os.walk(repo):
            dirs[:] = [d for d in dirs if d not in (".git", "__pycache__", "node_modules", ".next", "dist", "build", ".venv", "venv")]
            depth = Path(root).relative_to(repo).parts
            if len(depth) > 2:
                continue
            indent = "  " * len(depth)
            rel = Path(root).relative_to(repo)
            py_count = len([f for f in files if f.endswith((".py", ".ts", ".tsx", ".js", ".jsx"))])
            if py_count > 0:
                tree_lines.append(f"{indent}{rel}/ ({py_count} source files)")
        out.append("\n".join(tree_lines[:40]))

        # ── File Stats ─────────────────────────────────────────────────
        ext_counts = Counter()
        total_lines = 0
        biggest_files = []
        for f in repo.rglob("*"):
            if f.is_file() and ".git" not in f.parts and "node_modules" not in f.parts and "__pycache__" not in f.parts:
                ext_counts[f.suffix] += 1
                try:
                    size = f.stat().st_size
                    if f.suffix in (".py", ".ts", ".tsx", ".js", ".jsx"):
                        lines = f.read_text(errors="replace").count("\n")
                        total_lines += lines
                        biggest_files.append((str(f.relative_to(repo)), lines, size))
                except Exception:
                    pass

        biggest_files.sort(key=lambda x: x[1], reverse=True)
        out.append(f"\n## Stats")
        out.append(f"Total source lines: ~{total_lines:,}")
        out.append(f"File types: {dict(ext_counts.most_common(10))}")

        out.append("\n## Largest Files (most complex, modify with care)")
        for path, lines, size in biggest_files[:15]:
            out.append(f"  {path} ({lines} lines)")

        # ── Entry Points ───────────────────────────────────────────────
        out.append("\n## Entry Points")
        for name in ["main.py", "app/main.py", "src/main.py", "wsgi.py", "src/index.ts", "src/App.tsx", "src/main.tsx"]:
            ep = repo / name
            if ep.exists():
                out.append(f"  {name}")

        dockerfile = repo / "Dockerfile"
        if dockerfile.exists():
            text = dockerfile.read_text(errors="replace")
            cmd_match = re.search(r"CMD\s+(.+)", text)
            if cmd_match:
                out.append(f"  Docker CMD: {cmd_match.group(1).strip()}")
            port_match = re.search(r"EXPOSE\s+(\d+)", text)
            if port_match:
                out.append(f"  Exposed port: {port_match.group(1)}")

        # ── All API Endpoints / Routes ─────────────────────────────────
        out.append("\n## API Endpoints / Routes")
        endpoints = []
        if lang == "python":
            for f in repo.rglob("*.py"):
                if ".git" in f.parts or "__pycache__" in f.parts:
                    continue
                try:
                    text = f.read_text(errors="replace")
                except Exception:
                    continue
                for match in re.finditer(r'@(?:app|router)\.(get|post|put|delete|patch|websocket)\s*\(\s*["\']([^"\']+)["\']', text):
                    method, path = match.groups()
                    endpoints.append(f"  {method.upper():7s} {path:40s} ({f.relative_to(repo)})")
        elif lang == "typescript":
            for f in repo.rglob("*.tsx"):
                if ".git" in f.parts or "node_modules" in f.parts:
                    continue
                try:
                    text = f.read_text(errors="replace")
                except Exception:
                    continue
                for match in re.finditer(r'<Route\s+[^>]*path=["\']([^"\']+)["\']', text):
                    endpoints.append(f"  ROUTE   {match.group(1):40s} ({f.relative_to(repo)})")

        for ep in sorted(endpoints)[:50]:
            out.append(ep)
        if not endpoints:
            out.append("  (none found)")

        # ── All Models / Types ─────────────────────────────────────────
        out.append("\n## Models / Types")
        models = []
        if lang == "python":
            for f in repo.rglob("*.py"):
                if ".git" in f.parts or "__pycache__" in f.parts:
                    continue
                try:
                    text = f.read_text(errors="replace")
                except Exception:
                    continue
                for match in re.finditer(r'class\s+(\w+)\s*\(\s*(BaseModel|BaseSettings|Base)\s*\)', text):
                    models.append(f"  {match.group(1):30s} extends {match.group(2):15s} ({f.relative_to(repo)})")
        elif lang == "typescript":
            for f in repo.rglob("*.ts"):
                if ".git" in f.parts or "node_modules" in f.parts:
                    continue
                try:
                    text = f.read_text(errors="replace")
                except Exception:
                    continue
                for match in re.finditer(r'(?:export\s+)?(?:interface|type)\s+(\w+)', text):
                    models.append(f"  {match.group(1):30s} ({f.relative_to(repo)})")

        for m in sorted(set(models))[:40]:
            out.append(m)
        if not models:
            out.append("  (none found)")

        # ── Environment Variables ──────────────────────────────────────
        out.append("\n## Environment Variables")
        env_vars = set()
        for f in repo.rglob("*"):
            if f.is_file() and ".git" not in f.parts and "node_modules" not in f.parts:
                if f.suffix in (".py", ".ts", ".tsx", ".js", ".sh"):
                    try:
                        text = f.read_text(errors="replace")
                    except Exception:
                        continue
                    for match in re.finditer(r'(?:os\.environ|os\.getenv|process\.env)\s*[\[.]\s*["\']?(\w+)', text):
                        env_vars.add(match.group(1))
                    for match in re.finditer(r'(?:Settings|BaseSettings).*?(\w+)\s*:\s*str.*?=.*?Field', text, re.DOTALL):
                        env_vars.add(match.group(1))

        for name in ["env.example", ".env.example", ".env.template"]:
            env_file = repo / name
            if env_file.exists():
                for line in env_file.read_text().splitlines():
                    if "=" in line and not line.startswith("#"):
                        env_vars.add(line.split("=")[0].strip())

        for v in sorted(env_vars):
            out.append(f"  {v}")
        if not env_vars:
            out.append("  (none found)")

        # ── Key Dependencies ───────────────────────────────────────────
        out.append("\n## Key Dependencies")
        if lang == "python" and deps:
            important = [d for d in deps.values() if any(k in d.lower() for k in
                        ["fastapi", "openai", "langchain", "firebase", "google", "twilio",
                         "selenium", "pydantic", "sqlalchemy", "redis", "celery", "elevenlabs",
                         "pinecone", "faiss", "torch", "supabase", "sentry", "pagerduty",
                         "httpx", "aiohttp", "apscheduler"])]
            for d in sorted(important):
                out.append(f"  {d}")
            if not important:
                for d in sorted(deps.values())[:20]:
                    out.append(f"  {d}")
        elif lang == "typescript" and deps:
            important = {k: v for k, v in deps.items() if any(s in k for s in
                        ["react", "vite", "supabase", "vapi", "elevenlabs", "sentry",
                         "tailwind", "radix", "tanstack", "zod", "next"])}
            for k, v in sorted(important.items()):
                out.append(f"  {k}: {v}")

        return "\n".join(out)

    @mcp.tool()
    def extract_patterns(repo_name: str) -> str:
        """Extract coding conventions and patterns from a repo.

        Analyzes existing code to output a conventions guide: import style, naming,
        error handling, endpoint patterns, model patterns. Use this before writing
        any new code so it matches the existing codebase perfectly.

        Args:
            repo_name: Name of the repo to analyze
        """
        repo = _ensure_cloned(config, repo_name)
        if isinstance(repo, str):
            return repo

        repo_cfg = config.get_repo(repo_name)
        lang = repo_cfg.language if repo_cfg else "unknown"
        out = [f"# Coding Conventions: {repo_name}\n"]

        source_files = []
        if lang == "python":
            exts = (".py",)
        else:
            exts = (".ts", ".tsx")

        for f in repo.rglob("*"):
            if (f.is_file() and f.suffix in exts and
                    ".git" not in f.parts and "node_modules" not in f.parts and
                    "__pycache__" not in f.parts and "venv" not in f.parts):
                source_files.append(f)

        if not source_files:
            return "No source files found."

        # Sort by size desc to prioritize important files
        source_files.sort(key=lambda f: f.stat().st_size, reverse=True)
        # Sample top files for pattern analysis
        sample = source_files[:20]

        if lang == "python":
            # ── Import Style ───────────────────────────────────────────
            out.append("## Import Style")
            import_examples = []
            for f in sample[:5]:
                text = f.read_text(errors="replace")
                imports = [l for l in text.split("\n") if l.startswith("import ") or l.startswith("from ")]
                if imports:
                    import_examples.append(f"```python\n# {f.relative_to(repo)}\n" + "\n".join(imports[:8]) + "\n```")
            out.append("\n".join(import_examples[:3]))

            # ── Function/Endpoint Pattern ──────────────────────────────
            out.append("\n## Endpoint / Function Pattern")
            for f in sample:
                text = f.read_text(errors="replace")
                # Find a complete endpoint function (decorator + signature + first few lines)
                matches = list(re.finditer(
                    r'(@(?:app|router)\.\w+\([^)]*\)[^\n]*\n(?:@[^\n]+\n)*'
                    r'(?:async\s+)?def\s+\w+\([^)]*\)[^:]*:\s*\n'
                    r'(?:[ \t]+[^\n]+\n){1,8})',
                    text
                ))
                if matches:
                    out.append(f"```python\n# Pattern from {f.relative_to(repo)}\n{matches[0].group().strip()}\n```")
                    break

            # ── Error Handling Pattern ─────────────────────────────────
            out.append("\n## Error Handling Pattern")
            for f in sample:
                text = f.read_text(errors="replace")
                try_blocks = list(re.finditer(
                    r'(try:\s*\n(?:[ \t]+[^\n]+\n)+except[^\n]+:\s*\n(?:[ \t]+[^\n]+\n){1,4})',
                    text
                ))
                if try_blocks:
                    out.append(f"```python\n# Pattern from {f.relative_to(repo)}\n{try_blocks[0].group().strip()}\n```")
                    break

            # ── Model Pattern ──────────────────────────────────────────
            out.append("\n## Pydantic Model Pattern")
            for f in source_files:
                text = f.read_text(errors="replace")
                model_match = re.search(
                    r'(class\s+\w+\s*\(\s*BaseModel\s*\)\s*:\s*\n(?:[ \t]+[^\n]+\n){1,12})',
                    text
                )
                if model_match:
                    out.append(f"```python\n# Pattern from {f.relative_to(repo)}\n{model_match.group().strip()}\n```")
                    break

            # ── Naming Conventions ─────────────────────────────────────
            out.append("\n## Naming Conventions")
            func_names = []
            class_names = []
            for f in sample[:10]:
                text = f.read_text(errors="replace")
                func_names.extend(re.findall(r'def\s+(\w+)\s*\(', text))
                class_names.extend(re.findall(r'class\s+(\w+)', text))

            if func_names:
                snake = sum(1 for n in func_names if "_" in n)
                out.append(f"  Functions: {'snake_case' if snake > len(func_names) // 2 else 'camelCase'} (e.g. {', '.join(func_names[:5])})")
            if class_names:
                out.append(f"  Classes: PascalCase (e.g. {', '.join(class_names[:5])})")

            # ── File Organization ──────────────────────────────────────
            out.append("\n## File Organization")
            dirs = set()
            for f in source_files:
                rel = f.relative_to(repo)
                if len(rel.parts) > 1:
                    dirs.add(rel.parts[0] + "/" + (rel.parts[1] if len(rel.parts) > 2 else ""))
            for d in sorted(dirs)[:15]:
                out.append(f"  {d}")

        elif lang == "typescript":
            # ── Component Pattern ──────────────────────────────────────
            out.append("## Component Pattern")
            for f in sample:
                if f.suffix == ".tsx":
                    text = f.read_text(errors="replace")
                    comp_match = re.search(
                        r'((?:export\s+(?:default\s+)?)?(?:function|const)\s+\w+\s*(?::\s*React\.FC[^=]*=\s*)?(?:\([^)]*\)|\w+)\s*(?:=>|{)[^\n]*(?:\n[^\n]*){1,15})',
                        text
                    )
                    if comp_match:
                        out.append(f"```tsx\n// Pattern from {f.relative_to(repo)}\n{comp_match.group().strip()}\n```")
                        break

            # ── Import Style ───────────────────────────────────────────
            out.append("\n## Import Style")
            for f in sample[:3]:
                text = f.read_text(errors="replace")
                imports = [l for l in text.split("\n") if l.startswith("import ")]
                if imports:
                    out.append(f"```tsx\n// {f.relative_to(repo)}\n" + "\n".join(imports[:8]) + "\n```")
                    break

            # ── Hooks Pattern ──────────────────────────────────────────
            out.append("\n## Hooks Usage")
            hook_usage = Counter()
            for f in sample:
                text = f.read_text(errors="replace")
                for hook in re.findall(r'(use\w+)\s*\(', text):
                    hook_usage[hook] += 1
            for hook, count in hook_usage.most_common(10):
                out.append(f"  {hook} (used {count}x)")

        return "\n".join(out)

    @mcp.tool()
    def get_function_context(repo_name: str, function_name: str) -> str:
        """Get complete context for a function: definition, callers, callees, related tests.

        This replaces the manual process of grepping for a function, reading its file,
        grepping for callers, and finding tests — all in one call.

        Args:
            repo_name: Name of the repo
            function_name: Name of the function to analyze
        """
        repo = _ensure_cloned(config, repo_name)
        if isinstance(repo, str):
            return repo

        out = [f"# Context for `{function_name}`\n"]

        # ── Find Definition ────────────────────────────────────────────
        def_results = _run_cmd(str(repo), "grep", "-rn", "--include=*.py", "--include=*.ts", "--include=*.tsx",
                               f"def {function_name}\\|function {function_name}\\|const {function_name}", str(repo))

        out.append("## Definition")
        if def_results:
            for line in def_results.split("\n")[:5]:
                clean = line.replace(str(repo) + "/", "")
                out.append(f"  {clean}")

            # Read the full function body from the first match
            first_match = def_results.split("\n")[0]
            file_path = first_match.split(":")[0]
            line_num = int(first_match.split(":")[1]) if ":" in first_match.split(":")[1] else 0

            if line_num > 0:
                try:
                    source = Path(file_path).read_text(errors="replace").split("\n")
                    # Extract function body (up to 50 lines or next top-level def)
                    start = line_num - 1
                    end = start + 1
                    indent = len(source[start]) - len(source[start].lstrip())
                    for i in range(start + 1, min(start + 60, len(source))):
                        line = source[i]
                        if line.strip() == "":
                            end = i + 1
                            continue
                        line_indent = len(line) - len(line.lstrip())
                        if line_indent <= indent and line.strip() and not line.strip().startswith("#") and not line.strip().startswith("@"):
                            break
                        end = i + 1

                    out.append("\n```")
                    for i in range(start, min(end, start + 50)):
                        out.append(f"{i+1:>4} | {source[i]}")
                    if end > start + 50:
                        out.append(f"     ... ({end - start} total lines)")
                    out.append("```")
                except Exception:
                    pass
        else:
            out.append("  (not found)")

        # ── Find Callers ───────────────────────────────────────────────
        out.append("\n## Callers (who calls this function)")
        caller_results = _run_cmd(str(repo), "grep", "-rn", "--include=*.py", "--include=*.ts", "--include=*.tsx",
                                  f"{function_name}(", str(repo))
        if caller_results:
            callers = []
            for line in caller_results.split("\n"):
                clean = line.replace(str(repo) + "/", "")
                # Skip the definition itself and imports
                if f"def {function_name}" not in clean and f"function {function_name}" not in clean and "import" not in clean:
                    callers.append(f"  {clean}")
            out.extend(callers[:20])
            if not callers:
                out.append("  (no callers found)")
        else:
            out.append("  (no callers found)")

        # ── Find Related Tests ─────────────────────────────────────────
        out.append("\n## Related Tests")
        test_results = _run_cmd(str(repo), "grep", "-rn", "--include=test_*", "--include=*_test.*", "--include=*.test.*", "--include=*.spec.*",
                                function_name, str(repo))
        if test_results:
            for line in test_results.split("\n")[:10]:
                out.append(f"  {line.replace(str(repo) + '/', '')}")
        else:
            out.append("  (no tests found)")

        # ── Find Imports ───────────────────────────────────────────────
        out.append("\n## Import References")
        import_results = _run_cmd(str(repo), "grep", "-rn", "--include=*.py", "--include=*.ts",
                                  f"import.*{function_name}\\|from.*import.*{function_name}", str(repo))
        if import_results:
            for line in import_results.split("\n")[:10]:
                out.append(f"  {line.replace(str(repo) + '/', '')}")
        else:
            out.append("  (no imports found)")

        return "\n".join(out)

    @mcp.tool()
    def get_api_surface(repo_name: str) -> str:
        """Get complete API surface: all endpoints with their request/response types, middleware, and auth.

        Args:
            repo_name: Name of the repo
        """
        repo = _ensure_cloned(config, repo_name)
        if isinstance(repo, str):
            return repo

        repo_cfg = config.get_repo(repo_name)
        lang = repo_cfg.language if repo_cfg else "python"
        out = [f"# API Surface: {repo_name}\n"]

        if lang == "python":
            for f in sorted(repo.rglob("*.py")):
                if ".git" in f.parts or "__pycache__" in f.parts or "venv" in f.parts:
                    continue
                try:
                    text = f.read_text(errors="replace")
                except Exception:
                    continue

                # Find router prefix
                prefix = ""
                prefix_match = re.search(r'APIRouter\s*\(\s*prefix\s*=\s*["\']([^"\']+)', text)
                if prefix_match:
                    prefix = prefix_match.group(1)

                # Find endpoints with full signatures
                endpoint_pattern = re.compile(
                    r'@(?:app|router)\.(get|post|put|delete|patch)\s*\(\s*["\']([^"\']+)["\']'
                    r'(?:[^)]*response_model\s*=\s*(\w+))?[^)]*\)\s*\n'
                    r'(?:@[^\n]+\n)*'
                    r'(?:async\s+)?def\s+(\w+)\s*\(([^)]*)\)',
                    re.MULTILINE
                )

                endpoints = list(endpoint_pattern.finditer(text))
                if endpoints:
                    out.append(f"\n### {f.relative_to(repo)} {f'(prefix: {prefix})' if prefix else ''}")
                    for m in endpoints:
                        method, path, response_model, func_name, params = m.groups()
                        full_path = prefix + path
                        params_clean = re.sub(r'\s+', ' ', params.strip())
                        # Truncate long param lists
                        if len(params_clean) > 100:
                            params_clean = params_clean[:100] + "..."
                        line = f"  {method.upper():7s} {full_path:35s} → {func_name}({params_clean})"
                        if response_model:
                            line += f" -> {response_model}"
                        out.append(line)

            # Find router registrations in main
            for main_name in ["main.py", "app/main.py"]:
                main_file = repo / main_name
                if main_file.exists():
                    text = main_file.read_text(errors="replace")
                    includes = re.findall(r'include_router\s*\(\s*(\w+)(?:.*?prefix\s*=\s*["\']([^"\']+))?', text)
                    if includes:
                        out.append("\n### Router Registration (main.py)")
                        for router_var, prefix in includes:
                            out.append(f"  {router_var} → {prefix or '/'}")

        return "\n".join(out) if len(out) > 1 else "No API surface found."

    @mcp.tool()
    def get_dependency_graph(repo_name: str) -> str:
        """Map internal module dependencies — which modules import from which.

        Shows the import graph so you understand which files are foundational
        (many dependents) vs leaf (no dependents). Modify foundational files carefully.

        Args:
            repo_name: Name of the repo
        """
        repo = _ensure_cloned(config, repo_name)
        if isinstance(repo, str):
            return repo

        repo_cfg = config.get_repo(repo_name)
        lang = repo_cfg.language if repo_cfg else "python"

        imports_map = defaultdict(set)  # file -> set of files it imports from
        imported_by = defaultdict(set)  # file -> set of files that import it

        if lang == "python":
            for f in repo.rglob("*.py"):
                if ".git" in f.parts or "__pycache__" in f.parts or "venv" in f.parts:
                    continue
                try:
                    text = f.read_text(errors="replace")
                except Exception:
                    continue
                rel = str(f.relative_to(repo))
                for match in re.finditer(r'from\s+(\S+)\s+import', text):
                    module = match.group(1)
                    if module.startswith(".") or module.startswith("app.") or module.startswith("src."):
                        imports_map[rel].add(module)
                        imported_by[module].add(rel)

        out = [f"# Dependency Graph: {repo_name}\n"]

        # Most imported modules (foundational)
        out.append("## Most Imported (foundational — modify carefully)")
        by_count = sorted(imported_by.items(), key=lambda x: len(x[1]), reverse=True)
        for module, importers in by_count[:15]:
            out.append(f"  {module} (imported by {len(importers)} files)")

        # Leaf modules (no dependents)
        all_modules = set(imports_map.keys())
        all_imported = set(imported_by.keys())
        leaves = [m for m in all_modules if not any(m.replace("/", ".").replace(".py", "") in imp for imp in all_imported)]
        if leaves:
            out.append("\n## Leaf Modules (safe to modify)")
            for m in sorted(leaves)[:20]:
                out.append(f"  {m}")

        return "\n".join(out)
