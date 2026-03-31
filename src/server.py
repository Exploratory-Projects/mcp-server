from mcp.server.fastmcp import FastMCP

from src.config import load_config
from src.tools.file_tools import register_file_tools
from src.tools.git_tools import register_git_tools
from src.tools.repo_tools import register_repo_tools

mcp = FastMCP(
    "Dealership AI MCP Server",
    instructions=(
        "MCP server for managing Dealership AI repositories. "
        "Use list_repos to see available repos, clone_repo to clone them, "
        "then use file and git tools to read, edit, search, and manage code."
    ),
)

config = load_config()

register_repo_tools(mcp, config)
register_file_tools(mcp, config)
register_git_tools(mcp, config)


def main():
    mcp.run()


if __name__ == "__main__":
    main()
