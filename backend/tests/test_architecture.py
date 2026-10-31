"""The dependency rules in AGENTS.md, enforced."""

import ast
from pathlib import Path

ROOT = Path(__file__).parents[1]
CORE = ("api", "workflows", "modules", "repository", "schemas", "llm", "shared")


def imports(package: str):
    for path in (ROOT / package).rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("backend."):
                yield path.relative_to(ROOT), node.module


def test_core_never_imports_a_feature():
    assert [(str(path), module) for package in CORE for path, module in imports(package)
            if module.startswith(("backend.illustrations", "backend.recall"))] == []


def test_modules_never_import_workflows_or_api():
    assert [(str(path), module) for path, module in imports("modules")
            if module.startswith(("backend.workflows", "backend.api"))] == []


def test_lower_layers_never_import_upper_layers():
    upper = tuple(f"backend.{name}" for name in ("api", "workflows", "modules"))
    for package in ("repository", "schemas", "shared"):
        assert [(str(path), module) for path, module in imports(package) if module.startswith(upper)] == []
