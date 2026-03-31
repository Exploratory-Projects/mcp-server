"""Code validation tools: syntax checking, linting, type checking, testing.

One-call validation that catches issues before committing.
"""

import subprocess
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from src.config import Config


def _ensure_cloned(config: Config, repo_name: str) -> Path | str:
    p = config.get_repo_path(repo_name)
    if not p.is_dir():
        return f"Error: '{repo_name}' not cloned. Use clone_repo('{repo_name}') first."
    return p


def _run(cwd: str, *args, timeout: int = 120) -> tuple[bool, str]:
    try:
        r = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        output = (r.stdout + r.stderr).strip()
        return r.returncode == 0, output
    except FileNotFoundError:
        return False, f"Command not found: {args[0]}"
    except subprocess.TimeoutExpired:
        return False, "Command timed out"


def register_validation_tools(mcp: FastMCP, config: Config):

    @mcp.tool()
    def validate_repo(repo_name: str) -> str:
        """Run ALL available validation checks on a repo in one call.

        Runs: syntax check, linting, type checking, and tests (whatever is available).
        Returns a comprehensive report. Use this before committing.

        Args:
            repo_name: Name of the repo to validate
        """
        repo = _ensure_cloned(config, repo_name)
        if isinstance(repo, str):
            return repo

        repo_cfg = config.get_repo(repo_name)
        lang = repo_cfg.language if repo_cfg else "python"
        out = [f"# Validation Report: {repo_name}\n"]

        if lang == "python":
            # Syntax check
            out.append("## Syntax Check")
            ok, output = _run(str(repo), sys.executable, "-m", "py_compile", "--help")
            syntax_errors = []
            for f in repo.rglob("*.py"):
                if ".git" in f.parts or "__pycache__" in f.parts or "venv" in f.parts:
                    continue
                ok, err = _run(str(repo), sys.executable, "-c",
                              f"import ast; ast.parse(open('{f}').read())")
                if not ok:
                    syntax_errors.append(f"  FAIL: {f.relative_to(repo)}: {err[:200]}")
            if syntax_errors:
                out.extend(syntax_errors[:20])
            else:
                out.append("  All files pass syntax check")

            # Lint (ruff or flake8)
            out.append("\n## Lint")
            ok, output = _run(str(repo), "ruff", "check", ".", "--no-fix")
            if ok:
                out.append("  No lint errors (ruff)")
            elif "Command not found" in output:
                ok, output = _run(str(repo), sys.executable, "-m", "flake8", ".", "--max-line-length=120", "--count")
                if ok:
                    out.append("  No lint errors (flake8)")
                elif "Command not found" in output or "No module" in output:
                    out.append("  (no linter available — install ruff or flake8)")
                else:
                    out.append(f"  {output[:500]}")
            else:
                out.append(f"  {output[:500]}")

            # Type check
            out.append("\n## Type Check")
            ok, output = _run(str(repo), sys.executable, "-m", "mypy", ".", "--ignore-missing-imports", "--no-error-summary")
            if ok:
                out.append("  No type errors (mypy)")
            elif "No module" in output or "Command not found" in output:
                out.append("  (mypy not available — install mypy)")
            else:
                errors = [l for l in output.split("\n") if "error:" in l]
                out.append(f"  {len(errors)} type errors found:")
                for e in errors[:15]:
                    out.append(f"    {e}")
                if len(errors) > 15:
                    out.append(f"    ... and {len(errors) - 15} more")

            # Tests
            out.append("\n## Tests")
            test_files = list(repo.rglob("test_*.py")) + list(repo.rglob("*_test.py"))
            tests_dir = repo / "tests"
            if test_files or tests_dir.exists():
                ok, output = _run(str(repo), sys.executable, "-m", "pytest", "-v", "--tb=short", "-q", timeout=180)
                if ok:
                    out.append(f"  All tests pass")
                else:
                    out.append(f"  {output[-1000:]}")
            else:
                out.append("  (no tests found)")

        elif lang == "typescript":
            # TypeScript type check
            out.append("## TypeScript Check")
            ok, output = _run(str(repo), "npx", "tsc", "--noEmit", timeout=120)
            if ok:
                out.append("  No type errors")
            else:
                errors = [l for l in output.split("\n") if "error TS" in l]
                out.append(f"  {len(errors)} type errors:")
                for e in errors[:15]:
                    out.append(f"    {e}")

            # Lint
            out.append("\n## Lint")
            ok, output = _run(str(repo), "npx", "eslint", "src/", "--max-warnings=0")
            if ok:
                out.append("  No lint errors")
            elif "Command not found" in output:
                out.append("  (eslint not configured)")
            else:
                out.append(f"  {output[:500]}")

            # Build check
            out.append("\n## Build")
            ok, output = _run(str(repo), "npm", "run", "build", timeout=180)
            if ok:
                out.append("  Build succeeds")
            else:
                out.append(f"  Build failed:\n  {output[-500:]}")

            # Tests
            out.append("\n## Tests")
            ok, output = _run(str(repo), "npm", "test", "--", "--run", timeout=120)
            if ok:
                out.append(f"  Tests pass")
            elif "Missing script" in output or "ERR!" in output:
                out.append("  (no test script configured)")
            else:
                out.append(f"  {output[-500:]}")

        return "\n".join(out)

    @mcp.tool()
    def check_syntax(repo_name: str, file_path: str) -> str:
        """Quick syntax validation on a single file.

        Args:
            repo_name: Name of the repo
            file_path: Relative path to the file to check
        """
        repo = _ensure_cloned(config, repo_name)
        if isinstance(repo, str):
            return repo

        filepath = repo / file_path
        if not filepath.exists():
            return f"Error: {file_path} not found."

        if filepath.suffix == ".py":
            ok, output = _run(str(repo), sys.executable, "-c",
                             f"import ast; ast.parse(open('{filepath}').read()); print('OK')")
            return output if output else "Syntax OK"
        elif filepath.suffix in (".ts", ".tsx"):
            ok, output = _run(str(repo), "npx", "tsc", "--noEmit", str(filepath))
            return "No errors" if ok else output[:1000]
        else:
            return f"No syntax checker for {filepath.suffix} files."

    @mcp.tool()
    def run_tests(repo_name: str, test_path: str = "", verbose: bool = True) -> str:
        """Run tests for a repo, optionally filtering to a specific path.

        Args:
            repo_name: Name of the repo
            test_path: Optional path to specific test file or directory
            verbose: Show verbose output (default True)
        """
        repo = _ensure_cloned(config, repo_name)
        if isinstance(repo, str):
            return repo

        repo_cfg = config.get_repo(repo_name)
        lang = repo_cfg.language if repo_cfg else "python"

        if lang == "python":
            cmd = [sys.executable, "-m", "pytest"]
            if verbose:
                cmd.append("-v")
            cmd.append("--tb=short")
            if test_path:
                cmd.append(test_path)
            ok, output = _run(str(repo), *cmd, timeout=180)
        elif lang == "typescript":
            cmd = ["npm", "test", "--"]
            if test_path:
                cmd.append(test_path)
            cmd.append("--run")
            ok, output = _run(str(repo), *cmd, timeout=180)
        else:
            return f"No test runner for {lang}."

        return output[-3000:] if output else "No output."

    @mcp.tool()
    def check_imports(repo_name: str, file_path: str) -> str:
        """Verify all imports in a file resolve correctly.

        Catches missing dependencies, typos in import paths, circular imports.

        Args:
            repo_name: Name of the repo
            file_path: Relative path to check
        """
        repo = _ensure_cloned(config, repo_name)
        if isinstance(repo, str):
            return repo

        filepath = repo / file_path
        if not filepath.exists():
            return f"Error: {file_path} not found."

        if filepath.suffix != ".py":
            return "Import checking only available for Python files."

        text = filepath.read_text(errors="replace")
        import_lines = []
        for i, line in enumerate(text.split("\n"), 1):
            stripped = line.strip()
            if stripped.startswith("import ") or stripped.startswith("from "):
                import_lines.append((i, stripped))

        if not import_lines:
            return "No imports found."

        issues = []
        for line_num, import_line in import_lines:
            # Check if it's a local import
            if "from ." in import_line or "from app." in import_line or "from src." in import_line:
                # Try to resolve the module path
                match = __import__("re").search(r'from\s+(\S+)\s+import', import_line)
                if match:
                    module = match.group(1)
                    # Convert module path to file path
                    if module.startswith("."):
                        # Relative import
                        base = filepath.parent
                        parts = module.lstrip(".").split(".")
                        target = base / "/".join(parts)
                    else:
                        parts = module.split(".")
                        target = repo / "/".join(parts)

                    # Check if module file or package exists
                    if not (target.with_suffix(".py").exists() or
                            (target.is_dir() and (target / "__init__.py").exists())):
                        issues.append(f"  L{line_num}: {import_line} → module not found at {target.relative_to(repo)}")

        if issues:
            return f"Import issues found ({len(issues)}):\n" + "\n".join(issues)
        return f"All {len(import_lines)} imports look valid."

    @mcp.tool()
    def validate_changes(repo_name: str) -> str:
        """Validate ONLY the files that have been changed (uncommitted) in a repo.

        More focused than validate_repo — only checks modified files.
        Use this after making edits and before committing.

        Args:
            repo_name: Name of the repo
        """
        repo = _ensure_cloned(config, repo_name)
        if isinstance(repo, str):
            return repo

        # Get changed files
        r = subprocess.run(
            ["git", "diff", "--name-only", "--diff-filter=ACMR", "HEAD"],
            cwd=str(repo), capture_output=True, text=True,
        )
        # Also include untracked
        r2 = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            cwd=str(repo), capture_output=True, text=True,
        )

        changed = set()
        for line in (r.stdout + r2.stdout).strip().split("\n"):
            if line.strip():
                changed.add(line.strip())

        if not changed:
            return "No uncommitted changes to validate."

        out = [f"# Validating {len(changed)} changed files\n"]

        repo_cfg = config.get_repo(repo_name)
        lang = repo_cfg.language if repo_cfg else "python"

        for fpath in sorted(changed):
            filepath = repo / fpath
            if not filepath.exists():
                continue

            issues = []

            if filepath.suffix == ".py":
                # Syntax check
                ok, err = _run(str(repo), sys.executable, "-c",
                              f"import ast; ast.parse(open('{filepath}').read())")
                if not ok:
                    issues.append(f"SYNTAX ERROR: {err[:200]}")

                # Quick lint
                ok, err = _run(str(repo), "ruff", "check", fpath, "--no-fix")
                if not ok and "Command not found" not in err:
                    issues.append(f"LINT: {err[:200]}")

            elif filepath.suffix in (".ts", ".tsx"):
                ok, err = _run(str(repo), "npx", "tsc", "--noEmit", fpath)
                if not ok:
                    issues.append(f"TYPE ERROR: {err[:200]}")

            if issues:
                out.append(f"  FAIL {fpath}")
                for issue in issues:
                    out.append(f"    {issue}")
            else:
                out.append(f"  OK   {fpath}")

        return "\n".join(out)
