import fnmatch
import os
import re
import subprocess
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from src.config import Config


def _resolve_repo_path(config: Config, repo_name: str) -> Path | None:
    repo_path = config.get_repo_path(repo_name)
    if not repo_path.is_dir():
        return None
    return repo_path


def register_file_tools(mcp: FastMCP, config: Config):

    @mcp.tool()
    def read_file(repo_name: str, file_path: str, offset: int = 0, limit: int = 0) -> str:
        """Read contents of a file from a repository.

        Args:
            repo_name: Name of the repo
            file_path: Relative path to the file within the repo
            offset: Line number to start from (0-based, default 0)
            limit: Number of lines to read (0 = all, default 0)
        """
        repo_path = _resolve_repo_path(config, repo_name)
        if not repo_path:
            return f"Error: Repo '{repo_name}' not cloned."

        full_path = repo_path / file_path
        if not full_path.is_file():
            return f"Error: File not found: {file_path}"

        # Prevent path traversal
        if not full_path.resolve().is_relative_to(repo_path.resolve()):
            return "Error: Path traversal not allowed."

        text = full_path.read_text(errors="replace")
        lines = text.splitlines(keepends=True)

        if offset > 0:
            lines = lines[offset:]
        if limit > 0:
            lines = lines[:limit]

        numbered = []
        for i, line in enumerate(lines, start=max(offset, 0) + 1):
            numbered.append(f"{i:>6}\t{line.rstrip()}")
        return "\n".join(numbered)

    @mcp.tool()
    def write_file(repo_name: str, file_path: str, content: str) -> str:
        """Write content to a file in a repository. Creates the file and parent directories if they don't exist.

        Args:
            repo_name: Name of the repo
            file_path: Relative path to the file within the repo
            content: Content to write
        """
        repo_path = _resolve_repo_path(config, repo_name)
        if not repo_path:
            return f"Error: Repo '{repo_name}' not cloned."

        full_path = repo_path / file_path
        if not full_path.resolve().is_relative_to(repo_path.resolve()):
            return "Error: Path traversal not allowed."

        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content)
        return f"Written {len(content)} bytes to {file_path}"

    @mcp.tool()
    def edit_file(repo_name: str, file_path: str, old_string: str, new_string: str) -> str:
        """Edit a file by replacing an exact string match. The old_string must appear exactly once in the file.

        Args:
            repo_name: Name of the repo
            file_path: Relative path to the file
            old_string: The exact text to find and replace
            new_string: The replacement text
        """
        repo_path = _resolve_repo_path(config, repo_name)
        if not repo_path:
            return f"Error: Repo '{repo_name}' not cloned."

        full_path = repo_path / file_path
        if not full_path.is_file():
            return f"Error: File not found: {file_path}"
        if not full_path.resolve().is_relative_to(repo_path.resolve()):
            return "Error: Path traversal not allowed."

        text = full_path.read_text(errors="replace")
        count = text.count(old_string)
        if count == 0:
            return "Error: old_string not found in file."
        if count > 1:
            return f"Error: old_string found {count} times. Must be unique. Add more context."

        new_text = text.replace(old_string, new_string, 1)
        full_path.write_text(new_text)
        return f"Edited {file_path}: replaced 1 occurrence."

    @mcp.tool()
    def delete_file(repo_name: str, file_path: str) -> str:
        """Delete a file from a repository.

        Args:
            repo_name: Name of the repo
            file_path: Relative path to the file
        """
        repo_path = _resolve_repo_path(config, repo_name)
        if not repo_path:
            return f"Error: Repo '{repo_name}' not cloned."

        full_path = repo_path / file_path
        if not full_path.is_file():
            return f"Error: File not found: {file_path}"
        if not full_path.resolve().is_relative_to(repo_path.resolve()):
            return "Error: Path traversal not allowed."

        full_path.unlink()
        return f"Deleted {file_path}"

    @mcp.tool()
    def list_files(repo_name: str, pattern: str = "**/*", path: str = "") -> str:
        """List files in a repository matching a glob pattern.

        Args:
            repo_name: Name of the repo
            pattern: Glob pattern (default '**/*' for all files)
            path: Subdirectory to search in (default '' for repo root)
        """
        repo_path = _resolve_repo_path(config, repo_name)
        if not repo_path:
            return f"Error: Repo '{repo_name}' not cloned."

        search_path = repo_path / path
        if not search_path.is_dir():
            return f"Error: Directory not found: {path}"

        matches = []
        for p in sorted(search_path.glob(pattern)):
            if ".git" in p.parts:
                continue
            rel = p.relative_to(repo_path)
            prefix = "d" if p.is_dir() else "f"
            matches.append(f"[{prefix}] {rel}")

        if not matches:
            return "No files matched."
        return "\n".join(matches[:500])

    @mcp.tool()
    def search_code(repo_name: str, pattern: str, glob_filter: str = "", max_results: int = 50) -> str:
        """Search for text or regex pattern across files in a repository using ripgrep or grep.

        Args:
            repo_name: Name of the repo
            pattern: Regex pattern to search for
            glob_filter: Optional glob to filter files (e.g. '*.py')
            max_results: Maximum results to return (default 50)
        """
        repo_path = _resolve_repo_path(config, repo_name)
        if not repo_path:
            return f"Error: Repo '{repo_name}' not cloned."

        cmd = ["rg", "--no-heading", "--line-number", "--max-count", str(max_results)]
        if glob_filter:
            cmd.extend(["--glob", glob_filter])
        cmd.extend([pattern, str(repo_path)])

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 2:
            # rg not found, fall back to grep
            cmd = ["grep", "-rn", "--include", glob_filter or "*", pattern, str(repo_path)]
            result = subprocess.run(cmd, capture_output=True, text=True)

        if not result.stdout.strip():
            return "No matches found."

        # Make paths relative
        output = result.stdout.replace(str(repo_path) + "/", "")
        lines = output.strip().split("\n")
        return "\n".join(lines[:max_results])

    @mcp.tool()
    def get_file_tree(repo_name: str, max_depth: int = 3) -> str:
        """Get a tree view of the repository file structure.

        Args:
            repo_name: Name of the repo
            max_depth: Maximum directory depth (default 3)
        """
        repo_path = _resolve_repo_path(config, repo_name)
        if not repo_path:
            return f"Error: Repo '{repo_name}' not cloned."

        lines = []

        def _walk(dir_path: Path, prefix: str, depth: int):
            if depth > max_depth:
                return
            entries = sorted(dir_path.iterdir(), key=lambda e: (not e.is_dir(), e.name))
            entries = [e for e in entries if e.name != ".git"]
            for i, entry in enumerate(entries):
                is_last = i == len(entries) - 1
                connector = "└── " if is_last else "├── "
                lines.append(f"{prefix}{connector}{entry.name}")
                if entry.is_dir():
                    extension = "    " if is_last else "│   "
                    _walk(entry, prefix + extension, depth + 1)

        lines.append(repo_name + "/")
        _walk(repo_path, "", 1)
        return "\n".join(lines[:500])
