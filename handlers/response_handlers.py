import re
from psycopg import IntegrityError

from services.casting_service import get_casting_by_message, response_exists, save_response
from services.model_service import (
    create_or_get_self_registered_model,
    find_model_for_user,
    update_model_telegram_id,
)
from services.telegram_api import send_message
from state import clear_user_state, get_user_state, set_user_state


SKIP_COMMENT_TEXT = "Пропустить"
RESPOND_PAYLOAD_PREFIX = "respond"
RESPOND_PAYLOAD_PATTERN = re.compile(r"^respond_(-?\d+)_(\d+)$")


def _skip_keyboard():
    return {
        "keyboard": [[{"text": SKIP_COMMENT_TEXT}]],
        "resize_keyboard": True,
        "one_time_keyboard": True,
    }


def _remove_keyboard():
    return {"remove_keyboard": True}


def build_respond_payload(channel_id, message_id):
    return f"{RESPOND_PAYLOAD_PREFIX}_{channel_id}_{message_id}"


def parse_respond_payload(payload):
    if payload is None:
        return None

    match = RESPOND_PAYLOAD_PATTERN.match(str(payload).strip())
    if not match:
        return None

    return int(match.group(1)), int(match.group(2))


def start_response_comment_flow(user_id, casting_id, model_id):
    set_user_state(
        user_id,
        {
            "flow": "response_comment",
            "step": "await_comment",
            "casting_id": casting_id,
            "model_id": model_id,
        },
    )
    result = send_message(
        user_id,
        "Отправьте комментарий к отклику одним сообщением или нажмите «Пропустить».",
        reply_markup=_skip_keyboard(),
    )
    return bool(result.get("ok"))


def handle_start_response_payload(chat_id, user_id, username, payload):
    parsed = parse_respond_payload(payload)
    if parsed is None:
        send_message(chat_id, "Некорректная ссылка отклика.")
        return True

    channel_id, message_id = parsed
    casting = get_casting_by_message(channel_id, message_id)
    if not casting:
        send_message(chat_id, "Кастинг недоступен.")
        return True

    if casting["is_closed"]:
        send_message(chat_id, "Кастинг уже закрыт.")
        return True

    model = find_model_for_user(user_id, username)
    if not model:
        set_user_state(
            user_id,
            {
                "flow": "first_time_registration",
                "step": "await_full_name",
                "casting_id": casting["id"],
                "username": username,
            },
        )
        send_message(chat_id, "Вы впервые откликаетесь. Введите ваше ФИО одним сообщением.")
        return True

    if model["telegram_id"] is None:
        update_model_telegram_id(model["id"], user_id)

    if response_exists(casting["id"], model["id"]):
        send_message(chat_id, "Вы уже откликались на этот кастинг.")
        return True

    start_response_comment_flow(
        user_id=user_id,
        casting_id=casting["id"],
        model_id=model["id"],
    )
    return True


def handle_first_time_registration_flow(chat_id, user_id, message):
    state = get_user_state(user_id)

    if state.get("flow") != "first_time_registration" or state.get("step") != "await_full_name":
        return False

    casting_id = state.get("casting_id")
    username = state.get("username")
    if not casting_id:
        clear_user_state(user_id)
        send_message(chat_id, "Сессия регистрации сброшена. Откликнитесь на кастинг снова.")
        return True

    text = message.get("text")
    if text is None:
        send_message(chat_id, "Введите ФИО текстом одним сообщением.")
        return True

    full_name = text.strip()
    if not full_name:
        send_message(chat_id, "ФИО не может быть пустым. Введите ФИО одним сообщением.")
        return True

    model, _ = create_or_get_self_registered_model(
        full_name=full_name,
        telegram_id=user_id,
        username=username,
    )
    if not model:
        send_message(chat_id, "Не удалось завершить регистрацию. Попробуйте позже.")
        return True

    if model.get("telegram_id") is None:
        update_model_telegram_id(model["id"], user_id)

    if response_exists(casting_id, model["id"]):
        clear_user_state(user_id)
        send_message(chat_id, "Вы уже откликались на этот кастинг.")
        return True

    try:
        save_response(casting_id, model["id"], comment=None)
    except IntegrityError:
        clear_user_state(user_id)
        send_message(chat_id, "Вы уже откликались на этот кастинг.")
        return True
    except Exception:
        clear_user_state(user_id)
        send_message(chat_id, "Не удалось отправить отклик. Попробуйте снова по ссылке отклика.")
        return True

    clear_user_state(user_id)
    send_message(chat_id, "Регистрация завершена. Ваш отклик отправлен.")
    return True


def handle_response_comment_flow(chat_id, user_id, message):
    state = get_user_state(user_id)

    if state.get("flow") != "response_comment" or state.get("step") != "await_comment":
        return False

    casting_id = state.get("casting_id")
    model_id = state.get("model_id")
    if not casting_id or not model_id:
        clear_user_state(user_id)
        send_message(chat_id, "Сессия отклика сброшена. Попробуйте откликнуться снова.", reply_markup=_remove_keyboard())
        return True

    text = message.get("text")
    if text is None:
        send_message(chat_id, "Комментарий должен быть текстом или нажмите «Пропустить».", reply_markup=_skip_keyboard())
        return True

    cleaned_text = text.strip()
    if cleaned_text == SKIP_COMMENT_TEXT:
        comment = None
    elif cleaned_text:
        comment = cleaned_text
    else:
        send_message(chat_id, "Введите комментарий одним сообщением или нажмите «Пропустить».", reply_markup=_skip_keyboard())
        return True

    if response_exists(casting_id, model_id):
        clear_user_state(user_id)
        send_message(chat_id, "Вы уже откликались на этот кастинг.", reply_markup=_remove_keyboard())
        return True

    try:
        save_response(casting_id, model_id, comment=comment)
    except IntegrityError:
        clear_user_state(user_id)
        send_message(chat_id, "Вы уже откликались на этот кастинг.", reply_markup=_remove_keyboard())
        return True
    except Exception:
        send_message(
            chat_id,
            "Не удалось отправить отклик. Попробуйте снова по ссылке отклика.",
            reply_markup=_remove_keyboard(),
        )
        clear_user_state(user_id)
        return True

    clear_user_state(user_id)
    send_message(chat_id, "Отклик отправлен.", reply_markup=_remove_keyboard())
    return True
