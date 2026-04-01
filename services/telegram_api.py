import requests

from config import BOT_TOKEN


BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"


def _mask_token(token):
    if not token:
        return "<empty>"
    token = str(token).strip()
    if len(token) <= 12:
        return token[:2] + "…" + token[-2:]
    return token[:6] + "…" + token[-4:]


def get_telegram_debug_info():
    token = BOT_TOKEN
    masked = _mask_token(token)
    base_url_masked = f"https://api.telegram.org/bot{masked}"
    return {
        "token_loaded": bool(token and str(token).strip() and token != "PUT_BOT_TOKEN_HERE"),
        "token_preview": masked,
        "base_url_preview": base_url_masked,
    }


def get_updates(offset=None):
    params = {
        "timeout": 30,
    }

    if offset is not None:
        params["offset"] = offset

    try:
        response = requests.get(f"{BASE_URL}/getUpdates", params=params, timeout=35)
    except Exception as e:
        return {"ok": False, "error": f"REQUEST_ERROR: {e}"}

    try:
        return response.json()
    except Exception:
        return {
            "ok": False,
            "error": "NON_JSON_RESPONSE",
            "status_code": response.status_code,
            "text": response.text[:1000],
        }


def send_message(chat_id, text, reply_markup=None):
    payload = {
        "chat_id": chat_id,
        "text": text,
    }

    if reply_markup is not None:
        payload["reply_markup"] = reply_markup

    response = requests.post(f"{BASE_URL}/sendMessage", json=payload, timeout=20)
    return response.json()


def send_channel_message(channel_id, text, reply_markup=None):
    payload = {
        "chat_id": channel_id,
        "text": text,
    }

    if reply_markup is not None:
        payload["reply_markup"] = reply_markup

    response = requests.post(f"{BASE_URL}/sendMessage", json=payload, timeout=20)
    return response.json()


def answer_callback(callback_query_id, text, show_alert=False):
    payload = {
        "callback_query_id": callback_query_id,
        "text": text,
        "show_alert": show_alert,
    }

    response = requests.post(
        f"{BASE_URL}/answerCallbackQuery",
        json=payload,
        timeout=20,
    )
    return response.json()