from handlers import response_handlers
from state import get_user_state, set_user_state


def _open_casting(casting_id=10, channel_id=-100):
    return {
        "id": casting_id,
        "is_closed": False,
        "is_deleted": False,
        "channel_id": channel_id,
        "admin_id": 1,
    }


def _telegram_member(status="member", is_member=None):
    result = {"status": status}
    if is_member is not None:
        result["is_member"] = is_member
    return {"ok": True, "result": result}


class FakeBot:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error

    def get_chat_member(self, channel_id, user_id):
        if self.error:
            raise self.error
        return self.result


def test_is_user_channel_member_matches_telegram_status_rules():
    allowed_results = [
        _telegram_member("member"),
        _telegram_member("administrator"),
        _telegram_member("creator"),
        _telegram_member("restricted", is_member=True),
    ]
    denied_results = [
        _telegram_member("left"),
        _telegram_member("kicked"),
        _telegram_member("restricted", is_member=False),
        {"ok": False, "description": "Bad Request: user not found"},
        {"ok": True, "result": {}},
    ]

    for result in allowed_results:
        assert response_handlers.is_user_channel_member(FakeBot(result), -100, 1001) is True

    for result in denied_results:
        assert response_handlers.is_user_channel_member(FakeBot(result), -100, 1001) is False

    assert response_handlers.is_user_channel_member(FakeBot(error=RuntimeError("boom")), -100, 1001) is False


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


def test_start_payload_denies_user_outside_casting_channel(monkeypatch, telegram_spy):
    calls, send_message = telegram_spy
    monkeypatch.setattr(response_handlers, "send_message", send_message)
    monkeypatch.setattr(response_handlers, "get_casting_by_id", lambda casting_id: _open_casting(casting_id, -10055))
    monkeypatch.setattr(response_handlers, "get_chat_member", lambda channel_id, user_id: _telegram_member("left"))

    def fail_model_lookup(user_id, username):
        raise AssertionError("model lookup should not run when channel membership is denied")

    monkeypatch.setattr(response_handlers, "find_model_for_user", fail_model_lookup)

    handled = response_handlers.handle_start_response_payload(
        chat_id=501,
        user_id=1001,
        username="@model",
        payload="respond_casting_10",
    )

    assert handled is True
    assert calls[-1]["chat_id"] == 501
    assert calls[-1]["text"] == response_handlers.RESPONSE_CHANNEL_MEMBERS_ONLY_MESSAGE


def test_response_comment_flow_skip_saves_once(monkeypatch, telegram_spy):
    calls, send_message = telegram_spy
    monkeypatch.setattr(response_handlers, "send_message", send_message)
    monkeypatch.setattr(response_handlers, "get_casting_by_id", lambda casting_id: _open_casting(casting_id, -10055))
    monkeypatch.setattr(response_handlers, "get_chat_member", lambda channel_id, user_id: _telegram_member("member"))

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


def test_response_comment_flow_denies_if_user_left_before_save(monkeypatch, telegram_spy):
    calls, send_message = telegram_spy
    monkeypatch.setattr(response_handlers, "send_message", send_message)
    monkeypatch.setattr(response_handlers, "get_casting_by_id", lambda casting_id: _open_casting(casting_id, -10055))
    monkeypatch.setattr(response_handlers, "get_chat_member", lambda channel_id, user_id: _telegram_member("left"))
    monkeypatch.setattr(
        response_handlers,
        "response_exists",
        lambda casting_id, model_id: (_ for _ in ()).throw(AssertionError("response_exists should not run")),
    )
    monkeypatch.setattr(
        response_handlers,
        "save_response",
        lambda casting_id, model_id, comment=None: (_ for _ in ()).throw(AssertionError("save_response should not run")),
    )

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
        message={"text": "Available today"},
    )

    assert handled is True
    assert calls[-1]["text"] == response_handlers.RESPONSE_CHANNEL_MEMBERS_ONLY_MESSAGE
    assert calls[-1]["reply_markup"] == {"remove_keyboard": True}
    assert get_user_state(1001) == {}


def test_first_time_registration_denies_if_user_left_before_save(monkeypatch, telegram_spy):
    calls, send_message = telegram_spy
    monkeypatch.setattr(response_handlers, "send_message", send_message)
    monkeypatch.setattr(response_handlers, "get_casting_by_id", lambda casting_id: _open_casting(casting_id, -10055))
    monkeypatch.setattr(response_handlers, "get_chat_member", lambda channel_id, user_id: _telegram_member("left"))
    monkeypatch.setattr(
        response_handlers,
        "create_or_get_self_registered_model",
        lambda full_name, telegram_id, username: ({"id": 22, "telegram_id": telegram_id}, True),
    )
    monkeypatch.setattr(
        response_handlers,
        "response_exists",
        lambda casting_id, model_id: (_ for _ in ()).throw(AssertionError("response_exists should not run")),
    )
    monkeypatch.setattr(
        response_handlers,
        "save_response",
        lambda casting_id, model_id, comment=None: (_ for _ in ()).throw(AssertionError("save_response should not run")),
    )

    set_user_state(
        1001,
        {
            "flow": "first_time_registration",
            "step": "await_full_name",
            "casting_id": 10,
            "username": "@model",
        },
    )

    handled = response_handlers.handle_first_time_registration_flow(
        chat_id=1001,
        user_id=1001,
        message={"text": "Test Model"},
    )

    assert handled is True
    assert calls[-1]["text"] == response_handlers.RESPONSE_CHANNEL_MEMBERS_ONLY_MESSAGE
    assert get_user_state(1001) == {}

