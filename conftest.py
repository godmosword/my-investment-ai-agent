"""Pytest conftest: stub heavy/unavailable modules before test collection."""

import sys
from types import ModuleType
from unittest.mock import MagicMock

# Modules that may not be installed in CI or require credentials at import
_STUB_MODULES = [
    "feedparser",
    "litellm",
    "crewai",
    "crewai.tools",
    "crewai_tools",
    "yfinance",
    "telebot",
    "streamlit",
    "plotly",
    "plotly.express",
    "plotly.graph_objects",
    "matplotlib",
    "matplotlib.pyplot",
    "matplotlib.gridspec",
    "matplotlib.dates",
]


def _ensure_stub(name: str) -> ModuleType:
    if name in sys.modules:
        return sys.modules[name]
    mod = ModuleType(name)
    sys.modules[name] = mod
    return mod


for _mod_name in _STUB_MODULES:
    _ensure_stub(_mod_name)

# crewai.tools needs a @tool decorator that acts as passthrough
_crewai_tools = sys.modules["crewai.tools"]


def _fake_tool(func=None, **kwargs):
    if func is not None:
        func.run = func
        return func

    def wrapper(fn):
        fn.run = fn
        return fn
    return wrapper


_crewai_tools.tool = _fake_tool

# crewai needs Agent, Crew, LLM, Process, Task
_crewai = sys.modules["crewai"]
for _cls_name in ("Agent", "Crew", "LLM", "Process", "Task"):
    setattr(_crewai, _cls_name, MagicMock)

# telebot needs TeleBot class
sys.modules["telebot"].TeleBot = type(
    "TeleBot", (), {"__init__": lambda *a, **kw: None}
)

# google.cloud.bigquery — ensure SchemaField, Client etc. exist
_bq = _ensure_stub("google.cloud.bigquery")
_bq.Client = MagicMock
_bq.SchemaField = MagicMock
_bq.LoadJobConfig = MagicMock
_bq.SourceFormat = MagicMock
_bq.WriteDisposition = MagicMock

_gc = _ensure_stub("google.cloud")
_gc.bigquery = _bq
