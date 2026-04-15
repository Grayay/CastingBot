from services.model_service import create_model
from services.telegram_api import send_message
from state import clear_user_state, get_user_state, set_user_state


def start_add_model(chat_id, user_id):
    set_user_state(
        user_id,
        {
            "flow": "add_model",
            "step": "full_name",
        },
    )
    send_message(chat_id, "Введите ФИО модели.")


def handle_model_flow(chat_id, user_id, text):
    state = get_user_state(user_id)

    if state.get("flow") != "add_model":
        return False

    step = state.get("step")

    if step == "full_name":
        set_user_state(
            user_id,
            {
                "flow": "add_model",
                "step": "username",
                "full_name": text.strip(),
            },
        )
        send_message(chat_id, "Введите username модели с @.")
        return True

    if step == "username":
        success, error_text = create_model(
            full_name=state["full_name"],
            telegram_username=text.strip(),
            added_by_admin_id=user_id,
        )

        clear_user_state(user_id)

        if success:
            send_message(chat_id, "Модель успешно добавлена.")
        else:
            send_message(chat_id, error_text)

        return True

    return False