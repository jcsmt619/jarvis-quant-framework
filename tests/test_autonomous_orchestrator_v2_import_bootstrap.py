from __future__ import annotations

import importlib
import runpy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ORCHESTRATOR = (
    ROOT
    / "automation"
    / "autonomous_master_plan_orchestrator_v2.py"
)


def test_orchestrator_imports_as_package() -> None:
    module = importlib.import_module(
        "automation.autonomous_master_plan_orchestrator_v2"
    )
    assert module is not None


def test_orchestrator_imports_when_loaded_by_direct_path() -> None:
    namespace = runpy.run_path(
        str(ORCHESTRATOR),
        run_name="jarvis_orchestrator_import_probe",
    )
    assert isinstance(namespace, dict)
    assert namespace
