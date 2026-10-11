from unittest.mock import Mock

import pytest

from handlers import admin_handlers, casting_handlers
from services import access_control, casting_service
from state import get_user_state, set_user_state


@pytest.fixture
def booker_flow(monkeypatch, telegram_spy):
    calls, send_message = telegram_spy
    monkeypatch.setattr(casting_handlers, "send_message", send_message)
    monkeypatch.setattr(admin_handlers, "send_message", send_message)
    monkeypatch.setattr(access_control, "CHIEF_BOOKER_IDS", [9001, 9002])
    monkeypatch.setattr(access_control, "_is_regular_authorized_booker", lambda user_id, connection=None: user_id == 7001)
    bookers = [
        {"telegram_id": 7001, "username": "@same", "full_name": "Букер"},
        {"telegram_id": 7002, "username": "@same", "full_name": "Букер"},
        {"telegram_id": 7003, "username": None, "full_name": None},
    ]
    monkeypatch.setattr(casting_handlers, "get_responsible_bookers", lambda: bookers)
    monkeypatch.setattr(casting_handlers, "get_all_castings", Mock(return_value=[]))
    monkeypatch.setattr(casting_handlers, "get_castings_by_admin", Mock(return_value=[]))
    return calls, bookers


def _message(text, user_id=9001):
    admin_handlers.handle_message({"message": {"chat": {"id": user_id}, "from": {"id": user_id}, "text": text}})


def _button(calls, telegram_id):
    return next(
        button["text"]
        for row in calls[-1]["reply_markup"]["keyboard"]
        for button in row
        if button["text"].startswith(str(telegram_id))
    )


@pytest.mark.parametrize("chief_id", [9001, 9002])
def test_chief_selects_booker_by_id_and_can_select_another(booker_flow, chief_id):
    calls, _ = booker_flow
    _message("Ответственный букер", chief_id)
    assert calls[-1]["text"].startswith("Выберите букера")
    first = _button(calls, 7001)
    second = _button(calls, 7002)
    assert first != second
    casting_handlers.get_all_castings.assert_not_called()
    casting_handlers.get_castings_by_admin.return_value = [
        {"id": 11, "title": "Общий бренд", "is_closed": False},
        {"id": 12, "title": "Общий бренд", "is_closed": True},
    ]

    _message(second, chief_id)

    casting_handlers.get_castings_by_admin.assert_called_once_with(7002)
    assert "#11 Общий бренд" in calls[-1]["text"]
    assert "#12 Общий бренд [Закрыт]" in calls[-1]["text"]
    casting_handlers.get_castings_by_admin.return_value = []
    _message(first, chief_id)
    casting_handlers.get_castings_by_admin.assert_called_with(7001)
    assert "нет кастингов" in calls[-1]["text"]
    _message("Назад", chief_id)
    assert get_user_state(chief_id) == {}
    assert calls[-1]["text"] == "Главное меню."


