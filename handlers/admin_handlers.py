from handlers.booker_handlers import handle_booker_management_flow
from handlers.casting_handlers import (
    build_main_menu,
    handle_casting_flow,
    handle_legacy_casting_management,
    handle_select_casting_action,
    start_create_casting,
    start_close_casting,
    start_delete_casting,
    start_view_responsible_booker,
    start_view_responses,
)
from handlers.model_handlers import handle_model_flow, start_add_model
from handlers.response_handlers import (
    handle_first_time_registration_flow,
    handle_response_comment_flow,
    handle_start_response_payload,
)
from services.telegram_api import send_message
from services.access_control import is_authorized_booker
from state import clear_expired_user_state, clear_user_state


def _interrupt_and_start(chat_id, user_id, starter):
    clear_user_state(user_id)
    starter(chat_id, user_id)


def handle_message(update):
    message = update["message"]
    chat_id = message["chat"]["id"]
    user_id = message["from"]["id"]
    text = message.get("text", "").strip()
    username = message["from"].get("username")
    if username:
        username = "@" + username

    if text.startswith("/start"):
        clear_user_state(user_id)
        parts = text.split(maxsplit=1)
        payload = parts[1].strip() if len(parts) > 1 else None
        print(
            "Start command:",
            {
                "user_id": user_id,
                "username": username,
                "raw_text": text,
                "payload": payload,
            },
        )
        if payload:
            if handle_start_response_payload(chat_id, user_id, username, payload):
                return

        if is_authorized_booker(user_id):
            send_message(
                chat_id,
                "Добро пожаловать в систему управления кастингами.",
                reply_markup=build_main_menu(user_id),
            )
            return

        send_message(chat_id, "Откройте ссылку отклика из поста кастинга.")
        return

    if clear_expired_user_state(user_id):
        send_message(
            chat_id,
            "Сессия истекла. Откройте ссылку отклика из поста кастинга или начните действие заново из меню.",
        )
        return

    if handle_response_comment_flow(chat_id, user_id, message):
        return

    if handle_first_time_registration_flow(chat_id, user_id, message):
        return

    if not is_authorized_booker(user_id):
        send_message(chat_id, "Откройте ссылку отклика из поста кастинга или нажмите /start по этой ссылке.")
        return

    if handle_booker_management_flow(chat_id, user_id, text):
        return

    if text == "Создать кастинг":
        _interrupt_and_start(chat_id, user_id, start_create_casting)
        return

    if text == "Посмотреть отклики":
        _interrupt_and_start(chat_id, user_id, start_view_responses)
        return

    if text == "Ответственный букер":
        _interrupt_and_start(chat_id, user_id, start_view_responsible_booker)
        return

    if text == "Закрыть кастинг":
        _interrupt_and_start(chat_id, user_id, start_close_casting)
        return

    if text == "Удалить кастинг":
        _interrupt_and_start(chat_id, user_id, start_delete_casting)
        return

    if text == "Добавить модель":
        _interrupt_and_start(chat_id, user_id, start_add_model)
        return

    if text == "Назад":
        clear_user_state(user_id)
        send_message(chat_id, "Главное меню.", reply_markup=build_main_menu(user_id))
        return

    if handle_model_flow(chat_id, user_id, text):
        return

    if handle_casting_flow(chat_id, user_id, message):
        return

    if handle_select_casting_action(chat_id, user_id, text):
        return

    if handle_legacy_casting_management(chat_id, user_id, text):
        return

    send_message(
        chat_id,
        "Используйте кнопки меню.",
        reply_markup=build_main_menu(user_id),
    )
