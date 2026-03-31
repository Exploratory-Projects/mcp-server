from mcp.server.fastmcp import FastMCP

from src.config import load_config
from src.tools.file_tools import register_file_tools
from src.tools.git_tools import register_git_tools
from src.tools.repo_tools import register_repo_tools
from src.tools.voice_backend_tools import register_voice_backend_tools
from src.tools.admin_dashboard_tools import register_admin_dashboard_tools
from src.tools.selenium_automation_tools import register_selenium_automation_tools
from src.tools.chatbot_backend_tools import register_chatbot_backend_tools
from src.tools.firebase_backend_tools import register_firebase_backend_tools
from src.tools.workflow_builder_tools import register_workflow_builder_tools
from src.tools.ally_ai_production_tools import register_ally_ai_production_tools

mcp = FastMCP(
    "Dealership AI MCP Server",
    instructions=(
        "Unified MCP server for all Dealership AI / AllyAI repositories. "
        "Provides generic file, git, and repo management tools plus specialized tools "
        "for each repo: voice-backend-v2 (voice AI agents, prompts, vehicle data), "
        "admin-dashboard (API modules, Firestore, campaigns, analytics), "
        "selinium-browser-automation (Selenium flows, dealership configs, Cloud Tasks), "
        "chatbot-backend (store handlers, prompts, inventory, OpenAI tools), "
        "firebase-backend (routers, models, Firestore, post-call AI, email), "
        "workflow-builder (workflow models, LLM service, channel services, APScheduler), "
        "ally-ai-production (React components, Supabase, Vite, shadcn/ui, voice/chat). "
        "Use clone_repo('<name>') or clone_all_repos() to get started."
    ),
)

config = load_config()

# Core tools (all repos)
register_repo_tools(mcp, config)
register_file_tools(mcp, config)
register_git_tools(mcp, config)

# Repo-specific tools
register_voice_backend_tools(mcp, config)
register_admin_dashboard_tools(mcp, config)
register_selenium_automation_tools(mcp, config)
register_chatbot_backend_tools(mcp, config)
register_firebase_backend_tools(mcp, config)
register_workflow_builder_tools(mcp, config)
register_ally_ai_production_tools(mcp, config)


def main():
    mcp.run()


if __name__ == "__main__":
    main()
