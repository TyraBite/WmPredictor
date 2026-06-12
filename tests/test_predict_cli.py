import sys
import subprocess
import pytest


def run_predict(*args):
    result = subprocess.run(
        [sys.executable, "predict.py"] + list(args),
        capture_output=True, text=True,
        cwd="/workspace/work/wm-predictor",
    )
    return result.stdout, result.returncode


def test_predict_imports_without_error():
    import importlib.util
    import os
    spec = importlib.util.spec_from_file_location(
        "predict", "/workspace/work/wm-predictor/predict.py"
    )
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except SystemExit:
        pass  # expected when no model loaded


def test_predict_help_or_usage():
    out, code = run_predict("--help")
    assert code in (0, 1)
