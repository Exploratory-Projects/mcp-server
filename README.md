# Dealership AI MCP Server

MCP server that gives AI agents superpowers when working across the Dealership AI / AllyAI codebase. Instead of spending 20+ tool calls exploring a repo, agents get instant architecture understanding, pattern-aware code generation, cross-repo search, and one-call validation.

## Why This Exists

Giving an agent direct repo access is slow — they spend most of their time exploring, reading files to understand patterns, and manually validating. This MCP server eliminates that overhead:

| Without MCP Server | With MCP Server |
|---|---|
| 20+ reads to understand a repo | `get_codebase_summary()` — one call |
| Read 5 files to learn the pattern | `extract_patterns()` — one call |
| Search repos one at a time | `search_all_repos()` — all 7 at once |
| Write boilerplate from scratch | `scaffold_*()` — pattern-matching generation |
| Manual lint + type check + test | `validate_changes()` — one call |
| No cross-repo awareness | `get_service_map()` — full dependency graph |

## Setup

```bash
pip install -e .
```

## Adding to Claude Code

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

Add to `.cursor/mcp.json`:
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

## Tool Categories

### Context Tools — Instant Codebase Understanding
- `get_codebase_summary(repo)` — Full architecture: framework, endpoints, models, deps, env vars, biggest files
- `extract_patterns(repo)` — Coding conventions: import style, endpoint patterns, error handling, model patterns, naming
- `get_function_context(repo, func)` — Complete context: definition, callers, callees, tests, imports
- `get_api_surface(repo)` — All endpoints with request/response types and router registration
- `get_dependency_graph(repo)` — Internal module import graph (foundational vs leaf modules)

### Scaffold Tools — Pattern-Aware Code Generation
- `scaffold_fastapi_endpoint(...)` — Generate endpoint matching the repo's exact patterns
- `scaffold_react_component(...)` — Generate component with proper imports, styling, hooks
- `scaffold_pydantic_model(...)` — Generate model matching conventions
- `scaffold_test(repo, file)` — Generate test file for any source file
- `scaffold_from_example(repo, template_file, new_name, modifications)` — Clone + modify any file
- `create_new_repo(name, template, description)` — Create new GitHub repo (fastapi/react-vite/python-service)

### Cross-Repo Tools — Multi-Repo Operations
- `search_all_repos(pattern)` — Search all 7 repos simultaneously
- `get_service_map()` — Discover how services connect: shared Firestore, env vars, external APIs
- `find_shared_models()` — Find data models that appear across repos (API contracts)
- `get_deployment_overview()` — Docker, ports, Cloud Run config for all repos
- `batch_git_status()` — Git status of all repos in one call
- `batch_git_pull()` — Pull all repos at once
- `batch_create_branch(name)` — Create same branch across all repos

### Validation Tools — Quality Before Committing
- `validate_repo(repo)` — Full suite: syntax + lint + type check + tests
- `validate_changes(repo)` — Validate only uncommitted files (fast)
- `check_syntax(repo, file)` — Quick syntax check on one file
- `check_imports(repo, file)` — Verify all imports resolve
- `run_tests(repo)` — Run test suite

### Core Tools — File, Git, Repo Management
- File ops: `read_file`, `write_file`, `edit_file`, `delete_file`, `list_files`, `search_code`, `get_file_tree`
- Git ops: `git_status`, `git_diff`, `git_log`, `git_branch`, `git_checkout`, `git_add`, `git_commit`, `git_push`, `git_pull`, `git_stash`, `create_pull_request`, `run_command`
- Repo ops: `list_repos`, `clone_repo`, `clone_all_repos`, `get_repo_info`, `pull_repo`

## Resources (Auto-Loaded Context)
- `repo://overview` — Complete system architecture and how services connect
- `repo://conventions` — Coding patterns across all repos
- `repo://quick-start` — Step-by-step guide for agents

## Prompts (Task Templates)
- `implement_feature(repo, description)` — Guided feature implementation
- `fix_bug(repo, description)` — Guided bug fixing
- `add_endpoint(repo, description)` — Guided endpoint addition
- `cross_repo_change(description)` — Guided multi-repo changes

## Configured Repos

| Repo | Language | Purpose |
|------|----------|---------|
| voice-backend-v2 | Python | Voice AI agent for dealership phone calls |
| admin-dashboard | Python | Admin panel API for dealership staff |
| selinium-browser-automation | Python | Selenium appointment booking service |
| chatbot-backend | Python | Multi-tenant AI chatbot backend |
| firebase-backend | Python | Core REST API (users, conversations, tasks) |
| workflow-builder | Python | NLP-driven campaign workflow engine |
| ally-ai-production | TypeScript | Marketing/landing site (React + Vite) |
