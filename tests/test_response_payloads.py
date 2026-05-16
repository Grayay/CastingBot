from handlers.response_handlers import parse_respond_payload


def test_parse_respond_payload_supports_casting_id_payload():
    parsed = parse_respond_payload("respond_casting_42")
    assert parsed == {"type": "casting_id", "casting_id": 42}


def test_parse_respond_payload_supports_legacy_channel_message_payload():
    parsed = parse_respond_payload("respond_-1001234567890_987")
    assert parsed == {
        "type": "channel_message",
        "channel_id": -1001234567890,
        "message_id": 987,
    }


def test_parse_respond_payload_supports_plain_legacy_casting_id():
    parsed = parse_respond_payload("77")
    assert parsed == {"type": "casting_id", "casting_id": 77}


def test_parse_respond_payload_rejects_invalid_payload():
    assert parse_respond_payload("respond_bad_payload") is None

