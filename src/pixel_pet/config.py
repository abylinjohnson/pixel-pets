import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


DEFAULT_ENV_FILES = (
    ".env",
    ".pixel-pets.env",
    "src/pixel_pet/.env",
)


def load_env_file(filename=None):
    candidates = (
        [filename]
        if filename
        else DEFAULT_ENV_FILES
    )

    for candidate in candidates:
        env_path = PROJECT_ROOT / candidate

        if not env_path.exists():
            continue

        _load_env_path(env_path)
        return str(env_path)

    return None


def _load_env_path(env_path):
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("\"'")

        if key and key not in os.environ:
            os.environ[key] = value
