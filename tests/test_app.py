import importlib


def test_app_imports_cleanly():
    importlib.import_module("app")
