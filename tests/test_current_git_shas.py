"""Tests for pet_infra.replay._current_git_shas (F024 parents off-by-one fix)."""
import subprocess
from pathlib import Path

import pytest

import pet_infra.replay as replay_mod


def _init_git_repo(repo_dir: Path) -> str:
    repo_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo_dir, check=True)
    subprocess.run(["git", "config", "user.email", "test@test"], cwd=repo_dir, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=repo_dir, check=True)
    (repo_dir / "README.md").write_text("test\n")
    subprocess.run(["git", "add", "."], cwd=repo_dir, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=repo_dir, check=True)
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=repo_dir, text=True
    ).strip()


@pytest.fixture
def fake_monorepo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> dict[str, str]:
    """Build fake <root>/pet-infra/src/pet_infra/replay.py + sibling repos."""
    root = tmp_path
    pet_infra_module_dir = root / "pet-infra" / "src" / "pet_infra"
    pet_infra_module_dir.mkdir(parents=True)
    fake_module = pet_infra_module_dir / "replay.py"
    fake_module.write_text("# stub")
    shas = {
        "pet-train": _init_git_repo(root / "pet-train"),
        "pet-schema": _init_git_repo(root / "pet-schema"),
        "pet-eval": _init_git_repo(root / "pet-eval"),
    }
    # pet-infra itself has .git; collect filters it out.
    _init_git_repo(root / "pet-infra")
    monkeypatch.setattr(replay_mod, "__file__", str(fake_module))
    return shas


def test_current_git_shas_excludes_pet_infra(fake_monorepo: dict[str, str]) -> None:
    """F024: _current_git_shas must NOT include pet-infra (it's the orchestrator)."""
    result = replay_mod._current_git_shas()
    assert "pet-infra" not in result


def test_current_git_shas_returns_hyphenated_keys_for_siblings(
    fake_monorepo: dict[str, str],
) -> None:
    """F024: keys MUST match plugin-side `pet_train.lineage.collect_git_shas` format."""
    result = replay_mod._current_git_shas()
    assert set(result.keys()) == {"pet-train", "pet-schema", "pet-eval"}
    for repo, sha in fake_monorepo.items():
        assert result[repo] == sha


def test_current_git_shas_uses_parents_3_not_4(fake_monorepo: dict[str, str]) -> None:
    """F024: previous parents[4] resolved one level ABOVE the monorepo, returning {}."""
    result = replay_mod._current_git_shas()
    # If parents[4] were used, root would be tmp_path's parent → likely no sibling
    # repos and result == {}. Asserting non-empty proves the fix.
    assert result, "siblings not discovered — parents indexing likely off"
