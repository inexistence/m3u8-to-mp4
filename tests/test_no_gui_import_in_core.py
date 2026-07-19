# tests/test_no_gui_import_in_core.py
from __future__ import annotations

import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class NoGuiImportTests(unittest.TestCase):
    def test_core_and_sidecar_avoid_gui_and_ctk(self) -> None:
        banned = ('gui', 'customtkinter', 'tkinterdnd2')
        for package in ('core', 'sidecar'):
            for path in (ROOT / package).rglob('*.py'):
                tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            self.assertFalse(
                                any(alias.name == b or alias.name.startswith(b + '.') for b in banned),
                                msg=f'{path} imports {alias.name}',
                            )
                    if isinstance(node, ast.ImportFrom) and node.module:
                        self.assertFalse(
                            any(node.module == b or node.module.startswith(b + '.') for b in banned),
                            msg=f'{path} imports from {node.module}',
                        )


if __name__ == '__main__':
    unittest.main()
