from services.casting_service import (
    get_casting_by_message,
    response_exists,
)
from handlers.response_handlers import start_response_comment_flow
from services.model_service import find_model_for_user, update_model_telegram_id
from services.telegram_api import answer_callback, send_message
from state import clear_user_state, set_user_state


def handle_callback(update):
    callback = update["callback_query"]
    callback_id = callback["id"]

    user = callback["from"]
    user_id = user["id"]
    username = user.get("username")
    if username:
        username = "@" + username

    message = callback["message"]
    message_id = message["message_id"]
    channel_id = message["chat"]["id"]
    print(
        "Callback response attempt:",
        {
            "user_id": user_id,
            "username": username,
            "channel_id": channel_id,
            "message_id": message_id,
        },
    )

    casting = get_casting_by_message(channel_id, message_id)

    if not casting:
        print(
            "Callback unavailable:",
            {
                "reason": "casting_not_found",
                "channel_id": channel_id,
                "message_id": message_id,
            },
        )
        answer_callback(callback_id, "Кастинг недоступен.", show_alert=False)
        return

    if casting["is_closed"]:
        print(
            "Callback unavailable:",
            {
                "reason": "casting_closed",
                "casting_id": casting["id"],
                "is_closed": casting["is_closed"],
                "is_deleted": casting["is_deleted"],
                "channel_id": casting["channel_id"],
                "admin_id": casting["admin_id"],
            },
        )
        answer_callback(callback_id, "Кастинг уже закрыт.", show_alert=False)
        return

    model = find_model_for_user(user_id, username)

    if not model:
        print(
            "Callback decision:",
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
        dm_result = send_message(user_id, "Вы впервые откликаетесь. Введите ваше ФИО одним сообщением.")
        if not dm_result.get("ok"):
            clear_user_state(user_id)
            answer_callback(
                callback_id,
                "Не удалось написать вам в личные сообщения. Откройте чат с ботом и нажмите /start.",
                show_alert=True,
            )
            return
        answer_callback(callback_id, "Проверьте личные сообщения для регистрации.", show_alert=False)
        return

    if model["telegram_id"] is None:
        update_model_telegram_id(model["id"], user_id)

    if response_exists(casting["id"], model["id"]):
        print(
            "Callback decision:",
            {
                "decision": "already_responded",
                "casting_id": casting["id"],
                "model_id": model["id"],
            },
        )
        answer_callback(callback_id, "Вы уже откликались на этот кастинг.", show_alert=False)
        return

    started = start_response_comment_flow(
        user_id=user_id,
        casting_id=casting["id"],
        model_id=model["id"],
    )
    if not started:
        print(
            "Callback decision:",
            {
                "decision": "dm_unavailable",
                "casting_id": casting["id"],
                "model_id": model["id"],
            },
        )
        answer_callback(
            callback_id,
            "Не удалось написать вам в личные сообщения. Откройте чат с ботом и нажмите /start.",
            show_alert=True,
        )
        return

    print(
        "Callback decision:",
        {
            "decision": "start_comment_flow",
            "casting_id": casting["id"],
            "model_id": model["id"],
        },
    )
    answer_callback(callback_id, "Проверьте личные сообщения для завершения отклика.", show_alert=False)