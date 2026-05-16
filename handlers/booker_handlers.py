import re

from config import CHIEF_BOOKER_IDS
from handlers.casting_handlers import build_main_menu
from services.access_control import (
    add_authorized_booker,
    is_chief_booker,
    list_authorized_bookers,
    remove_authorized_booker,
)
from services.telegram_api import send_message
from state import clear_user_state, get_user_state, set_user_state


BOOKER_MANAGEMENT_TEXT = "👥 Управление букерами"
ADD_BOOKER_TEXT = "➕ Добавить букера"
REMOVE_BOOKER_TEXT = "➖ Удалить букера"
LIST_BOOKERS_TEXT = "📋 Список букеров"
BACK_TEXT = "⬅️ Назад"


def _build_management_menu():
    return {
        "keyboard": [
            [{"text": ADD_BOOKER_TEXT}],
            [{"text": REMOVE_BOOKER_TEXT}],
            [{"text": LIST_BOOKERS_TEXT}],
            [{"text": BACK_TEXT}],
        ],
        "resize_keyboard": True,
    }


def _format_booker_label(booker):
    username = (booker.get("username") or "").strip()
    full_name = (booker.get("full_name") or "").strip()
    details = " ".join(part for part in [username, full_name] if part)
    if details:
        return f"{booker['telegram_id']} {details}"
    return str(booker["telegram_id"])


def _build_remove_booker_keyboard(bookers):
    keyboard = [[{"text": _format_booker_label(booker)}] for booker in bookers]
    keyboard.append([{"text": BACK_TEXT}])
    return {
        "keyboard": keyboard,
        "resize_keyboard": True,
    }


def _parse_telegram_id(text):
    value = (text or "").strip()
    match = re.match(r"^(-?\d+)\b", value)
    candidate = match.group(1) if match else value
    if not re.fullmatch(r"-?\d+", candidate):
        return None
    return int(candidate)


def _format_bookers_list():
    lines = ["Главные букеры (CHIEF_BOOKER_IDS):"]
    if CHIEF_BOOKER_IDS:
        lines.extend(f"• {telegram_id}" for telegram_id in CHIEF_BOOKER_IDS)
    else:
        lines.append("• не настроены")

    lines.append("")
    lines.append("Обычные букеры (authorized_bookers):")
    bookers = list_authorized_bookers()
    if bookers:
        lines.extend(f"• {_format_booker_label(booker)}" for booker in bookers)
    else:
        lines.append("• список пуст")

    lines.append("")
    lines.append("BOOKER_IDS используется только для первого переноса и больше не даёт доступ сам по себе.")
    return "\n".join(lines)


def _deny_management(chat_id, user_id):
    clear_user_state(user_id)
    print(f"event=booker_management_denied actor_id={user_id}")
    send_message(chat_id, "Недостаточно прав для управления букерами.")


def start_booker_management(chat_id, user_id):
    if not is_chief_booker(user_id):
        _deny_management(chat_id, user_id)
        return

    set_user_state(
        user_id,
        {
            "flow": "manage_bookers",
            "step": "menu",
        },
    )
    send_message(chat_id, "Управление букерами.", reply_markup=_build_management_menu())


def _start_add_booker(chat_id, user_id):
    set_user_state(
        user_id,
        {
            "flow": "manage_bookers",
            "step": "await_add_booker_id",
        },
    )
    send_message(chat_id, "Отправьте Telegram ID букера, которого нужно добавить.")


def _start_remove_booker(chat_id, user_id):
    bookers = list_authorized_bookers()
    set_user_state(
        user_id,
        {
            "flow": "manage_bookers",
            "step": "await_remove_booker_id",
        },
    )
    if bookers:
        send_message(
            chat_id,
            "Выберите букера кнопкой или отправьте Telegram ID вручную.",
            reply_markup=_build_remove_booker_keyboard(bookers),
        )
        return

    send_message(
        chat_id,
        "Список обычных букеров пуст. Можно отправить Telegram ID вручную или нажать «⬅️ Назад».",
        reply_markup=_build_remove_booker_keyboard(bookers),
    )


