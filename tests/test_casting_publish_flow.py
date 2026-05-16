from handlers import casting_handlers
from state import set_user_state


def test_create_casting_publishes_to_selected_channel(monkeypatch, telegram_spy):
    calls, send_message = telegram_spy
    monkeypatch.setattr(casting_handlers, "send_message", send_message)
    monkeypatch.setattr(casting_handlers, "BOT_USERNAME", "test_bot")
    monkeypatch.setattr(
        casting_handlers,
        "CASTING_CHANNELS",
        [
            {"key": "channel_1", "title": "Main", "id": -100123},
            {"key": "channel_2", "title": "Alt", "id": -100124},
        ],
    )

    created = {}

    def fake_create_casting_draft(**kwargs):
        created.update(kwargs)
        return 321

    publish_calls = []

    def fake_send_channel_message(channel_id, text, reply_markup=None):
        publish_calls.append(
            {
                "channel_id": channel_id,
                "text": text,
                "reply_markup": reply_markup,
            }
        )
        return {"ok": True, "_request_status": "success", "result": {"message_id": 654}}

    monkeypatch.setattr(casting_handlers, "create_casting_draft", fake_create_casting_draft)
    monkeypatch.setattr(casting_handlers, "send_channel_message", fake_send_channel_message)
    monkeypatch.setattr(casting_handlers, "send_channel_photo", lambda **kwargs: {"ok": False, "_request_status": "failure_certain"})
    monkeypatch.setattr(casting_handlers, "attach_published_message", lambda casting_id, message_id: casting_id == 321 and message_id == 654)
    monkeypatch.setattr(casting_handlers, "mark_casting_deleted_by_id", lambda casting_id: False)

    user_id = 7007
    set_user_state(
        user_id,
        {
            "flow": "create_casting",
            "step": "channel",
            "title": "Summer Casting",
            "description": "Need fresh faces",
            "photo_file_id": None,
        },
    )

    handled = casting_handlers.handle_casting_flow(
        chat_id=7007,
        user_id=user_id,
        message={"text": "2. Alt", "from": {"username": "admin", "first_name": "A", "last_name": "D"}},
    )

    assert handled is True
    assert created["channel_id"] == -100124
    assert publish_calls[0]["channel_id"] == -100124
    assert publish_calls[0]["reply_markup"]["inline_keyboard"][0][0]["text"] == "Откликнуться"
    assert "respond_casting_321" in publish_calls[0]["reply_markup"]["inline_keyboard"][0][0]["url"]
    assert calls[-1]["text"] == "Кастинг опубликован."

