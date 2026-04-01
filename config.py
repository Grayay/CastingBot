import os
from pathlib import Path


def _load_dotenv(path):
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv(Path(__file__).resolve().parent / ".env")


def _parse_int(value, default=None):
    if value is None or str(value).strip() == "":
        return default
    return int(str(value).strip())


def _parse_admins(value, default):
    if value is None or str(value).strip() == "":
        return default
    parts = [p.strip() for p in str(value).split(",")]
    return [int(p) for p in parts if p]


# Secrets must come from environment on VPS
BOT_TOKEN = os.getenv("BOT_TOKEN") or "PUT_BOT_TOKEN_HERE"

# Пример: -1001234567890
CHANNEL_ID = _parse_int(os.getenv("CHANNEL_ID"), default=-1003677854141)

# Telegram ID администраторов (comma-separated in env: "123,456")
ADMINS = _parse_admins(os.getenv("ADMINS"), default=[2081888103, 1640758237, 2081888103])