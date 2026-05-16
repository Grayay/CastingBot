import copy
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import state


@pytest.fixture(autouse=True)
def clear_runtime_state():
    state.user_states.clear()
    yield
    state.user_states.clear()


@pytest.fixture
def telegram_spy():
    calls = []

    def _send(chat_id, text, reply_markup=None):
        calls.append(
            {
                "chat_id": chat_id,
                "text": text,
                "reply_markup": copy.deepcopy(reply_markup),
            }
        )
        return {"ok": True, "result": {"message_id": 1}}

    return calls, _send

