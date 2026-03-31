from mcp.server.fastmcp import FastMCP

from src.config import load_config
from src.tools.file_tools import register_file_tools
from src.tools.git_tools import register_git_tools
from src.tools.repo_tools import register_repo_tools
from src.tools.context_tools import register_context_tools
from src.tools.scaffold_tools import register_scaffold_tools
from src.tools.cross_repo_tools import register_cross_repo_tools
from src.tools.validation_tools import register_validation_tools
from src.resources import register_resources, register_prompts

mcp = FastMCP(
    "Dealership AI MCP Server",
    instructions=(
        "Unified MCP server for the Dealership AI / AllyAI platform (7 repos). "
        "Read the repo://overview resource first for full architecture context. "
        "\n\nWorkflow: "
        "1) clone_all_repos() → 2) get_codebase_summary('repo') for architecture → "
        "3) extract_patterns('repo') for conventions → 4) scaffold_* tools for boilerplate → "
        "5) edit_file for customization → 6) validate_changes('repo') before committing. "
        "\n\nCross-repo: search_all_repos() searches everywhere, get_service_map() shows "
        "dependencies, find_shared_models() reveals data contracts, batch_* tools operate "
        "on all repos at once."
    ),
)

config = load_config()

# Core tools — file, git, repo management
register_repo_tools(mcp, config)
register_file_tools(mcp, config)
register_git_tools(mcp, config)

# Intelligence tools — understand codebases deeply
register_context_tools(mcp, config)

# Scaffolding tools — generate pattern-matching code
register_scaffold_tools(mcp, config)

# Cross-repo tools — operate across all repos
register_cross_repo_tools(mcp, config)

# Validation tools — catch issues before committing
register_validation_tools(mcp, config)

# Resources — auto-loaded architecture context
register_resources(mcp, config)

# Prompts — guided task templates
register_prompts(mcp, config)


def main():
    mcp.run()


if __name__ == "__main__":
    main()
