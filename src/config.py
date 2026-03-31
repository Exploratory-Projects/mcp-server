import json
import os
from pathlib import Path
from pydantic import BaseModel


class RepoConfig(BaseModel):
    name: str
    url: str
    language: str
    description: str


class Config(BaseModel):
    workspace_dir: str
    github_org: str
    repos: list[RepoConfig]

    @property
    def workspace_path(self) -> Path:
        return Path(self.workspace_dir).resolve()

    def get_repo(self, name: str) -> RepoConfig | None:
        for repo in self.repos:
            if repo.name == name:
                return repo
        return None

    def get_repo_path(self, name: str) -> Path:
        return self.workspace_path / name

    def repo_names(self) -> list[str]:
        return [r.name for r in self.repos]


def load_config(config_path: str | None = None) -> Config:
    if config_path is None:
        config_path = os.environ.get(
            "MCP_CONFIG_PATH",
            str(Path(__file__).parent.parent / "config.json"),
        )
    with open(config_path) as f:
        data = json.load(f)
    return Config(**data)
