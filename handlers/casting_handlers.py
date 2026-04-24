import re

from config import BOT_USERNAME, CASTING_CHANNELS
from handlers.response_handlers import build_respond_payload
from services.casting_service import (
    attach_published_message,
    close_casting,
    create_casting_draft,
    delete_casting,
    get_all_castings,
    get_casting_by_id_for_admin,
    get_castings_by_admin,
    mark_casting_deleted_by_id,
    get_responsible_bookers_for_brand_title,
    get_responses_for_casting,
)
from services.telegram_api import (
    send_channel_message,
    send_channel_photo,
    send_message,
)
from state import clear_user_state, get_user_state, set_user_state


def build_main_menu():
    return {
        "keyboard": [
            [{"text": "Создать кастинг"}],
            [{"text": "Посмотреть отклики"}],
            [{"text": "Закрыть кастинг"}],
            [{"text": "Удалить кастинг"}],
            [{"text": "Добавить модель"}],
            [{"text": "Ответственный букер"}],
        ],
        "resize_keyboard": True,
    }


def build_castings_list_keyboard(castings, back_button_text="Назад", back_button_first=False, show_closed_marker=False):
    keyboard = []

    if back_button_first:
        keyboard.append([{"text": back_button_text}])

    for casting in castings:
        title = casting["title"]
        short_title = title[:28] + "..." if len(title) > 28 else title
        closed_suffix = " [Закрыт]" if show_closed_marker and casting.get("is_closed") else ""
        keyboard.append([{"text": f"#{casting['id']} {short_title}{closed_suffix}"}])

    if not back_button_first:
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
            main_line = f"{index}. {response['full_name']} — {response['telegram_username']}"
            comment = (response.get("comment") or "").strip()
            if comment:
                lines.append(f"{main_line}\nКомментарий: {comment}")
            else:
                lines.append(main_line)

    return "\n\n".join(lines)


def _channel_choice_items():
    return [
        {
            "key": channel["key"],
            "title": channel["title"],
            "id": channel["id"],
            "button_text": f"{index}. {channel['title']}",
        }
        for index, channel in enumerate(CASTING_CHANNELS, start=1)
    ]


def _build_channel_selection_keyboard():
    keyboard = [[{"text": channel["button_text"]}] for channel in _channel_choice_items()]
    return {
        "keyboard": keyboard,
        "resize_keyboard": True,
    }


def _get_channel_by_button_text(text):
    normalized_text = (text or "").strip()
    for channel in _channel_choice_items():
        if normalized_text == channel["button_text"]:
            return channel
    return None


def _build_add_image_keyboard():
    return {
        "keyboard": [
            [{"text": "Добавить изображение"}],
            [{"text": "Пропустить"}],
        ],
        "resize_keyboard": True,
    }


def _build_responses_inline_keyboard(casting_id):
    payload = build_respond_payload(casting_id=casting_id)
    response_url = f"https://t.me/{BOT_USERNAME}?start={payload}"
    return {
        "inline_keyboard": [
            [
                {
                    "text": "Откликнуться",
                    "url": response_url,
                }
            ]
        ]
    }


def _build_admin_identity(user):
    first_name = (user.get("first_name") or "").strip()
    last_name = (user.get("last_name") or "").strip()
    full_name = f"{first_name} {last_name}".strip()
    username = (user.get("username") or "").strip()
    username_with_at = f"@{username}" if username else None

    # Keep backward compatibility with old field:
    # save username there first so old readers still show readable value.
    legacy_name = username_with_at or full_name or None

    return {
        "legacy_name": legacy_name,
        "username": username_with_at,
        "full_name": full_name or None,
    }


