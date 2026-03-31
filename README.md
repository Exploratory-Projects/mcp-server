# Dealership AI MCP Server

MCP (Model Context Protocol) server for managing Dealership AI repositories. Provides tools for file operations, git management, and code search across all project repos.

## Configured Repos

| Repo | Language |
|------|----------|
| voice-backend-v2 | Python |
| admin-dashboard | Python |
| selinium-browser-automation | Python |
| chatbot-backend | Python |
| firebase-backend | Python |
| workflow-builder | Python |
| ally-ai-production | TypeScript |

## Setup

```bash
pip install -e .
```

Or with requirements:

```bash
pip install -r requirements.txt
```

## Running

```bash
# Run directly
python -m src.server

# Or via installed entry point
dealership-mcp
```

## Configuration

Edit `config.json` to modify repos or workspace directory. Set `MCP_CONFIG_PATH` env var to use a custom config location.

## Adding to Claude Code

Add to your Claude Code MCP settings (`~/.claude/settings.json` or project `.claude/settings.json`):

```json
{
  "mcpServers": {
    "dealership-ai": {
      "command": "python",
      "args": ["-m", "src.server"],
      "cwd": "/path/to/mcp-server"
    }
  }
}
```

## Adding to Cursor

Add to `.cursor/mcp.json` in your project:

```json
{
  "mcpServers": {
    "dealership-ai": {
      "command": "python",
      "args": ["-m", "src.server"],
      "cwd": "/path/to/mcp-server"
    }
  }
}
```

## Available Tools

### Repo Management
- `list_repos` - List all configured repos and clone status
- `clone_repo` - Clone a specific repo
- `clone_all_repos` - Clone all repos
- `get_repo_info` - Detailed repo info (branch, remotes, recent commits)
- `pull_repo` - Pull latest changes

### File Operations
- `read_file` - Read file contents with line numbers
- `write_file` - Create or overwrite a file
- `edit_file` - Find-and-replace edit
- `delete_file` - Delete a file
- `list_files` - Glob-based file listing
- `search_code` - Regex search across files (uses ripgrep)
- `get_file_tree` - Directory tree view

### Git Operations
- `git_status` - Working tree status
- `git_diff` - View changes
- `git_log` - Commit history
- `git_branch` - List/create/delete branches
- `git_checkout` - Switch branches
- `git_add` - Stage files
- `git_commit` - Commit changes
- `git_push` - Push to remote
- `git_pull` - Pull from remote
- `git_stash` - Stash/pop changes
- `create_pull_request` - Create GitHub PR (via gh CLI)
- `run_command` - Run arbitrary shell commands in repo context

## Branch Strategy

Each target repo has a dedicated branch in this mcp-server repo for repo-specific tool implementations:
- `voice-backend-v2`
- `admin-dashboard`
- `selinium-browser-automation`
- `chatbot-backend`
- `firebase-backend`
- `workflow-builder`
- `ally-ai-production`
