from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def test_pre_commit_config_includes_gitleaks_secret_scanner() -> None:
    config = yaml.safe_load((ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8"))
    repos = config["repos"]
    hooks = {
        hook["id"]: {"repo": repo["repo"], "rev": repo.get("rev")}
        for repo in repos
        for hook in repo.get("hooks", [])
    }

    assert hooks["gitleaks"] == {
        "repo": "https://github.com/gitleaks/gitleaks",
        "rev": "v8.18.4",
    }
    assert "detect-secrets" in hooks
    assert "detect-private-key" in hooks
