from handlers import booker_handlers
from state import get_user_state, set_user_state


def test_non_chief_cannot_manage_bookers(monkeypatch, telegram_spy):
    calls, send_message = telegram_spy
    monkeypatch.setattr(booker_handlers, "send_message", send_message)
    monkeypatch.setattr(booker_handlers, "is_chief_booker", lambda user_id: False)
    monkeypatch.setattr(
        booker_handlers,
        "add_authorized_booker",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("must not add")),
    )

    handled = booker_handlers.handle_booker_management_flow(
        chat_id=5001,
        user_id=7001,
        text=booker_handlers.ADD_BOOKER_TEXT,
    )

    assert handled is True
    assert calls[-1]["text"] == "Недостаточно прав для управления букерами."


def test_chief_can_add_regular_booker(monkeypatch, telegram_spy):
    calls, send_message = telegram_spy
    added = []

    monkeypatch.setattr(booker_handlers, "send_message", send_message)
    monkeypatch.setattr(booker_handlers, "is_chief_booker", lambda user_id: user_id == 9001)
    monkeypatch.setattr(
        booker_handlers,
        "add_authorized_booker",
        lambda telegram_id, added_by=None: added.append((telegram_id, added_by)) or True,
    )

    assert booker_handlers.handle_booker_management_flow(9001, 9001, booker_handlers.ADD_BOOKER_TEXT) is True
    assert get_user_state(9001)["step"] == "await_add_booker_id"

    assert booker_handlers.handle_booker_management_flow(9001, 9001, "7001") is True

    assert added == [(7001, 9001)]
    assert calls[-1]["text"] == "Букер 7001 добавлен."


def test_chief_can_remove_regular_booker(monkeypatch, telegram_spy):
    calls, send_message = telegram_spy
    removed = []

    monkeypatch.setattr(booker_handlers, "send_message", send_message)
    monkeypatch.setattr(booker_handlers, "is_chief_booker", lambda user_id: user_id == 9001)
    monkeypatch.setattr(
        booker_handlers,
        "list_authorized_bookers",
        lambda: [{"telegram_id": 7001, "username": None, "full_name": None}],
    )
    monkeypatch.setattr(
        booker_handlers,
        "remove_authorized_booker",
        lambda telegram_id: removed.append(telegram_id) or True,
    )

    assert booker_handlers.handle_booker_management_flow(9001, 9001, booker_handlers.REMOVE_BOOKER_TEXT) is True
    assert get_user_state(9001)["step"] == "await_remove_booker_id"

    assert booker_handlers.handle_booker_management_flow(9001, 9001, "7001") is True

    assert removed == [7001]
    assert calls[-1]["text"] == "Букер 7001 удалён из списка доступа."


def test_chief_cannot_remove_chief_booker(monkeypatch, telegram_spy):
    calls, send_message = telegram_spy
    monkeypatch.setattr(booker_handlers, "send_message", send_message)
    monkeypatch.setattr(booker_handlers, "is_chief_booker", lambda user_id: user_id == 9001)
    monkeypatch.setattr(
        booker_handlers,
        "remove_authorized_booker",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("must not remove chief")),
    )
    set_user_state(9001, {"flow": "manage_bookers", "step": "await_remove_booker_id"})

    handled = booker_handlers.handle_booker_management_flow(9001, 9001, "9001")

    assert handled is True
    assert calls[-1]["text"] == "Главного букера нельзя удалить через бот."
