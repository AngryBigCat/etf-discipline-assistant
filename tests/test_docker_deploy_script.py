from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_deploy_script_runs_expected_safe_compose_steps() -> None:
    script = (ROOT / "scripts" / "deploy_docker.sh").read_text(encoding="utf-8")

    assert "docker compose" in script
    assert '"${COMPOSE[@]}" build' in script
    assert '"${COMPOSE[@]}" run --rm etf-init' in script
    assert '"${COMPOSE[@]}" up -d "${SERVICES[@]}"' in script
    assert "curl -fsS \"$HEALTH_URL\"" in script
    assert "etf-web etf-scheduler" in script


def test_deploy_script_does_not_print_or_expand_env_file() -> None:
    script = (ROOT / "scripts" / "deploy_docker.sh").read_text(encoding="utf-8")

    assert "docker compose config" not in script
    assert "cat .env" not in script
    assert "source .env" not in script
    assert ". .env" not in script


def test_deploy_script_supports_skip_flags() -> None:
    script = (ROOT / "scripts" / "deploy_docker.sh").read_text(encoding="utf-8")

    assert "--skip-build" in script
    assert "--skip-init" in script


def test_deploy_script_does_not_prune_images() -> None:
    script = (ROOT / "scripts" / "deploy_docker.sh").read_text(encoding="utf-8")

    assert "docker image rm" not in script
    assert "docker image prune" not in script
