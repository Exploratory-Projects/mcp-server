"""Pattern-aware code scaffolding tools.

These tools read existing code to understand patterns, then generate new code
that matches those patterns exactly. This is the key advantage over direct repo
access — instead of reading 5 files to understand the pattern then writing from
scratch, one tool call produces correct boilerplate.
"""

import json
import re
import subprocess
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from src.config import Config


def _ensure_cloned(config: Config, repo_name: str) -> Path | str:
    p = config.get_repo_path(repo_name)
    if not p.is_dir():
        return f"Error: '{repo_name}' not cloned. Use clone_repo('{repo_name}') first."
    return p


def register_scaffold_tools(mcp: FastMCP, config: Config):

    @mcp.tool()
    def scaffold_fastapi_endpoint(
        repo_name: str,
        router_file: str,
        path: str,
        method: str,
        function_name: str,
        description: str,
        request_body: str = "",
        response_fields: str = "",
    ) -> str:
        """Generate a FastAPI endpoint that matches the repo's existing patterns.

        Analyzes the target router file to extract the exact decorator style,
        async vs sync, error handling, response model conventions, then generates
        a matching endpoint. Returns ready-to-paste code.

        Args:
            repo_name: Name of the repo
            router_file: Relative path to the router file (e.g. 'app/routers/users.py')
            path: URL path for the endpoint (e.g. '/users/{user_id}')
            method: HTTP method (get, post, put, delete, patch)
            function_name: Name for the endpoint function
            description: What the endpoint should do
            request_body: Description of request body fields (e.g. 'name: str, email: str, phone: Optional[str]')
            response_fields: Description of response fields (e.g. 'id: str, name: str, created_at: datetime')
        """
        repo = _ensure_cloned(config, repo_name)
        if isinstance(repo, str):
            return repo

        filepath = repo / router_file
        if not filepath.exists():
            return f"Error: {router_file} not found."

        text = filepath.read_text(errors="replace")

        # ── Analyze existing patterns ──────────────────────────────────
        uses_async = "async def" in text
        router_var = "router"
        for match in re.finditer(r'(\w+)\s*=\s*APIRouter', text):
            router_var = match.group(1)

        # Find import style
        imports = [l for l in text.split("\n") if l.startswith("from ") or l.startswith("import ")]

        # Find error handling pattern
        uses_http_exception = "HTTPException" in text
        uses_try_except = "try:" in text

        # Find response model pattern
        uses_response_model = "response_model=" in text

        # Find an existing endpoint as template
        existing_endpoint = None
        pattern = re.compile(
            r'(@' + router_var + r'\.\w+\([^)]*\)[^\n]*\n'
            r'(?:@[^\n]+\n)*'
            r'(?:async\s+)?def\s+\w+\([^)]*\)[^:]*:\s*\n'
            r'(?:[ \t]+[^\n]+\n){1,20})',
            re.MULTILINE
        )
        match = pattern.search(text)
        if match:
            existing_endpoint = match.group()

        # ── Generate new endpoint ──────────────────────────────────────
        out = []
        out.append(f"\n# === Generated endpoint for {method.upper()} {path} ===")
        out.append(f"# Description: {description}")
        out.append(f"# Based on patterns from: {router_file}\n")

        # Generate request model if needed
        if request_body and method.lower() in ("post", "put", "patch"):
            model_name = function_name.replace("_", " ").title().replace(" ", "") + "Request"
            out.append(f"class {model_name}(BaseModel):")
            for field in request_body.split(","):
                field = field.strip()
                if field:
                    out.append(f"    {field}")
            out.append("")

        # Generate response model if needed
        response_model_name = None
        if response_fields:
            response_model_name = function_name.replace("_", " ").title().replace(" ", "") + "Response"
            out.append(f"class {response_model_name}(BaseModel):")
            for field in response_fields.split(","):
                field = field.strip()
                if field:
                    out.append(f"    {field}")
            out.append("")

        # Decorator
        decorator_parts = [f'"{path}"']
        if response_model_name and uses_response_model:
            decorator_parts.append(f"response_model={response_model_name}")
        decorator = f"@{router_var}.{method.lower()}({', '.join(decorator_parts)})"
        out.append(decorator)

        # Function signature
        params = []
        if method.lower() in ("post", "put", "patch") and request_body:
            model_name = function_name.replace("_", " ").title().replace(" ", "") + "Request"
            params.append(f"request: {model_name}")

        # Extract path params
        path_params = re.findall(r'\{(\w+)\}', path)
        for pp in path_params:
            params.append(f"{pp}: str")

        async_prefix = "async " if uses_async else ""
        params_str = ", ".join(params)
        out.append(f'{async_prefix}def {function_name}({params_str}):')
        out.append(f'    """{description}"""')

        # Body with error handling matching repo pattern
        if uses_try_except:
            out.append("    try:")
            out.append(f"        # TODO: Implement {description}")
            out.append(f"        pass")
            out.append("    except Exception as e:")
            if uses_http_exception:
                out.append("        raise HTTPException(status_code=500, detail=str(e))")
            else:
                out.append('        return {"error": str(e)}')
        else:
            out.append(f"    # TODO: Implement {description}")
            out.append(f"    pass")

        out.append("\n# === End generated endpoint ===")

        result = "\n".join(out)

        # Show the existing pattern for reference
        if existing_endpoint:
            result += f"\n\n# Reference — existing endpoint pattern in this file:\n# " + existing_endpoint.replace("\n", "\n# ")

        return result

    @mcp.tool()
    def scaffold_react_component(
        repo_name: str,
        component_name: str,
        directory: str,
        description: str,
        props: str = "",
        component_type: str = "functional",
    ) -> str:
        """Generate a React component matching the repo's patterns (imports, styling, hooks).

        Analyzes existing components to match: import conventions, styling approach
        (Tailwind, CSS modules, styled-components), hooks usage, export style.

        Args:
            repo_name: Name of the repo
            component_name: PascalCase component name (e.g. 'UserProfile')
            directory: Target directory relative to src/components/ (e.g. 'user' or 'dashboard')
            description: What the component should do
            props: Comma-separated props (e.g. 'name: string, onClose: () => void, isOpen?: boolean')
            component_type: 'functional' (default) or 'page'
        """
        repo = _ensure_cloned(config, repo_name)
        if isinstance(repo, str):
            return repo

        # ── Analyze existing patterns ──────────────────────────────────
        components_dir = repo / "src" / "components"
        sample_component = None
        uses_tailwind = False
        uses_cn = False
        uses_forwardref = False
        export_style = "named"  # or "default"

        for f in (components_dir.rglob("*.tsx") if components_dir.exists() else []):
            if f.name == "index.tsx" or "ui/" in str(f.relative_to(repo)):
                continue
            try:
                text = f.read_text(errors="replace")
            except Exception:
                continue

            if "className=" in text or "tailwind" in text.lower():
                uses_tailwind = True
            if "cn(" in text:
                uses_cn = True
            if "forwardRef" in text:
                uses_forwardref = True
            if "export default" in text:
                export_style = "default"

            if sample_component is None and len(text) > 200:
                sample_component = text

        # ── Generate component ─────────────────────────────────────────
        out = []

        # Imports
        out.append('import React from "react";')
        if uses_cn:
            out.append('import { cn } from "@/lib/utils";')

        out.append("")

        # Props interface
        if props:
            out.append(f"interface {component_name}Props {{")
            for prop in props.split(","):
                prop = prop.strip()
                if prop:
                    out.append(f"  {prop};")
            out.append("}")
            out.append("")

        # Component
        props_type = f"{component_name}Props" if props else ""
        props_destructure = ""
        if props:
            prop_names = [p.split(":")[0].strip().replace("?", "") for p in props.split(",") if p.strip()]
            props_destructure = f"{{ {', '.join(prop_names)} }}"

        if export_style == "default":
            if props:
                out.append(f"export default function {component_name}({props_destructure}: {props_type}) {{")
            else:
                out.append(f"export default function {component_name}() {{")
        else:
            if props:
                out.append(f"export const {component_name} = ({props_destructure}: {props_type}) => {{")
            else:
                out.append(f"export const {component_name} = () => {{")

        out.append(f"  // TODO: Implement {description}")
        out.append("  return (")
        if uses_tailwind:
            out.append(f'    <div className="flex flex-col">')
        else:
            out.append(f"    <div>")
        out.append(f"      <h2>{component_name}</h2>")
        out.append(f"      {{/* {description} */}}")
        out.append("    </div>")
        out.append("  );")

        if export_style == "default":
            out.append("}")
        else:
            out.append("};")

        result = "\n".join(out)

        target_path = f"src/components/{directory}/{component_name}.tsx"
        return f"# File: {target_path}\n# Description: {description}\n\n{result}"

    @mcp.tool()
    def scaffold_pydantic_model(
        repo_name: str,
        model_name: str,
        fields: str,
        description: str,
        target_file: str = "",
    ) -> str:
        """Generate a Pydantic model matching the repo's conventions.

        Analyzes existing models for: BaseModel vs BaseSettings, Optional handling,
        Field usage, validator patterns, Config class usage.

        Args:
            repo_name: Name of the repo
            model_name: PascalCase model name (e.g. 'UserProfile')
            fields: Comma-separated fields (e.g. 'name: str, email: str, phone: Optional[str] = None')
            description: What the model represents
            target_file: Optional target file path for context
        """
        repo = _ensure_cloned(config, repo_name)
        if isinstance(repo, str):
            return repo

        # ── Analyze existing patterns ──────────────────────────────────
        uses_field = False
        uses_validator = False
        uses_config_class = False
        uses_optional_import = False
        sample_model = None

        for f in repo.rglob("*.py"):
            if ".git" in f.parts or "__pycache__" in f.parts or "venv" in f.parts:
                continue
            try:
                text = f.read_text(errors="replace")
            except Exception:
                continue

            if "BaseModel" not in text:
                continue

            if "Field(" in text:
                uses_field = True
            if "@validator" in text or "@field_validator" in text:
                uses_validator = True
            if "class Config:" in text or "model_config" in text:
                uses_config_class = True
            if "Optional[" in text:
                uses_optional_import = True

            model_match = re.search(
                r'(class\s+\w+\s*\(\s*BaseModel\s*\)\s*:\s*\n(?:[ \t]+[^\n]+\n){1,15})',
                text
            )
            if model_match and sample_model is None:
                sample_model = model_match.group()

        # ── Generate model ─────────────────────────────────────────────
        out = []
        out.append(f"# Model: {model_name}")
        out.append(f"# Description: {description}\n")

        # Imports
        import_parts = ["BaseModel"]
        if uses_field:
            import_parts.append("Field")
        out.append(f"from pydantic import {', '.join(import_parts)}")

        if uses_optional_import or "Optional" in fields:
            out.append("from typing import Optional, List")
        if "datetime" in fields.lower():
            out.append("from datetime import datetime")
        out.append("")

        out.append(f'class {model_name}(BaseModel):')
        out.append(f'    """{description}"""')
        out.append("")

        for field in fields.split(","):
            field = field.strip()
            if field:
                out.append(f"    {field}")

        if uses_config_class:
            out.append("")
            out.append("    model_config = {")
            out.append('        "from_attributes": True,')
            out.append("    }")

        result = "\n".join(out)

        if sample_model:
            result += f"\n\n# Reference — existing model pattern in this repo:\n# " + sample_model.replace("\n", "\n# ")

        return result

    @mcp.tool()
    def scaffold_test(repo_name: str, target_file: str) -> str:
        """Generate a test file for a given source file, matching the repo's test conventions.

        Analyzes the target file to extract testable functions/classes, and existing
        test files to match the testing framework and patterns.

        Args:
            repo_name: Name of the repo
            target_file: Relative path to the source file to test
        """
        repo = _ensure_cloned(config, repo_name)
        if isinstance(repo, str):
            return repo

        filepath = repo / target_file
        if not filepath.exists():
            return f"Error: {target_file} not found."

        text = filepath.read_text(errors="replace")
        repo_cfg = config.get_repo(repo_name)
        lang = repo_cfg.language if repo_cfg else "python"

        # ── Extract testable items ─────────────────────────────────────
        functions = re.findall(r'(?:async\s+)?def\s+(\w+)\s*\(', text)
        classes = re.findall(r'class\s+(\w+)', text)
        # Filter out private/dunder
        functions = [f for f in functions if not f.startswith("_")]

        # ── Detect test framework ──────────────────────────────────────
        uses_pytest = False
        existing_test_pattern = None
        for tf in repo.rglob("test_*.py"):
            uses_pytest = True
            if existing_test_pattern is None:
                existing_test_pattern = tf.read_text(errors="replace")[:2000]
            break

        out = []
        module_path = target_file.replace("/", ".").replace(".py", "")

        if lang == "python":
            out.append(f"# Tests for {target_file}")
            out.append(f"import pytest")
            out.append(f"from {module_path} import {', '.join(functions[:10])}")
            out.append("")

            for func in functions[:15]:
                out.append(f"def test_{func}():")
                out.append(f'    """Test {func}."""')
                out.append(f"    # TODO: Implement test")
                out.append(f"    result = {func}()")
                out.append(f"    assert result is not None")
                out.append("")

            for cls in classes[:5]:
                out.append(f"class Test{cls}:")
                out.append(f'    """Tests for {cls}."""')
                out.append("")
                out.append(f"    def test_init(self):")
                out.append(f"        # TODO: Implement test")
                out.append(f"        instance = {cls}()")
                out.append(f"        assert instance is not None")
                out.append("")

        elif lang == "typescript":
            out.append(f'import {{ describe, it, expect }} from "vitest";')
            out.append(f'// import from "{target_file.replace(".tsx", "").replace(".ts", "")}";')
            out.append("")
            out.append(f'describe("{Path(target_file).stem}", () => {{')
            for func in functions[:10]:
                out.append(f'  it("should {func}", () => {{')
                out.append(f"    // TODO: Implement test")
                out.append(f"    expect(true).toBe(true);")
                out.append(f"  }});")
                out.append("")
            out.append("});")

        result = "\n".join(out)

        # Suggest file path
        if lang == "python":
            test_path = "tests/test_" + Path(target_file).name
        else:
            test_path = target_file.replace(".tsx", ".test.tsx").replace(".ts", ".test.ts")

        return f"# Suggested file: {test_path}\n\n{result}"

    @mcp.tool()
    def create_new_repo(
        name: str,
        template: str,
        description: str,
    ) -> str:
        """Create a new GitHub repo with standard project structure.

        Templates available:
        - 'fastapi': Python FastAPI service with Docker, Pydantic, Firestore patterns
        - 'react-vite': React + Vite + TypeScript + Tailwind + shadcn/ui
        - 'python-service': Generic Python service with Docker

        Args:
            name: Repo name (e.g. 'new-service')
            template: Template type ('fastapi', 'react-vite', 'python-service')
            description: Repo description
        """
        org = config.github_org
        repo_path = config.workspace_path / name

        if repo_path.exists():
            return f"Error: Directory {repo_path} already exists."

        # Create repo on GitHub
        result = subprocess.run(
            ["gh", "repo", "create", f"{org}/{name}", "--private", "--description", description, "--clone"],
            cwd=str(config.workspace_path),
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            return f"Error creating repo: {result.stderr}"

        # Generate template files
        files = {}

        if template == "fastapi":
            files["requirements.txt"] = "fastapi>=0.100.0\nuvicorn[standard]>=0.20.0\npydantic>=2.0.0\nfirebase-admin>=6.0.0\npython-dotenv>=1.0.0\nhttpx>=0.24.0\n"

            files["Dockerfile"] = """FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s CMD curl -f http://localhost:8080/health || exit 1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
"""

            files["app/__init__.py"] = ""
            files["app/main.py"] = """from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="{name}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health():
    return {{"status": "ok"}}
""".format(name=name)

            files["app/core/__init__.py"] = ""
            files["app/core/config.py"] = """import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    port: int = 8080
    log_level: str = "INFO"

    class Config:
        env_file = ".env"

settings = Settings()
"""
            files["app/core/firebase.py"] = """import firebase_admin
from firebase_admin import credentials, firestore

cred = credentials.ApplicationDefault()
firebase_admin.initialize_app(cred)
db = firestore.client()
"""
            files["app/routers/__init__.py"] = ""
            files["app/models/__init__.py"] = ""
            files["env.example"] = "FIREBASE_CREDENTIALS=\nLOG_LEVEL=INFO\nPORT=8080\n"
            files[".gitignore"] = "__pycache__/\n*.py[cod]\n.env\n.venv/\nvenv/\n*.egg-info/\n"

            files["deploy.sh"] = f"""#!/bin/bash
set -e
PROJECT_ID="allyai-website"
SERVICE_NAME="{name}"
REGION="us-central1"
gcloud builds submit --tag gcr.io/$PROJECT_ID/$SERVICE_NAME --platform managed
gcloud run deploy $SERVICE_NAME --image gcr.io/$PROJECT_ID/$SERVICE_NAME --region $REGION --platform managed --allow-unauthenticated
"""

        elif template == "react-vite":
            files["package.json"] = json.dumps({
                "name": name,
                "private": True,
                "version": "0.0.0",
                "type": "module",
                "scripts": {
                    "dev": "vite",
                    "build": "tsc && vite build",
                    "preview": "vite preview",
                },
                "dependencies": {
                    "react": "^18.3.0",
                    "react-dom": "^18.3.0",
                    "react-router-dom": "^6.20.0",
                },
                "devDependencies": {
                    "@types/react": "^18.3.0",
                    "@types/react-dom": "^18.3.0",
                    "@vitejs/plugin-react-swc": "^3.7.0",
                    "autoprefixer": "^10.4.18",
                    "postcss": "^8.4.38",
                    "tailwindcss": "^3.4.0",
                    "typescript": "^5.5.0",
                    "vite": "^5.4.0",
                },
            }, indent=2)

            files["index.html"] = f"""<!DOCTYPE html>
<html lang="en">
  <head><meta charset="UTF-8" /><meta name="viewport" content="width=device-width, initial-scale=1.0" /><title>{name}</title></head>
  <body><div id="root"></div><script type="module" src="/src/main.tsx"></script></body>
</html>"""

            files["src/main.tsx"] = """import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode><App /></React.StrictMode>
);
"""
            files["src/App.tsx"] = """import { BrowserRouter, Routes, Route } from "react-router-dom";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<div>Home</div>} />
      </Routes>
    </BrowserRouter>
  );
}
"""
            files["src/index.css"] = '@tailwind base;\n@tailwind components;\n@tailwind utilities;\n'
            files[".gitignore"] = "node_modules/\ndist/\n.env\n"
            files["tsconfig.json"] = json.dumps({
                "compilerOptions": {
                    "target": "ES2020", "useDefineForClassFields": True, "lib": ["ES2020", "DOM"],
                    "module": "ESNext", "skipLibCheck": True, "moduleResolution": "bundler",
                    "jsx": "react-jsx", "strict": True, "noUnusedLocals": True,
                    "baseUrl": ".", "paths": {"@/*": ["./src/*"]},
                },
                "include": ["src"],
            }, indent=2)

        elif template == "python-service":
            files["requirements.txt"] = "pydantic>=2.0.0\npython-dotenv>=1.0.0\nhttpx>=0.24.0\n"
            files["Dockerfile"] = "FROM python:3.11-slim\nWORKDIR /app\nCOPY requirements.txt .\nRUN pip install --no-cache-dir -r requirements.txt\nCOPY . .\nCMD [\"python\", \"main.py\"]\n"
            files["main.py"] = f'"""Entry point for {name}."""\n\ndef main():\n    print("Hello from {name}")\n\nif __name__ == "__main__":\n    main()\n'
            files[".gitignore"] = "__pycache__/\n*.py[cod]\n.env\n.venv/\nvenv/\n"
            files["env.example"] = "# Environment variables\n"
        else:
            return f"Error: Unknown template '{template}'. Use: fastapi, react-vite, python-service"

        # Write files
        for path, content in files.items():
            full_path = repo_path / path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content)

        # Commit and push
        subprocess.run(["git", "add", "-A"], cwd=str(repo_path), capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", f"Initial {template} project scaffold"],
            cwd=str(repo_path), capture_output=True,
        )
        push_result = subprocess.run(
            ["git", "push", "-u", "origin", "main"],
            cwd=str(repo_path), capture_output=True, text=True,
        )

        return f"Created repo {org}/{name} with {template} template at {repo_path}\nFiles: {', '.join(files.keys())}\nPush: {push_result.stdout or push_result.stderr}"

    @mcp.tool()
    def scaffold_from_example(
        repo_name: str,
        example_file: str,
        new_name: str,
        modifications: str,
    ) -> str:
        """Generate new code by cloning an existing file and describing modifications.

        This is the most powerful scaffolding tool — reads an existing file as a template,
        then describes what to change. Use this for: new dealership handler from existing one,
        new router from existing one, new component from similar one.

        Args:
            repo_name: Name of the repo
            example_file: Relative path to the file to use as template
            new_name: Name for the new file/module
            modifications: Description of what should be different in the new version
        """
        repo = _ensure_cloned(config, repo_name)
        if isinstance(repo, str):
            return repo

        filepath = repo / example_file
        if not filepath.exists():
            return f"Error: {example_file} not found."

        text = filepath.read_text(errors="replace")

        # Return the template with clear modification instructions
        out = []
        out.append(f"# Scaffold new '{new_name}' based on '{example_file}'")
        out.append(f"# Modifications needed: {modifications}")
        out.append(f"# Original file: {len(text.splitlines())} lines, {len(text)} bytes")
        out.append(f"#")
        out.append(f"# Below is the complete template. Apply the modifications described above.")
        out.append(f"# Key patterns to preserve: imports, error handling, naming conventions.")
        out.append("")

        # Include the full file content (truncated at 500 lines for huge files)
        lines = text.split("\n")
        if len(lines) > 500:
            out.append("# (Showing first 500 lines — file has {len(lines)} total)")
            out.extend(lines[:500])
        else:
            out.extend(lines)

        return "\n".join(out)
