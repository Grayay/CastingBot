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


def parse_id_list(value):
    if value is None or str(value).strip() == "":
        return []

    ids = []
    seen = set()
    for part in str(value).split(","):
        part = part.strip()
        if not part:
            continue
        try:
            parsed_id = int(part)
        except ValueError:
            continue
        if parsed_id not in seen:
            ids.append(parsed_id)
            seen.add(parsed_id)
    return ids


def _parse_admins(value, default):
    parsed = parse_id_list(value)
    return parsed if parsed else default


def _legacy_booker_ids_env():
    booker_ids = os.getenv("BOOKER_IDS")
    if booker_ids is not None:
        return booker_ids
    return os.getenv("ADMINS")


def _build_casting_channels(default_channel_id):
    channels = []
    for index in range(1, 7):
        title = (os.getenv(f"CASTING_CHANNEL_{index}_NAME") or f"Канал {index}").strip()
        channel_id = _parse_int(
            os.getenv(f"CASTING_CHANNEL_{index}_ID"),
            default=default_channel_id,
        )
        channels.append(
            {
                "key": f"channel_{index}",
                "title": title,
                "id": channel_id,
            }
        )
    return channels


# Secrets must come from environment on VPS
BOT_TOKEN = os.getenv("BOT_TOKEN") or "PUT_BOT_TOKEN_HERE"
BOT_USERNAME = (os.getenv("BOT_USERNAME") or "").strip().lstrip("@")

# Пример: -1001234567890
CHANNEL_ID = _parse_int(os.getenv("CHANNEL_ID"), default=-1003677854141)
CASTING_CHANNELS = _build_casting_channels(CHANNEL_ID)

# Chief bookers stay env-based permanently.
CHIEF_BOOKER_IDS = parse_id_list(os.getenv("CHIEF_BOOKER_IDS"))

# BOOKER_IDS is bootstrap-only. ADMINS is accepted as a legacy seed source for
# existing deployments that used the old name before the access-control table.
BOOKER_IDS = parse_id_list(_legacy_booker_ids_env())

# Legacy constant kept for old imports/tests only. Do not use for live access.
ADMINS = parse_id_list(os.getenv("ADMINS"))