def _handle_add_booker_id(chat_id, user_id, text):
    telegram_id = _parse_telegram_id(text)
    if telegram_id is None:
        print(f"event=authorized_booker_add actor_id={user_id} outcome=invalid_id raw={text!r}")
        send_message(chat_id, "Telegram ID должен быть целым числом.")
        return True

    if is_chief_booker(telegram_id):
        print(f"event=authorized_booker_add actor_id={user_id} target_id={telegram_id} outcome=chief_already_allowed")
        clear_user_state(user_id)
        send_message(
            chat_id,
            f"{telegram_id} уже указан как главный букер в CHIEF_BOOKER_IDS.",
            reply_markup=_build_management_menu(),
        )
        set_user_state(user_id, {"flow": "manage_bookers", "step": "menu"})
        return True

    created = add_authorized_booker(telegram_id, added_by=user_id)
    print(
        f"event=authorized_booker_add actor_id={user_id} target_id={telegram_id} "
        f"outcome={'created' if created else 'already_exists'}"
    )
    clear_user_state(user_id)
    if created:
        send_message(
            chat_id,
            f"Букер {telegram_id} добавлен.",
            reply_markup=_build_management_menu(),
        )
    else:
        send_message(
            chat_id,
            f"Букер {telegram_id} уже есть в списке.",
            reply_markup=_build_management_menu(),
        )
    set_user_state(user_id, {"flow": "manage_bookers", "step": "menu"})
    return True


def _handle_remove_booker_id(chat_id, user_id, text):
    telegram_id = _parse_telegram_id(text)
    if telegram_id is None:
        print(f"event=authorized_booker_remove actor_id={user_id} outcome=invalid_id raw={text!r}")
        send_message(chat_id, "Telegram ID должен быть целым числом.")
        return True

    if is_chief_booker(telegram_id):
        print(f"event=authorized_booker_remove actor_id={user_id} target_id={telegram_id} outcome=chief_blocked")
        send_message(chat_id, "Главного букера нельзя удалить через бот.")
        return True

    removed = remove_authorized_booker(telegram_id)
    print(
        f"event=authorized_booker_remove actor_id={user_id} target_id={telegram_id} "
        f"outcome={'removed' if removed else 'not_found'}"
    )
    clear_user_state(user_id)
    if removed:
        send_message(
            chat_id,
            f"Букер {telegram_id} удалён из списка доступа.",
            reply_markup=_build_management_menu(),
        )
    else:
        send_message(
            chat_id,
            f"Букер {telegram_id} не найден в списке обычных букеров.",
            reply_markup=_build_management_menu(),
        )
    set_user_state(user_id, {"flow": "manage_bookers", "step": "menu"})
    return True


def handle_booker_management_flow(chat_id, user_id, text):
    state = get_user_state(user_id)
    in_flow = state.get("flow") == "manage_bookers"
    management_texts = {
        BOOKER_MANAGEMENT_TEXT,
        ADD_BOOKER_TEXT,
        REMOVE_BOOKER_TEXT,
        LIST_BOOKERS_TEXT,
        BACK_TEXT,
    }
    if not in_flow and text not in management_texts:
        return False

    if not is_chief_booker(user_id):
        _deny_management(chat_id, user_id)
        return True

    if text == BOOKER_MANAGEMENT_TEXT:
        start_booker_management(chat_id, user_id)
        return True

    if text == BACK_TEXT:
        clear_user_state(user_id)
        send_message(chat_id, "Главное меню.", reply_markup=build_main_menu(user_id))
        return True

    if text == ADD_BOOKER_TEXT:
        _start_add_booker(chat_id, user_id)
        return True

    if text == REMOVE_BOOKER_TEXT:
        _start_remove_booker(chat_id, user_id)
        return True

    if text == LIST_BOOKERS_TEXT:
        send_message(chat_id, _format_bookers_list(), reply_markup=_build_management_menu())
        set_user_state(user_id, {"flow": "manage_bookers", "step": "menu"})
        return True

    step = state.get("step")
    if step == "await_add_booker_id":
        return _handle_add_booker_id(chat_id, user_id, text)

    if step == "await_remove_booker_id":
        return _handle_remove_booker_id(chat_id, user_id, text)

    send_message(chat_id, "Выберите действие кнопкой.", reply_markup=_build_management_menu())
    return True
