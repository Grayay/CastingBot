from copy import deepcopy

from services import access_control


class FakeCursor:
    def __init__(self, db):
        self.db = db
        self.rowcount = 0
        self._one = None
        self._many = []

    def execute(self, sql, params=None):
        normalized = " ".join(sql.split()).lower()
        params = params or ()
        self.rowcount = 0
        self._one = None
        self._many = []

        if normalized.startswith("create table"):
            return

        if normalized.startswith("select value from access_control_meta"):
            value = self.db.meta.get(params[0])
            self._one = {"value": value} if value is not None else None
            return

        if normalized.startswith("insert into access_control_meta"):
            key, value = params[0], params[1]
            self.db.meta[key] = value
            self.rowcount = 1
            return

        if normalized.startswith("insert into authorized_bookers") and "returning telegram_id" in normalized:
            telegram_id, username, full_name, added_by = params
            if telegram_id in self.db.bookers:
                self._one = None
                self.rowcount = 0
                return
            self.db.bookers[telegram_id] = {
                "telegram_id": telegram_id,
                "username": username,
                "full_name": full_name,
                "added_by": added_by,
                "created_at": None,
            }
            self._one = {"telegram_id": telegram_id}
            self.rowcount = 1
            return

        if normalized.startswith("insert into authorized_bookers"):
            telegram_id = params[0]
            if telegram_id not in self.db.bookers:
                self.db.bookers[telegram_id] = {
                    "telegram_id": telegram_id,
                    "username": None,
                    "full_name": None,
                    "added_by": None,
                    "created_at": None,
                }
                self.rowcount = 1
            return

        if normalized.startswith("select telegram_id from authorized_bookers"):
            self._one = self.db.bookers.get(params[0])
            return

        if normalized.startswith("delete from authorized_bookers"):
            self.rowcount = 1 if self.db.bookers.pop(params[0], None) is not None else 0
            return

        if normalized.startswith("select telegram_id, username, full_name, added_by, created_at"):
            self._many = [self.db.bookers[key] for key in sorted(self.db.bookers)]
            return

        raise AssertionError(f"Unexpected SQL: {sql}")

    def fetchone(self):
        return self._one

    def fetchall(self):
        return list(self._many)


class FakeConnection:
    def __init__(self):
        self.bookers = {}
        self.meta = {}
        self.castings = [{"id": 1, "admin_id": 7001}]
        self.responses = [{"id": 10, "casting_id": 1, "model_id": 20}]
        self.commits = 0

    def cursor(self):
        return FakeCursor(self)

    def commit(self):
        self.commits += 1


def test_first_startup_seeds_legacy_booker_ids_once_and_removal_survives_restart(monkeypatch):
    db = FakeConnection()
    monkeypatch.setattr(access_control, "BOOKER_IDS", [7001, 7002])
    monkeypatch.setattr(access_control, "CHIEF_BOOKER_IDS", [9001])

    assert access_control.seed_legacy_booker_ids_once(db) == 2
    assert access_control.is_authorized_booker(7001, db) is True

    assert access_control.remove_authorized_booker(7001, db) is True
    assert access_control.is_authorized_booker(7001, db) is False

    assert access_control.seed_legacy_booker_ids_once(db) == 0
    assert access_control.is_authorized_booker(7001, db) is False
    assert access_control.is_authorized_booker(7002, db) is True


def test_chief_booker_access_and_regular_booker_add_remove(monkeypatch):
    db = FakeConnection()
    monkeypatch.setattr(access_control, "CHIEF_BOOKER_IDS", [9001])

    assert access_control.is_authorized_booker(9001, db) is True

    assert access_control.add_authorized_booker(7003, added_by=9001, connection=db) is True
    assert access_control.is_authorized_booker(7003, db) is True

    assert access_control.remove_authorized_booker(7003, db) is True
    assert access_control.is_authorized_booker(7003, db) is False


def test_chief_booker_cannot_be_removed(monkeypatch):
    db = FakeConnection()
    monkeypatch.setattr(access_control, "CHIEF_BOOKER_IDS", [9001])

    assert access_control.remove_authorized_booker(9001, db) is False
    assert access_control.is_authorized_booker(9001, db) is True


def test_removing_booker_does_not_delete_castings_or_responses(monkeypatch):
    db = FakeConnection()
    monkeypatch.setattr(access_control, "CHIEF_BOOKER_IDS", [9001])
    access_control.add_authorized_booker(7001, added_by=9001, connection=db)
    castings_before = deepcopy(db.castings)
    responses_before = deepcopy(db.responses)

    assert access_control.remove_authorized_booker(7001, db) is True

    assert db.castings == castings_before
    assert db.responses == responses_before
