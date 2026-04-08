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

# Classes that must exist on each stub module (default: MagicMock)
_STUB_CLASSES = {
    "crewai": ["Agent", "Crew", "LLM", "Process", "Task"],
    "telebot": ["TeleBot"],
    "google.cloud.bigquery": [
        "Client",
        "SchemaField",
        "LoadJobConfig",
        "QueryJobConfig",
        "ScalarQueryParameter",
        "SourceFormat",
        "WriteDisposition",
        "Table",
    ],
}


def _ensure_stub(name: str) -> ModuleType:
    if name in sys.modules:
        return sys.modules[name]
    mod = ModuleType(name)
    sys.modules[name] = mod
    return mod


for _mod_name in _STUB_MODULES:
    _ensure_stub(_mod_name)

# Attach required class attributes to stubs
for _mod_name, _classes in _STUB_CLASSES.items():
    _mod = _ensure_stub(_mod_name)
    for _cls_name in _classes:
        setattr(_mod, _cls_name, MagicMock)


# crewai.tools needs a @tool decorator that acts as passthrough
def _fake_tool(func=None, **kwargs):
    if func is not None:
        func.run = func
        return func

    def wrapper(fn):
        fn.run = fn
        return fn
    return wrapper


sys.modules["crewai.tools"].tool = _fake_tool

# Wire google.cloud parent to bigquery stub
_gc = _ensure_stub("google.cloud")
_gc.bigquery = sys.modules["google.cloud.bigquery"]

# telebot.apihelper：main._send_telegram_report 會 `from telebot import apihelper`
_tb_mod = sys.modules.get("telebot")
if _tb_mod is not None:
    _ah = ModuleType("telebot.apihelper")
    _ah.SESSION_TIME_TO_LIVE = 300
    sys.modules["telebot.apihelper"] = _ah
    _tb_mod.apihelper = _ah
