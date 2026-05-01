from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]


def _dependency_lines(path: Path) -> list[str]:
    return [
        line.strip().lower()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def test_backend_requirements_include_lightgbm_for_closure_risk_model():
    requirements = _dependency_lines(ROOT_DIR / "backend" / "requirements.txt")

    assert any(line.startswith("lightgbm") for line in requirements)


def test_backend_runtime_image_installs_openmp_for_lightgbm():
    dockerfile = (ROOT_DIR / "backend" / "Dockerfile").read_text(encoding="utf-8")
    runtime_stage = dockerfile.split("FROM python:3.12-slim AS runtime", maxsplit=1)[1]

    assert "libgomp1" in runtime_stage
