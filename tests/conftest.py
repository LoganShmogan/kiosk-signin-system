import pytest
import database as db_module


@pytest.fixture
def db(tmp_path, monkeypatch):
    """Fresh temp-file DB for each test, with seed data from init_db."""
    monkeypatch.setattr(db_module, "DB_PATH", str(tmp_path / "test.db"))
    db_module.init_db()
    return db_module


@pytest.fixture
def tk_root():
    """Real (not withdrawn) Tk root so hover/crossing events actually fire.
    Skipped automatically when no display is available (e.g. headless CI)."""
    try:
        import tkinter as tk
        root = tk.Tk()
        root.geometry("1x1+0+0")
        root.update()
        yield root
        root.destroy()
    except Exception:
        pytest.skip("no display available")
