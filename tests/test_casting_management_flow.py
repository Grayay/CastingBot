from handlers import casting_handlers, response_handlers
from state import set_user_state


def test_close_casting_blocks_new_responses_and_keeps_existing_visible(monkeypatch, telegram_spy):
    calls, send_message = telegram_spy
    monkeypatch.setattr(casting_handlers, "send_message", send_message)
    monkeypatch.setattr(response_handlers, "send_message", send_message)

    db = {
        "casting": {
            "id": 42,
            "title": "Nike campaign",
            "admin_id": 7001,
            "is_closed": False,
            "is_deleted": False,
            "channel_id": -1001,
        },
        "responses": [
            {"full_name": "Alice Doe", "telegram_username": "@alice", "comment": "Ready"},
        ],
    }

    def get_for_admin(casting_id, admin_id):
        casting = db["casting"]
        if casting["id"] == casting_id and casting["admin_id"] == admin_id and not casting["is_deleted"]:
            return casting
        return None

    monkeypatch.setattr(casting_handlers, "get_casting_by_id_for_admin", get_for_admin)
    monkeypatch.setattr(
        casting_handlers,
        "close_casting",
        lambda casting_id, admin_id: db["casting"].update({"is_closed": True}) or True,
    )
    monkeypatch.setattr(casting_handlers, "get_responses_for_casting", lambda *_: list(db["responses"]))
    monkeypatch.setattr(response_handlers, "get_casting_by_id", lambda casting_id: db["casting"] if casting_id == 42 else None)

    set_user_state(7001, {"flow": "select_casting_action", "action": "close_casting"})
    handled = casting_handlers.handle_select_casting_action(7001, 7001, "#42 Nike campaign")
    assert handled is True
    assert db["casting"]["is_closed"] is True

    response_handlers.handle_start_response_payload(
        chat_id=9001,
        user_id=222,
        username="@model",
        payload="respond_casting_42",
    )
    assert calls[-1]["text"] == "Кастинг уже закрыт."

    # Existing responses are still available for the booker/admin.
    set_user_state(7001, {"flow": "select_casting_action", "action": "view_responses"})
    casting_handlers.handle_select_casting_action(7001, 7001, "#42 Nike campaign")
    assert "Количество откликов: 1" in calls[-1]["text"]
    assert "Alice Doe" in calls[-1]["text"]


def test_delete_casting_hides_and_blocks_new_responses(monkeypatch, telegram_spy):
    calls, send_message = telegram_spy
    monkeypatch.setattr(casting_handlers, "send_message", send_message)
    monkeypatch.setattr(response_handlers, "send_message", send_message)

    db = {
        "casting": {
            "id": 77,
            "title": "Deleted campaign",
            "admin_id": 8001,
            "is_closed": False,
            "is_deleted": False,
            "channel_id": -1002,
        }
    }

    def get_for_admin(casting_id, admin_id):
        casting = db["casting"]
        if casting["id"] == casting_id and casting["admin_id"] == admin_id and not casting["is_deleted"]:
            return casting
        return None

    monkeypatch.setattr(casting_handlers, "get_casting_by_id_for_admin", get_for_admin)
    monkeypatch.setattr(
        casting_handlers,
        "delete_casting",
        lambda casting_id, admin_id: db["casting"].update({"is_deleted": True}) or True,
    )
    monkeypatch.setattr(
        response_handlers,
        "get_casting_by_id",
        lambda casting_id: db["casting"] if (casting_id == 77 and not db["casting"]["is_deleted"]) else None,
    )

    set_user_state(8001, {"flow": "select_casting_action", "action": "delete_casting"})
    handled = casting_handlers.handle_select_casting_action(8001, 8001, "#77 Deleted campaign")
    assert handled is True
    assert db["casting"]["is_deleted"] is True

    response_handlers.handle_start_response_payload(
        chat_id=9011,
        user_id=333,
        username="@model",
        payload="respond_casting_77",
    )
    assert calls[-1]["text"] == "Кастинг недоступен."

