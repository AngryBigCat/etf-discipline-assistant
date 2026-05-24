from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def test_dockerignore_excludes_runtime_secrets_and_data() -> None:
    patterns = (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()

    assert ".env" in patterns
    assert "data" in patterns
    assert "backups" in patterns
    assert "logs" in patterns
    assert "!.env.example" in patterns


def test_compose_defines_independent_web_scheduler_and_init_services() -> None:
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    services = compose["services"]

    assert compose["name"] == "etf-discipline-assistant"
    assert set(services) == {"etf-init", "etf-web", "etf-scheduler"}
    assert services["etf-web"]["command"] == [
        "streamlit",
        "run",
        "app.py",
        "--server.address=0.0.0.0",
        "--server.port=8501",
    ]
    assert services["etf-scheduler"]["command"] == [
        "python",
        "scripts/scheduler_worker.py",
    ]
    assert services["etf-init"]["command"] == [
        "sh",
        "-c",
        "python scripts/init_db.py && python scripts/sync_assets_from_seed.py",
    ]
    assert "build" in services["etf-init"]
    assert "build" not in services["etf-web"]
    assert "build" not in services["etf-scheduler"]

    assert services["etf-web"]["depends_on"]["etf-init"]["condition"] == (
        "service_completed_successfully"
    )
    assert services["etf-scheduler"]["depends_on"]["etf-init"]["condition"] == (
        "service_completed_successfully"
    )


def test_dockerfile_does_not_copy_env_file_directly() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    from_line = next(line for line in dockerfile.splitlines() if line.startswith("FROM "))
    assert from_line.endswith("python:3.11-slim")
    assert "ARG PROJECT_NAME" not in dockerfile
    assert "LABEL com.etf-discipline-assistant.project" not in dockerfile
    assert "COPY .env" not in dockerfile
    assert "streamlit" in dockerfile