def test_large_result_is_complete_and_each_message_fits_telegram(booker_flow):
    calls, _ = booker_flow
    _message("Ответственный букер")
    selected = _button(calls, 7001)
    castings = [{"id": index, "title": f"Кастинг {index} 🎭", "is_closed": False} for index in range(1, 151)]
    castings.append({"id": 151, "title": "🎭" * 5000, "is_closed": True})
    casting_handlers.get_castings_by_admin.return_value = castings
    calls.clear()

    _message(selected)

    text = "".join(call["text"] for call in calls)
    assert all(f"#{item['id']} {item['title']}" in text for item in castings)
    assert text.count("🎭") == 5150
    assert all(0 < len(call["text"].encode("utf-16-le")) // 2 <= 4096 for call in calls)


def test_invalid_booker_does_not_query_castings(booker_flow):
    calls, _ = booker_flow
    _message("Ответственный букер")
    _message("9999 @forged")
    assert "Выберите букера" in calls[-1]["text"]
    casting_handlers.get_castings_by_admin.assert_not_called()


@pytest.mark.parametrize("user_id", [7001, 1234])
def test_non_chief_cannot_reuse_chief_selection(booker_flow, user_id):
    calls, _ = booker_flow
    _message("Ответственный букер")
    selected = _button(calls, 7001)
    set_user_state(user_id, get_user_state(9001))

    casting_handlers.handle_select_casting_action(user_id, user_id, selected)

    assert "Недостаточно прав" in calls[-1]["text"]
    assert get_user_state(user_id) == {}
    casting_handlers.get_castings_by_admin.assert_not_called()


def test_unauthorized_message_cannot_open_feature(booker_flow):
    _message("Ответственный букер", 1234)
    assert get_user_state(1234) == {}
    casting_handlers.get_all_castings.assert_not_called()
    casting_handlers.get_castings_by_admin.assert_not_called()


def test_regular_booker_keeps_existing_lookup(booker_flow, monkeypatch):
    calls, _ = booker_flow
    casting_handlers.get_all_castings.return_value = [{"id": 42, "title": "Бренд", "is_closed": False}]
    monkeypatch.setattr(casting_handlers, "get_responsible_bookers_for_brand_title", lambda title: [{"responsible_admin_username": "@owner"}])

    _message("Ответственный букер", 7001)
    assert calls[-1]["text"] == "Выберите кастинг, чтобы увидеть ответственного букера."
    _message("#42 Бренд", 7001)
    assert calls[-1]["text"] == "Бренд — @owner"


def test_responses_keep_intentional_90_casting_limit(booker_flow):
    calls, _ = booker_flow
    casting_handlers.get_castings_by_admin.return_value = [
        {"id": index, "title": "Кастинг", "is_closed": False} for index in range(100)
    ]
    casting_handlers.start_view_responses(9001, 9001)
    buttons = [button for row in calls[-1]["reply_markup"]["keyboard"] for button in row]
    assert len([button for button in buttons if button["text"].startswith("#")]) == 90


def test_booker_list_paging_keeps_every_booker_accessible(booker_flow):
    calls, bookers = booker_flow
    bookers[:] = [{"telegram_id": index, "full_name": "Букер"} for index in range(1000, 1181)]
    _message("Ответственный букер")
    seen = set()
    for _ in range(3):
        buttons = [button["text"] for row in calls[-1]["reply_markup"]["keyboard"] for button in row]
        seen.update(int(button.split()[0]) for button in buttons if button[0].isdigit())
        assert len(buttons) <= 93
        if "Следующие букеры" in buttons:
            _message("Следующие букеры")
    assert seen == set(range(1000, 1181))
    selected = _button(calls, 1180)
    _message(selected)
    casting_handlers.get_castings_by_admin.assert_called_once_with(1180)
    _message("Предыдущие букеры")
    assert get_user_state(9001)["page"] == 1
    _message("Назад")
    assert get_user_state(9001) == {}


def test_expired_selection_cannot_query_castings(booker_flow):
    calls, _ = booker_flow
    _message("Ответственный букер")
    selected = _button(calls, 7001)
    get_user_state(9001)["created_at"] = 0
    _message(selected)
    assert "Сессия истекла" in calls[-1]["text"]
    assert get_user_state(9001) == {}
    casting_handlers.get_castings_by_admin.assert_not_called()


def test_empty_booker_list_returns_to_menu(booker_flow):
    calls, bookers = booker_flow
    bookers.clear()
    _message("Ответственный букер")
    assert calls[-1]["text"] == "Нет букеров для просмотра."
    assert get_user_state(9001) == {}


def test_booker_service_merges_current_chief_and_historical_owners(monkeypatch):
    authorized = [
        {"telegram_id": 7001, "username": "@current", "full_name": "Current"},
        {"telegram_id": 7002, "username": None, "full_name": None},
        {"telegram_id": 7003, "username": None, "full_name": None},
        {"telegram_id": 9001, "username": "@chief"},
    ]
    monkeypatch.setattr(casting_service, "list_authorized_bookers", lambda: authorized)
    monkeypatch.setattr(casting_service, "CHIEF_BOOKER_IDS", [9001, 9002])
    connection = Mock()
    cursor = connection.cursor.return_value
    cursor.fetchall.return_value = [
        {"telegram_id": 7001, "username": "@old", "full_name": "Old"},
        {"telegram_id": 7002, "username": "@from_casting", "full_name": "From casting"},
        {"telegram_id": 7004, "username": None, "full_name": "Legacy"},
    ]
    monkeypatch.setattr(casting_service, "get_connection", lambda: connection)

    bookers = {item["telegram_id"]: item for item in casting_service.get_responsible_bookers()}

    assert list(bookers) == [7001, 7002, 7003, 7004, 9001, 9002]
    assert bookers[7001]["username"] == "@current"
    assert bookers[7002]["username"] == "@from_casting"
    assert bookers[7004]["full_name"] == "Legacy"
    assert bookers[7003]["username"] is None
    assert bookers[9001]["username"] == "@chief"
    assert authorized[1]["username"] is None
    connection.commit.assert_not_called()


def test_casting_query_uses_owner_id_and_excludes_deleted(monkeypatch):
    connection = Mock()
    cursor = connection.cursor.return_value
    monkeypatch.setattr(casting_service, "get_connection", lambda: connection)
    casting_service.get_castings_by_admin(7002)
    sql, params = cursor.execute.call_args.args
    normalized = " ".join(sql.split())
    assert params == (7002,)
    assert "c.admin_id = %s AND c.is_deleted = FALSE" in normalized
    assert "ORDER BY c.created_at DESC, c.id DESC" in normalized
    assert "is_closed = FALSE" not in normalized
    assert "LIMIT" not in normalized
    connection.commit.assert_not_called()
