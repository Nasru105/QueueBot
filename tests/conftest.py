import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class _DummyCollection:
    def __getitem__(self, _):
        return self


class _DummyDB(dict):
    def __getitem__(self, name):
        return self.setdefault(name, _DummyCollection())


class _DummyMotorClient:
    def __init__(self, *_, **__):
        self._dbs = {}

    def __getitem__(self, name):
        return self._dbs.setdefault(name, _DummyDB())


motor_module = ModuleType("motor")
motor_asyncio_module = ModuleType("motor.motor_asyncio")
motor_asyncio_module.AsyncIOMotorClient = _DummyMotorClient
motor_module.motor_asyncio = motor_asyncio_module
sys.modules.setdefault("motor", motor_module)
sys.modules.setdefault("motor.motor_asyncio", motor_asyncio_module)
