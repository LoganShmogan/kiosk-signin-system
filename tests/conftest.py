import pytest
import database as db_module


@pytest.fixture
def db(tmp_path, monkeypatch):
    """Fresh temp-file DB for each test, with seed data from init_db."""
    monkeypatch.setattr(db_module, "DB_PATH", str(tmp_path / "test.db"))
    db_module.init_db()
    return db_module
