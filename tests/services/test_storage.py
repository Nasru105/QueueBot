import tempfile
from pathlib import Path

from app.services import storage


def test_save_and_load_tempdir(monkeypatch):
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        # Переопределяем константы в модуле storage, чтобы файл писалcя в tempdir
        monkeypatch.setattr(storage, "DATA_DIR", str(td_path / "data"))
        monkeypatch.setattr(storage, "FILE", str(td_path / "data" / "queue_data.json"))

        data = {"1": {"queues": {}}}
        storage.save_data(data)

        loaded = storage.load_data()
        assert loaded == data
