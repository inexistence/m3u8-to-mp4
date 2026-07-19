"""用户配置路径与 AppData 读写测试。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from core.utils.config import (
    GlobalConfig,
    get_global_config,
    legacy_local_config_path,
    save_local_config,
    user_config_dir,
    user_config_path,
)


class UserConfigPathTests(unittest.TestCase):
    def test_user_config_dir_uses_appdata_on_windows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with (
                patch('core.utils.config.sys.platform', 'win32'),
                patch.dict('os.environ', {'APPDATA': tmp}, clear=False),
            ):
                self.assertEqual(user_config_dir(), Path(tmp) / 'm3u8-to-mp4')
                self.assertEqual(user_config_path(), Path(tmp) / 'm3u8-to-mp4' / 'config.yaml')

    def test_save_writes_to_appdata_not_app_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            appdata = Path(tmp) / 'AppData'
            appdata.mkdir()
            with (
                patch('core.utils.config.sys.platform', 'win32'),
                patch.dict('os.environ', {'APPDATA': str(appdata)}, clear=False),
            ):
                cfg = GlobalConfig({
                    'output_file_name': 'from-gui.mp4',
                    'max_parallel_conversions': 3,
                })
                save_local_config(cfg)
                path = user_config_path()
                self.assertTrue(path.is_file())
                data = yaml.safe_load(path.read_text(encoding='utf-8'))
                self.assertEqual(data['output_file_name'], 'from-gui.mp4')
                self.assertEqual(data['max_parallel_conversions'], 3)
                self.assertFalse(legacy_local_config_path().is_file())

    def test_load_prefers_appdata_over_legacy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            appdata = Path(tmp) / 'AppData'
            app_root = Path(tmp) / 'app'
            appdata.mkdir()
            app_root.mkdir()
            user_file = appdata / 'm3u8-to-mp4' / 'config.yaml'
            user_file.parent.mkdir(parents=True)
            user_file.write_text('output_file_name: from-appdata.mp4\n', encoding='utf-8')
            legacy = app_root / 'local_config.yaml'
            legacy.write_text('output_file_name: from-legacy.mp4\n', encoding='utf-8')
            defaults = Path(tmp) / 'defaults.yaml'
            defaults.write_text('output_file_name: default.mp4\n', encoding='utf-8')

            with (
                patch('core.utils.config.sys.platform', 'win32'),
                patch.dict('os.environ', {'APPDATA': str(appdata)}, clear=False),
                patch('core.utils.config.CONFIG_FILE', defaults),
                patch('core.utils.config._app_root', return_value=app_root),
            ):
                cfg = get_global_config()
            self.assertEqual(cfg.output_file_name, 'from-appdata.mp4')

    def test_load_falls_back_to_legacy_local_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            appdata = Path(tmp) / 'AppData'
            app_root = Path(tmp) / 'app'
            appdata.mkdir()
            app_root.mkdir()
            legacy = app_root / 'local_config.yaml'
            legacy.write_text('output_file_name: from-legacy.mp4\n', encoding='utf-8')
            defaults = Path(tmp) / 'defaults.yaml'
            defaults.write_text('output_file_name: default.mp4\n', encoding='utf-8')

            with (
                patch('core.utils.config.sys.platform', 'win32'),
                patch.dict('os.environ', {'APPDATA': str(appdata)}, clear=False),
                patch('core.utils.config.CONFIG_FILE', defaults),
                patch('core.utils.config._app_root', return_value=app_root),
            ):
                cfg = get_global_config()
            self.assertEqual(cfg.output_file_name, 'from-legacy.mp4')


if __name__ == '__main__':
    unittest.main()
