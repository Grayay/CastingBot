from handlers import response_handlers
from state import set_user_state


def test_start_payload_closed_casting_is_blocked(monkeypatch, telegram_spy):
    calls, send_message = telegram_spy
    monkeypatch.setattr(response_handlers, "send_message", send_message)
    monkeypatch.setattr(
        response_handlers,
        "get_casting_by_id",
        lambda casting_id: {"id": casting_id, "is_closed": True, "is_deleted": False, "channel_id": -100, "admin_id": 1},
    )

    handled = response_handlers.handle_start_response_payload(
        chat_id=501,
        user_id=1001,
        username="@model",
        payload="respond_casting_10",
    )

    assert handled is True
    assert calls[-1]["chat_id"] == 501
    assert calls[-1]["text"] == "Кастинг уже закрыт."


def test_response_comment_flow_skip_saves_once(monkeypatch, telegram_spy):
    calls, send_message = telegram_spy
    monkeypatch.setattr(response_handlers, "send_message", send_message)

    saved = []
    responded_pairs = set()

    def fake_exists(casting_id, model_id):
        return (casting_id, model_id) in responded_pairs

    def fake_save(casting_id, model_id, comment=None):
        saved.append((casting_id, model_id, comment))
        responded_pairs.add((casting_id, model_id))

    monkeypatch.setattr(response_handlers, "response_exists", fake_exists)
    monkeypatch.setattr(response_handlers, "save_response", fake_save)

    set_user_state(
        1001,
        {
            "flow": "response_comment",
            "step": "await_comment",
            "casting_id": 10,
            "model_id": 22,
        },
    )

    handled = response_handlers.handle_response_comment_flow(
        chat_id=1001,
        user_id=1001,
        message={"text": response_handlers.SKIP_COMMENT_TEXT},
    )
    assert handled is True
    assert saved == [(10, 22, None)]
    assert calls[-1]["text"] == "Отклик отправлен."

    # Re-entering the same flow for the same pair should not create duplicates.
    set_user_state(
        1001,
        {
            "flow": "response_comment",
            "step": "await_comment",
            "casting_id": 10,
            "model_id": 22,
        },
    )
    handled_second = response_handlers.handle_response_comment_flow(
        chat_id=1001,
        user_id=1001,
        message={"text": "Любой комментарий"},
    )
    assert handled_second is True
    assert saved == [(10, 22, None)]
    assert calls[-1]["text"] == "Вы уже откликались на этот кастинг."

