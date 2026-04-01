import re

from config import CHANNEL_ID
from services.casting_service import (
    close_casting,
    create_casting,
    delete_casting,
    get_casting_by_id_for_admin,
    get_castings_by_admin,
    get_responses_for_casting,
)
from services.telegram_api import send_channel_message, send_message
from state import clear_user_state, get_user_state, set_user_state


def build_main_menu():
    return {
        "keyboard": [
            [{"text": "Создать кастинг"}],
            [{"text": "Посмотреть отклики"}],
            [{"text": "Закрыть кастинг"}],
            [{"text": "Удалить кастинг"}],
            [{"text": "Добавить модель"}],
        ],
        "resize_keyboard": True,
    }


def build_castings_list_keyboard(castings, back_button_text="Назад"):
    keyboard = []

    for casting in castings:
        title = casting["title"]
        short_title = title[:28] + "..." if len(title) > 28 else title
        keyboard.append([{"text": f"#{casting['id']} {short_title}"}])

    keyboard.append([{"text": back_button_text}])

    return {
        "keyboard": keyboard,
        "resize_keyboard": True,
    }


def _format_responses_text(casting, responses):
    lines = [f"Отклики по кастингу «{casting['title']}»:", f"Количество откликов: {len(responses)}"]

    if responses:
        lines.append("")
        for index, response in enumerate(responses, start=1):
            username = response["telegram_username"]
            lines.append(
                f"{index}. {response['full_name']}\n"
                f"{username}\n"
                f"{response['portfolio_link']}"
            )

    return "\n\n".join(lines)


def start_create_casting(chat_id, user_id):
    set_user_state(
        user_id,
        {
            "flow": "create_casting",
            "step": "title",
        },
    )
    send_message(chat_id, "Введите название кастинга.")


def handle_casting_flow(chat_id, user_id, text):
    state = get_user_state(user_id)

    if state.get("flow") != "create_casting":
        return False

    step = state.get("step")

    if step == "title":
        set_user_state(
            user_id,
            {
                "flow": "create_casting",
                "step": "description",
                "title": text.strip(),
            },
        )
        send_message(chat_id, "Введите текст кастинга.")
        return True

    if step == "description":
        title = state["title"]
        description = text.strip()

        reply_markup = {
            "inline_keyboard": [
                [
                    {
                        "text": "Откликнуться",
                        "callback_data": "respond_casting",
                    }
                ]
            ]
        }

        post_text = f"📢 {title}\n\n{description}"

        result = send_channel_message(
            CHANNEL_ID,
            post_text,
            reply_markup=reply_markup,
        )

        if not result.get("ok"):
            clear_user_state(user_id)
            send_message(chat_id, "Не удалось опубликовать кастинг. Проверь токен, ID канала и права бота.")
            return True

        message_id = result["result"]["message_id"]

        create_casting(
            title=title,
            description=description,
            admin_id=user_id,
            message_id=message_id,
            channel_id=CHANNEL_ID,
        )

        clear_user_state(user_id)
        send_message(chat_id, "Кастинг опубликован.", reply_markup=build_main_menu())
        return True

    return False


def _extract_casting_id_from_text(text):
    match = re.match(r"^#(\d+)\b", text.strip())
    if not match:
        return None
    return int(match.group(1))


def _active_castings(castings):
    return [casting for casting in castings if not casting["is_closed"]]


def start_view_responses(chat_id, admin_id):
    castings = _active_castings(get_castings_by_admin(admin_id))

    if not castings:
        send_message(chat_id, "Нет активных кастингов для просмотра откликов.", reply_markup=build_main_menu())
        return

    send_message(
        chat_id,
        "Выберите активный кастинг для просмотра откликов.",
        reply_markup=build_castings_list_keyboard(castings),
    )
    set_user_state(
        admin_id,
        {
            "flow": "select_casting_action",
            "action": "view_responses",
        },
    )


def start_close_casting(chat_id, admin_id):
    castings = _active_castings(get_castings_by_admin(admin_id))

    if not castings:
        send_message(chat_id, "Нет активных кастингов для закрытия.", reply_markup=build_main_menu())
        return

    send_message(
        chat_id,
        "Выберите кастинг, который нужно закрыть.",
        reply_markup=build_castings_list_keyboard(castings),
    )
    set_user_state(
        admin_id,
        {
            "flow": "select_casting_action",
            "action": "close_casting",
        },
    )


