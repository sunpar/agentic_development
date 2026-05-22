import os
from pathlib import Path


FACTORY_ROOT = Path(os.environ.get("FACTORY_ROOT", Path(__file__).resolve().parents[1])).expanduser().resolve()
CODEX_HOME = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).expanduser().resolve()
AGENTS_HOME = Path(os.environ.get("AGENTS_HOME", Path.home() / ".agents")).expanduser().resolve()


def script_path(name: str) -> Path:
    return FACTORY_ROOT / "scripts" / name


def fixture_path(name: str) -> Path:
    return FACTORY_ROOT / "fixtures" / name