def _format_responsible_bookers_for_brand(casting):
    title = casting["title"]
    bookers = get_responsible_bookers_for_brand_title(title)

    def _human_booker_name(item):
        username = (item.get("responsible_admin_username") or "").strip()
        if username:
            return username

        full_name = (item.get("responsible_admin_full_name") or "").strip()
        if full_name:
            return full_name

        legacy_name = (item.get("responsible_admin_name") or "").strip()
        if legacy_name:
            return legacy_name

        return "Ответственный не указан"

    lines = []
    if not bookers:
        lines.append(f"{title} — Ответственный не указан")
        return "\n".join(lines)

    for item in bookers:
        lines.append(f"{title} — {_human_booker_name(item)}")
    return "\n".join(lines)


def start_create_casting(chat_id, user_id):
    set_user_state(
        user_id,
        {
            "flow": "create_casting",
            "step": "title",
        },
    )
    send_message(chat_id, "Введите название кастинга.")


def handle_casting_flow(chat_id, user_id, message):
    state = get_user_state(user_id)

    if state.get("flow") != "create_casting":
        return False

    step = state.get("step")
    text = (message.get("text") or "").strip()
    photos = message.get("photo") or []

    if step == "title":
        if not text:
            send_message(chat_id, "Введите название кастинга текстом.")
            return True
        set_user_state(
            user_id,
            {
                "flow": "create_casting",
                "step": "description",
                "title": text,
            },
        )
        send_message(chat_id, "Введите текст кастинга.")
        return True

    if step == "description":
        if not text:
            send_message(chat_id, "Введите текст кастинга текстом.")
            return True
        set_user_state(
            user_id,
            {
                "flow": "create_casting",
                "step": "add_image_choice",
                "title": state["title"],
                "description": text,
            },
        )
        send_message(chat_id, "Добавить изображение к кастингу?", reply_markup=_build_add_image_keyboard())
        return True

    if step == "add_image_choice":
        if text == "Добавить изображение":
            set_user_state(
                user_id,
                {
                    "flow": "create_casting",
                    "step": "image",
                    "title": state["title"],
                    "description": state["description"],
                },
            )
            send_message(chat_id, "Отправьте изображение одним сообщением.")
            return True

        if text == "Пропустить":
            set_user_state(
                user_id,
                {
                    "flow": "create_casting",
                    "step": "channel",
                    "title": state["title"],
                    "description": state["description"],
                    "photo_file_id": None,
                },
            )
            send_message(
                chat_id,
                "Выберите канал для публикации кастинга.",
                reply_markup=_build_channel_selection_keyboard(),
            )
            return True

        send_message(chat_id, "Выберите вариант кнопкой.", reply_markup=_build_add_image_keyboard())
        return True

    if step == "image":
        if not photos:
            send_message(chat_id, "Отправьте изображение или нажмите «Назад» для отмены.")
            return True

        largest_photo = photos[-1]
        file_id = largest_photo.get("file_id")
        if not file_id:
            send_message(chat_id, "Не удалось получить изображение. Отправьте другое фото.")
            return True

        set_user_state(
            user_id,
            {
                "flow": "create_casting",
                "step": "channel",
                "title": state["title"],
                "description": state["description"],
                "photo_file_id": file_id,
            },
        )
        send_message(
            chat_id,
            "Выберите канал для публикации кастинга.",
            reply_markup=_build_channel_selection_keyboard(),
        )
        return True

    if step == "channel":
        title = state["title"]
        description = state["description"]
        photo_file_id = state.get("photo_file_id")
        selected_channel = _get_channel_by_button_text(text)
        if not selected_channel:
            send_message(
                chat_id,
                "Выберите канал кнопкой из списка.",
                reply_markup=_build_channel_selection_keyboard(),
            )
            return True

        channel_id = selected_channel["id"]
        post_text = f"📢 {title}\n\n{description}"
        if not BOT_USERNAME:
            clear_user_state(user_id)
            send_message(chat_id, "Не удалось опубликовать: не настроен BOT_USERNAME для кнопки отклика.")
            return True

        admin_identity = _build_admin_identity(message["from"])
        casting_id = create_casting_draft(
            title=title,
            description=description,
            admin_id=user_id,
            channel_id=channel_id,
            responsible_admin_name=admin_identity["legacy_name"],
            responsible_admin_username=admin_identity["username"],
            responsible_admin_full_name=admin_identity["full_name"],
            photo_file_id=photo_file_id,
        )
        reply_markup = _build_responses_inline_keyboard(casting_id)
        deep_link = reply_markup["inline_keyboard"][0][0]["url"]

        if photo_file_id:
            result = send_channel_photo(
                channel_id=channel_id,
                photo_file_id=photo_file_id,
                caption=post_text,
                reply_markup=reply_markup,
            )
        else:
            result = send_channel_message(
                channel_id,
                post_text,
                reply_markup=reply_markup,
            )

        publish_status = result.get("_request_status")

        if publish_status == "failure_certain":
            mark_casting_deleted_by_id(casting_id)
            print(
                f"event=publication_failure_certain casting_id={casting_id} admin_id={user_id} "
                f"channel_id={channel_id} reason=telegram_api_ok_false result={result}"
            )
            clear_user_state(user_id)
            send_message(chat_id, "Не удалось опубликовать кастинг. Проверь токен, ID канала и права бота.")
            return True

        if publish_status == "failure_unknown":
            print(
                f"event=publication_status_unknown casting_id={casting_id} admin_id={user_id} "
                f"channel_id={channel_id} reason=publish_status_unknown result={result}"
            )
            clear_user_state(user_id)
            send_message(
                chat_id,
                "Статус публикации неизвестен. Проверьте канал перед повторной попыткой, чтобы избежать дубля.",
            )
            return True

        if not result.get("ok"):
            mark_casting_deleted_by_id(casting_id)
            print(
                f"event=publication_failure_certain casting_id={casting_id} admin_id={user_id} "
                f"channel_id={channel_id} reason=unexpected_not_ok result={result}"
            )
            clear_user_state(user_id)
            send_message(chat_id, "Не удалось опубликовать кастинг. Проверь токен, ID канала и права бота.")
            return True

        message_id = result["result"]["message_id"]
        print(
            f"event=publication_success casting_id={casting_id} admin_id={user_id} "
            f"channel_id={channel_id} message_id={message_id} deep_link={deep_link}"
        )

        attach_error = None
        try:
            linked = attach_published_message(casting_id, message_id)
        except Exception as error:
            linked = False
            attach_error = str(error)

        if not linked:
            print(
                f"event=attach_published_message_failure level=CRITICAL casting_id={casting_id} "
                f"admin_id={user_id} channel_id={channel_id} message_id={message_id} "
                f"reason={attach_error or 'row_not_updated'}"
            )
            clear_user_state(user_id)
            send_message(
                chat_id,
                "Кастинг опубликован, но возникла ошибка сохранения message_id в базе. Проверьте канал и обратитесь к разработчику.",
                reply_markup=build_main_menu(),
            )
            return True

        print(
            f"event=attach_published_message_success casting_id={casting_id} admin_id={user_id} "
            f"channel_id={channel_id} message_id={message_id}"
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
    castings = get_castings_by_admin(admin_id)

    if not castings:
        send_message(chat_id, "Нет кастингов для просмотра откликов.", reply_markup=build_main_menu())
        return

    send_message(
        chat_id,
        "Выберите кастинг для просмотра откликов.",
        reply_markup=build_castings_list_keyboard(castings, show_closed_marker=True),
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


def start_view_responsible_booker(chat_id, admin_id):
    castings = get_all_castings()

    if not castings:
        send_message(chat_id, "Нет кастингов для просмотра.", reply_markup=build_main_menu())
        return

    send_message(
        chat_id,
        "Выберите кастинг, чтобы увидеть ответственного букера.",
        reply_markup=build_castings_list_keyboard(castings, back_button_first=True),
    )
    set_user_state(
        admin_id,
        {
            "flow": "select_casting_action",
            "action": "view_responsible_booker",
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

    if action == "view_responsible_booker":
        casting = next((item for item in get_all_castings() if item["id"] == casting_id), None)
    else:
        casting = get_casting_by_id_for_admin(casting_id, admin_id)

    if not casting:
        send_message(chat_id, "Кастинг не найден.")
        return True

    if action == "view_responsible_booker":
        send_message(chat_id, _format_responsible_bookers_for_brand(casting))
        return True

    if action == "view_responses":
        responses = get_responses_for_casting(casting_id, admin_id)
        print(
            f"event=view_responses casting_id={casting_id} admin_id={admin_id} "
            f"response_count={len(responses)} is_closed={casting['is_closed']}"
        )
        send_message(chat_id, _format_responses_text(casting, responses))
        return True

    if action == "close_casting":
        print(f"event=close_casting_attempt casting_id={casting_id} admin_id={admin_id}")
        if casting["is_closed"]:
            print(f"event=close_casting_failure casting_id={casting_id} admin_id={admin_id} reason=already_closed")
            send_message(chat_id, "Кастинг уже закрыт.")
            return True

        success = close_casting(casting_id, admin_id)
        if success:
            print(f"event=close_casting_success casting_id={casting_id} admin_id={admin_id}")
            clear_user_state(admin_id)
            send_message(chat_id, f"Кастинг «{casting['title']}» закрыт.", reply_markup=build_main_menu())
        else:
            print(f"event=close_casting_failure casting_id={casting_id} admin_id={admin_id} reason=db_update_failed")
            send_message(chat_id, "Не удалось закрыть кастинг.")
        return True

    if action == "delete_casting":
        print(f"event=delete_casting_attempt casting_id={casting_id} admin_id={admin_id}")
        success = delete_casting(casting_id, admin_id)
        if success:
            print(f"event=delete_casting_success casting_id={casting_id} admin_id={admin_id}")
            clear_user_state(admin_id)
            send_message(chat_id, f"Кастинг «{casting['title']}» удалён из списка.", reply_markup=build_main_menu())
        else:
            print(f"event=delete_casting_failure casting_id={casting_id} admin_id={admin_id} reason=db_update_failed")
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
        print(
            f"event=view_responses casting_id={casting_id} admin_id={admin_id} "
            f"response_count={len(responses)} is_closed={casting['is_closed']} source=legacy_manage"
        )
        send_message(chat_id, _format_responses_text(casting, responses))
        return True

    if text == "Закрыть кастинг":
        print(f"event=close_casting_attempt casting_id={casting_id} admin_id={admin_id} source=legacy_manage")
        if casting["is_closed"]:
            print(
                f"event=close_casting_failure casting_id={casting_id} admin_id={admin_id} "
                "reason=already_closed source=legacy_manage"
            )
            send_message(chat_id, "Кастинг уже закрыт.")
            return True

        success = close_casting(casting_id, admin_id)

        if success:
            print(f"event=close_casting_success casting_id={casting_id} admin_id={admin_id} source=legacy_manage")
            send_message(chat_id, "Кастинг закрыт.", reply_markup=build_main_menu())
            clear_user_state(admin_id)
        else:
            print(
                f"event=close_casting_failure casting_id={casting_id} admin_id={admin_id} "
                "reason=db_update_failed source=legacy_manage"
            )
            send_message(chat_id, "Не удалось закрыть кастинг.")
        return True

    if text == "Удалить кастинг":
        print(f"event=delete_casting_attempt casting_id={casting_id} admin_id={admin_id} source=legacy_manage")
        success = delete_casting(casting_id, admin_id)
        if success:
            print(f"event=delete_casting_success casting_id={casting_id} admin_id={admin_id} source=legacy_manage")
            clear_user_state(admin_id)
            send_message(chat_id, "Кастинг удалён из списка.", reply_markup=build_main_menu())
        else:
            print(
                f"event=delete_casting_failure casting_id={casting_id} admin_id={admin_id} "
                "reason=db_update_failed source=legacy_manage"
            )
            send_message(chat_id, "Не удалось удалить кастинг.")
        return True

    send_message(chat_id, "Используйте кнопки управления кастингом.")
    return True