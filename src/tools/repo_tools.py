import subprocess
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from src.config import Config


def register_repo_tools(mcp: FastMCP, config: Config):

    @mcp.tool()
    def list_repos() -> dict:
        """List all configured repositories and their clone status."""
        results = []
        for repo in config.repos:
            repo_path = config.get_repo_path(repo.name)
            results.append({
                "name": repo.name,
                "url": repo.url,
                "language": repo.language,
                "description": repo.description,
                "cloned": repo_path.is_dir(),
                "local_path": str(repo_path),
            })
        return {"repos": results}

    @mcp.tool()
    def clone_repo(repo_name: str) -> str:
        """Clone a repository to the local workspace.

        Args:
            repo_name: Name of the repo to clone (e.g. 'voice-backend-v2')
        """
        repo_cfg = config.get_repo(repo_name)
        if not repo_cfg:
            return f"Error: Unknown repo '{repo_name}'. Available: {config.repo_names()}"

        repo_path = config.get_repo_path(repo_name)
        if repo_path.is_dir():
            return f"Repo '{repo_name}' already cloned at {repo_path}"

        config.workspace_path.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(
            ["git", "clone", repo_cfg.url, str(repo_path)],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            return f"Error cloning: {result.stderr}"
        return f"Cloned '{repo_name}' to {repo_path}"

    @mcp.tool()
    def clone_all_repos() -> str:
        """Clone all configured repositories that aren't already cloned."""
        results = []
        for repo in config.repos:
            repo_path = config.get_repo_path(repo.name)
            if repo_path.is_dir():
                results.append(f"{repo.name}: already cloned")
                continue
            config.workspace_path.mkdir(parents=True, exist_ok=True)
            result = subprocess.run(
                ["git", "clone", repo.url, str(repo_path)],
                capture_output=True, text=True,
            )
            if result.returncode != 0:
                results.append(f"{repo.name}: ERROR - {result.stderr.strip()}")
            else:
                results.append(f"{repo.name}: cloned")
        return "\n".join(results)

    @mcp.tool()
    def get_repo_info(repo_name: str) -> dict:
        """Get detailed info about a repository including branch, remotes, and recent commits.

        Args:
            repo_name: Name of the repo
        """
        repo_cfg = config.get_repo(repo_name)
        if not repo_cfg:
            return {"error": f"Unknown repo '{repo_name}'"}

        repo_path = config.get_repo_path(repo_name)
        if not repo_path.is_dir():
            return {"error": f"Repo '{repo_name}' not cloned. Use clone_repo first."}

        def run_git(*args):
            r = subprocess.run(
                ["git", *args], cwd=str(repo_path),
                capture_output=True, text=True,
            )
            return r.stdout.strip() if r.returncode == 0 else f"ERROR: {r.stderr.strip()}"

        return {
            "name": repo_name,
            "path": str(repo_path),
            "language": repo_cfg.language,
            "current_branch": run_git("branch", "--show-current"),
            "branches": run_git("branch", "-a").split("\n"),
            "remotes": run_git("remote", "-v"),
            "recent_commits": run_git("log", "--oneline", "-10"),
        }

    @mcp.tool()
    def pull_repo(repo_name: str) -> str:
        """Pull latest changes for a repository.

        Args:
            repo_name: Name of the repo
        """
        repo_path = config.get_repo_path(repo_name)
        if not repo_path.is_dir():
            return f"Error: Repo '{repo_name}' not cloned."

        result = subprocess.run(
            ["git", "pull"], cwd=str(repo_path),
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            return f"Error: {result.stderr}"
        return result.stdout.strip()