def start_delete_casting(chat_id, admin_id):
    castings = get_castings_by_admin(admin_id)

    if not castings:
        send_message(chat_id, "У вас пока нет кастингов для удаления.", reply_markup=build_main_menu())
        return

    send_message(
        chat_id,
        "Выберите кастинг, который нужно удалить.",
        reply_markup=build_castings_list_keyboard(castings),
    )
    set_user_state(
        admin_id,
        {
            "flow": "select_casting_action",
            "action": "delete_casting",
        },
    )


def handle_select_casting_action(chat_id, admin_id, text):
    state = get_user_state(admin_id)

    if state.get("flow") != "select_casting_action":
        return False

    if text == "Назад":
        clear_user_state(admin_id)
        send_message(chat_id, "Главное меню.", reply_markup=build_main_menu())
        return True

    action = state.get("action")
    casting_id = _extract_casting_id_from_text(text)
    if casting_id is None:
        send_message(chat_id, "Выберите кастинг кнопкой из списка.")
        return True

    casting = get_casting_by_id_for_admin(casting_id, admin_id)
    if not casting:
        send_message(chat_id, "Кастинг не найден.")
        return True

    if action == "view_responses":
        if casting["is_closed"]:
            send_message(chat_id, "Этот кастинг уже закрыт. Выберите активный кастинг.")
            return True
        responses = get_responses_for_casting(casting_id, admin_id)
        send_message(chat_id, _format_responses_text(casting, responses))
        return True

    if action == "close_casting":
        if casting["is_closed"]:
            send_message(chat_id, "Кастинг уже закрыт.")
            return True

        success = close_casting(casting_id, admin_id)
        if success:
            clear_user_state(admin_id)
            send_message(chat_id, f"Кастинг «{casting['title']}» закрыт.", reply_markup=build_main_menu())
        else:
            send_message(chat_id, "Не удалось закрыть кастинг.")
        return True

    if action == "delete_casting":
        success = delete_casting(casting_id, admin_id)
        if success:
            clear_user_state(admin_id)
            send_message(chat_id, f"Кастинг «{casting['title']}» удалён из списка.", reply_markup=build_main_menu())
        else:
            send_message(chat_id, "Не удалось удалить кастинг.")
        return True

    clear_user_state(admin_id)
    send_message(chat_id, "Команда устарела. Повторите действие из меню.", reply_markup=build_main_menu())
    return True


def handle_legacy_casting_management(chat_id, admin_id, text):
    state = get_user_state(admin_id)

    if state.get("flow") != "manage_casting":
        return False

    casting_id = state.get("selected_casting_id")
    if not casting_id:
        clear_user_state(admin_id)
        send_message(chat_id, "Сессия управления кастингом сброшена.", reply_markup=build_main_menu())
        return True

    casting = get_casting_by_id_for_admin(casting_id, admin_id)
    if not casting:
        clear_user_state(admin_id)
        send_message(chat_id, "Кастинг больше недоступен.", reply_markup=build_main_menu())
        return True

    if text == "Отклики":
        responses = get_responses_for_casting(casting_id, admin_id)
        send_message(chat_id, _format_responses_text(casting, responses))
        return True

    if text == "Закрыть кастинг":
        if casting["is_closed"]:
            send_message(chat_id, "Кастинг уже закрыт.")
            return True

        success = close_casting(casting_id, admin_id)

        if success:
            send_message(chat_id, "Кастинг закрыт.", reply_markup=build_main_menu())
            clear_user_state(admin_id)
        else:
            send_message(chat_id, "Не удалось закрыть кастинг.")
        return True

    if text == "Удалить кастинг":
        success = delete_casting(casting_id, admin_id)
        if success:
            clear_user_state(admin_id)
            send_message(chat_id, "Кастинг удалён из списка.", reply_markup=build_main_menu())
        else:
            send_message(chat_id, "Не удалось удалить кастинг.")
        return True

    send_message(chat_id, "Используйте кнопки управления кастингом.")
    return True