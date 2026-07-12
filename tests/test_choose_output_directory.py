"""输出目录选择交互测试。"""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from gui.app import M3u8GuiApp


class ChooseOutputDirectoryTests(unittest.TestCase):
    def test_cancel_does_not_clear_existing_directory(self) -> None:
        """取消选目录对话框应保留当前配置，而不是写成 None。"""
        app = object.__new__(M3u8GuiApp)
        app.is_converting = False
        app.global_config = MagicMock(output_directory=r'D:\videos')
        set_calls: list[str | None] = []
        app._set_output_directory = set_calls.append  # type: ignore[method-assign]

        with patch('gui.app.filedialog.askdirectory', return_value=''):
            M3u8GuiApp._choose_output_directory(app)

        self.assertEqual(set_calls, [])

    def test_select_directory_updates_config(self) -> None:
        app = object.__new__(M3u8GuiApp)
        app.is_converting = False
        app.global_config = MagicMock(output_directory=None)
        set_calls: list[str | None] = []
        app._set_output_directory = set_calls.append  # type: ignore[method-assign]

        with patch('gui.app.filedialog.askdirectory', return_value=r'E:\out'):
            M3u8GuiApp._choose_output_directory(app)

        self.assertEqual(set_calls, [r'E:\out'])


if __name__ == '__main__':
    unittest.main()
