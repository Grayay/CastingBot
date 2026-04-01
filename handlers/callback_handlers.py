from services.casting_service import (
    get_casting_by_message,
    response_exists,
    save_response,
)
from services.model_service import find_model_for_user, update_model_telegram_id
from services.telegram_api import answer_callback


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

    casting = get_casting_by_message(channel_id, message_id)

    if not casting:
        answer_callback(callback_id, "Кастинг недоступен.", show_alert=False)
        return

    if casting["is_closed"]:
        answer_callback(callback_id, "Кастинг уже закрыт.", show_alert=False)
        return

    model = find_model_for_user(user_id, username)

    if not model:
        answer_callback(
            callback_id,
            "Вас нет в базе, напишите администратору.",
            show_alert=True,
        )
        return

    if model["telegram_id"] is None:
        update_model_telegram_id(model["id"], user_id)

    if response_exists(casting["id"], model["id"]):
        answer_callback(callback_id, "Вы уже откликались на этот кастинг.", show_alert=False)
        return

    save_response(casting["id"], model["id"])
    answer_callback(callback_id, "Отклик отправлен.", show_alert=False)