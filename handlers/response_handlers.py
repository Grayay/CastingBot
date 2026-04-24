import re
from psycopg import IntegrityError

from services.casting_service import get_casting_by_id, get_casting_by_message, response_exists, save_response
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
RESPOND_CASTING_PAYLOAD_PATTERN = re.compile(r"^respond_casting_(\d+)$")
START_CASTING_ID_PATTERN = re.compile(r"^\d+$")


def _skip_keyboard():
    return {
        "keyboard": [[{"text": SKIP_COMMENT_TEXT}]],
        "resize_keyboard": True,
        "one_time_keyboard": True,
    }


def _remove_keyboard():
    return {"remove_keyboard": True}


def build_respond_payload(casting_id=None, channel_id=None, message_id=None):
    if casting_id is not None:
        return f"respond_casting_{int(casting_id)}"
    return f"{RESPOND_PAYLOAD_PREFIX}_{channel_id}_{message_id}"


def parse_respond_payload(payload):
    if payload is None:
        return None

    payload_text = str(payload).strip()

    by_casting_match = RESPOND_CASTING_PAYLOAD_PATTERN.match(payload_text)
    if by_casting_match:
        return {
            "type": "casting_id",
            "casting_id": int(by_casting_match.group(1)),
        }

    old_match = RESPOND_PAYLOAD_PATTERN.match(payload_text)
    if old_match:
        return {
            "type": "channel_message",
            "channel_id": int(old_match.group(1)),
            "message_id": int(old_match.group(2)),
        }

    plain_id_match = START_CASTING_ID_PATTERN.match(payload_text)
    if plain_id_match:
        return {
            "type": "casting_id",
            "casting_id": int(plain_id_match.group(0)),
        }

    return None


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
    print(
        "Response attempt:",
        {
            "user_id": user_id,
            "username": username,
            "raw_payload": payload,
            "parsed": parsed,
        },
    )
    if parsed is None:
        print("Response payload rejected: invalid format")
        send_message(chat_id, "Некорректная ссылка отклика.")
        return True

    if parsed["type"] == "casting_id":
        casting = get_casting_by_id(parsed["casting_id"])
    else:
        casting = get_casting_by_message(parsed["channel_id"], parsed["message_id"])

    if not casting:
        print(
            "Response payload unavailable:",
            {
                "reason": "casting_not_found",
                "payload": payload,
                "parsed": parsed,
            },
        )
        send_message(chat_id, "Кастинг недоступен.")
        return True

    if casting["is_closed"]:
        print(
            "Response payload unavailable:",
            {
                "reason": "casting_closed",
                "casting_id": casting["id"],
                "is_closed": casting["is_closed"],
                "is_deleted": casting["is_deleted"],
                "channel_id": casting["channel_id"],
                "admin_id": casting["admin_id"],
            },
        )
        send_message(chat_id, "Кастинг уже закрыт.")
        return True

    model = find_model_for_user(user_id, username)
    if not model:
        print(
            "Response decision:",
            {
                "decision": "start_first_time_registration",
                "casting_id": casting["id"],
                "user_id": user_id,
            },
        )
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
        print(
            f"event=save_response_already_exists casting_id={casting['id']} model_id={model['id']} "
            f"user_id={user_id} username={username}"
        )
        print(
            "Response decision:",
            {
                "decision": "already_responded",
                "casting_id": casting["id"],
                "model_id": model["id"],
            },
        )
        send_message(chat_id, "Вы уже откликались на этот кастинг.")
        return True

    print(
        "Response decision:",
        {
            "decision": "start_comment_flow",
            "casting_id": casting["id"],
            "model_id": model["id"],
        },
    )
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
        print(
            f"event=save_response_already_exists casting_id={casting_id} model_id={model['id']} "
            f"user_id={user_id} username={username}"
        )
        clear_user_state(user_id)
        send_message(chat_id, "Вы уже откликались на этот кастинг.")
        return True

    try:
        save_response(casting_id, model["id"], comment=None)
        print(
            f"event=save_response_success casting_id={casting_id} model_id={model['id']} "
            f"user_id={user_id} username={username} comment_present=false source=first_time_registration"
        )
    except IntegrityError:
        print(
            f"event=save_response_already_exists casting_id={casting_id} model_id={model['id']} "
            f"user_id={user_id} username={username} source=first_time_registration"
        )
        clear_user_state(user_id)
        send_message(chat_id, "Вы уже откликались на этот кастинг.")
        return True
    except Exception as error:
        print(
            f"event=save_response_failure casting_id={casting_id} model_id={model['id']} "
            f"user_id={user_id} username={username} reason={error} source=first_time_registration"
        )
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
        print(
            f"event=save_response_already_exists casting_id={casting_id} model_id={model_id} "
            f"user_id={user_id} source=response_comment"
        )
        clear_user_state(user_id)
        send_message(chat_id, "Вы уже откликались на этот кастинг.", reply_markup=_remove_keyboard())
        return True

    try:
        save_response(casting_id, model_id, comment=comment)
        print(
            f"event=save_response_success casting_id={casting_id} model_id={model_id} "
            f"user_id={user_id} comment_present={comment is not None} source=response_comment"
        )
    except IntegrityError:
        print(
            f"event=save_response_already_exists casting_id={casting_id} model_id={model_id} "
            f"user_id={user_id} source=response_comment"
        )
        clear_user_state(user_id)
        send_message(chat_id, "Вы уже откликались на этот кастинг.", reply_markup=_remove_keyboard())
        return True
    except Exception as error:
        print(
            f"event=save_response_failure casting_id={casting_id} model_id={model_id} "
            f"user_id={user_id} reason={error} source=response_comment"
        )
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
