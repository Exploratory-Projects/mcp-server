import subprocess
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from src.config import Config


def _run_git(repo_path: Path, *args) -> tuple[bool, str]:
    result = subprocess.run(
        ["git", *args], cwd=str(repo_path),
        capture_output=True, text=True,
    )
    output = result.stdout.strip() or result.stderr.strip()
    return result.returncode == 0, output


def _validate_repo(config: Config, repo_name: str) -> Path | str:
    repo_path = config.get_repo_path(repo_name)
    if not repo_path.is_dir():
        return f"Error: Repo '{repo_name}' not cloned. Use clone_repo first."
    return repo_path


def register_git_tools(mcp: FastMCP, config: Config):

    @mcp.tool()
    def git_status(repo_name: str) -> str:
        """Get the git status of a repository.

        Args:
            repo_name: Name of the repo
        """
        repo_path = _validate_repo(config, repo_name)
        if isinstance(repo_path, str):
            return repo_path
        ok, output = _run_git(repo_path, "status")
        return output

    @mcp.tool()
    def git_diff(repo_name: str, staged: bool = False, file_path: str = "") -> str:
        """Get the git diff for a repository.

        Args:
            repo_name: Name of the repo
            staged: If True, show staged changes (default False)
            file_path: Optional specific file to diff
        """
        repo_path = _validate_repo(config, repo_name)
        if isinstance(repo_path, str):
            return repo_path
        args = ["diff"]
        if staged:
            args.append("--staged")
        if file_path:
            args.extend(["--", file_path])
        ok, output = _run_git(repo_path, *args)
        return output or "No changes."

    @mcp.tool()
    def git_log(repo_name: str, count: int = 20, branch: str = "") -> str:
        """Get git commit log.

        Args:
            repo_name: Name of the repo
            count: Number of commits to show (default 20)
            branch: Optional branch name (default: current branch)
        """
        repo_path = _validate_repo(config, repo_name)
        if isinstance(repo_path, str):
            return repo_path
        args = ["log", f"--oneline", f"-{count}"]
        if branch:
            args.append(branch)
        ok, output = _run_git(repo_path, *args)
        return output

    @mcp.tool()
    def git_branch(repo_name: str, branch_name: str = "", create: bool = False, delete: bool = False) -> str:
        """List, create, or delete branches.

        Args:
            repo_name: Name of the repo
            branch_name: Branch name (required for create/delete)
            create: Create a new branch and switch to it
            delete: Delete the branch
        """
        repo_path = _validate_repo(config, repo_name)
        if isinstance(repo_path, str):
            return repo_path

        if not branch_name:
            ok, output = _run_git(repo_path, "branch", "-a")
            return output

        if create:
            ok, output = _run_git(repo_path, "checkout", "-b", branch_name)
            return output if ok else f"Error: {output}"

        if delete:
            ok, output = _run_git(repo_path, "branch", "-d", branch_name)
            return output if ok else f"Error: {output}"

        # Switch to existing branch
        ok, output = _run_git(repo_path, "checkout", branch_name)
        return output if ok else f"Error: {output}"

    @mcp.tool()
    def git_checkout(repo_name: str, ref: str) -> str:
        """Checkout a branch, tag, or commit.

        Args:
            repo_name: Name of the repo
            ref: Branch name, tag, or commit hash
        """
        repo_path = _validate_repo(config, repo_name)
        if isinstance(repo_path, str):
            return repo_path
        ok, output = _run_git(repo_path, "checkout", ref)
        return output if ok else f"Error: {output}"

    @mcp.tool()
    def git_add(repo_name: str, files: list[str] | None = None) -> str:
        """Stage files for commit.

        Args:
            repo_name: Name of the repo
            files: List of file paths to stage (None = all changes)
        """
        repo_path = _validate_repo(config, repo_name)
        if isinstance(repo_path, str):
            return repo_path

        if files:
            ok, output = _run_git(repo_path, "add", *files)
        else:
            ok, output = _run_git(repo_path, "add", "-A")
        return "Staged." if ok else f"Error: {output}"

    @mcp.tool()
    def git_commit(repo_name: str, message: str) -> str:
        """Commit staged changes.

        Args:
            repo_name: Name of the repo
            message: Commit message
        """
        repo_path = _validate_repo(config, repo_name)
        if isinstance(repo_path, str):
            return repo_path
        ok, output = _run_git(repo_path, "commit", "-m", message)
        return output if ok else f"Error: {output}"

    @mcp.tool()
    def git_push(repo_name: str, branch: str = "", set_upstream: bool = False) -> str:
        """Push commits to remote.

        Args:
            repo_name: Name of the repo
            branch: Branch to push (default: current branch)
            set_upstream: Set upstream tracking (-u flag)
        """
        repo_path = _validate_repo(config, repo_name)
        if isinstance(repo_path, str):
            return repo_path

        args = ["push"]
        if set_upstream:
            args.append("-u")
        args.append("origin")
        if branch:
            args.append(branch)
        ok, output = _run_git(repo_path, *args)
        return output if ok else f"Error: {output}"

    @mcp.tool()
    def git_pull(repo_name: str, branch: str = "") -> str:
        """Pull latest changes from remote.

        Args:
            repo_name: Name of the repo
            branch: Branch to pull (default: current branch)
        """
        repo_path = _validate_repo(config, repo_name)
        if isinstance(repo_path, str):
            return repo_path
        args = ["pull"]
        if branch:
            args.extend(["origin", branch])
        ok, output = _run_git(repo_path, *args)
        return output if ok else f"Error: {output}"

    @mcp.tool()
    def git_stash(repo_name: str, pop: bool = False) -> str:
        """Stash or pop stashed changes.

        Args:
            repo_name: Name of the repo
            pop: If True, pop the latest stash
        """
        repo_path = _validate_repo(config, repo_name)
        if isinstance(repo_path, str):
            return repo_path
        args = ["stash"]
        if pop:
            args.append("pop")
        ok, output = _run_git(repo_path, *args)
        return output if ok else f"Error: {output}"

    @mcp.tool()
    def create_pull_request(repo_name: str, title: str, body: str, base: str = "main", head: str = "") -> str:
        """Create a GitHub pull request using gh CLI.

        Args:
            repo_name: Name of the repo
            title: PR title
            body: PR description/body
            base: Base branch (default 'main')
            head: Head branch (default: current branch)
        """
        repo_path = _validate_repo(config, repo_name)
        if isinstance(repo_path, str):
            return repo_path

        cmd = ["gh", "pr", "create", "--title", title, "--body", body, "--base", base]
        if head:
            cmd.extend(["--head", head])

        result = subprocess.run(cmd, cwd=str(repo_path), capture_output=True, text=True)
        if result.returncode != 0:
            return f"Error: {result.stderr.strip()}"
        return result.stdout.strip()

    @mcp.tool()
    def run_command(repo_name: str, command: str) -> str:
        """Run a shell command in the context of a repository directory.

        Args:
            repo_name: Name of the repo
            command: Shell command to execute
        """
        repo_path = _validate_repo(config, repo_name)
        if isinstance(repo_path, str):
            return repo_path

        result = subprocess.run(
            command, shell=True, cwd=str(repo_path),
            capture_output=True, text=True, timeout=120,
        )
        output = result.stdout + result.stderr
        return output.strip() or "(no output)"
