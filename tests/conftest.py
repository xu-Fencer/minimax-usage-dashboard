import pytest
import app.db as db_module


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    test_db = tmp_path / "test.db"
    monkeypatch.setattr(db_module, "DB_PATH", test_db)
    db_module.init_db()
    yield
