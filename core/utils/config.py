"""全局配置加载。"""
import os
import sys
from pathlib import Path

import yaml

import core.utils.file as file
from core.utils.value import get_value

APP_NAME = 'm3u8-to-mp4'


def _app_root() -> Path:
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent.parent


def _bundled_config_path() -> Path:
    if getattr(sys, 'frozen', False):
        return Path(sys._MEIPASS) / 'config.yaml'
    return _app_root() / 'config.yaml'


def user_config_dir() -> Path:
    """用户可写配置目录：Windows 为 %APPDATA%\\m3u8-to-mp4。"""
    if sys.platform == 'win32':
        base = os.environ.get('APPDATA')
        if base:
            return Path(base) / APP_NAME
    xdg = os.environ.get('XDG_CONFIG_HOME')
    if xdg:
        return Path(xdg) / APP_NAME
    return Path.home() / '.config' / APP_NAME


def user_config_path() -> Path:
    """用户覆盖配置文件路径。"""
    return user_config_dir() / 'config.yaml'


def legacy_local_config_path() -> Path:
    """旧版程序目录旁的 local_config.yaml，仅用于读取迁移。"""
    return _app_root() / 'local_config.yaml'


CONFIG_FILE = _bundled_config_path()


def normalize_max_parallel_conversions(value: object) -> int:
    """规范并发数：非法/缺失 → 2；小于 1 → 2；大于 8 → 8。"""
    try:
        n = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 2
    if n < 1:
        return 2
    if n > 8:
        return 8
    return n


class GlobalConfig:
    """从默认 config.yaml 与用户配置加载的运行时配置。"""
    def __init__(self, config: dict):
        self.skip_first_part: bool = get_value(dict=config, key='skip_first_part', default_value=False)
        self.output_file_name: str = get_value(dict=config, key='output_file_name', default_value='output.mp4')
        self.output_directory: str | None = self._normalize_output_directory(
            get_value(dict=config, key='output_directory', default_value=None)
        )
        self.reset_decryption_if_part_changed: bool = get_value(dict=config, key='reset_decryption_if_part_changed', default_value=True)
        self.aes_iv_mode: str = get_value(dict=config, key='aes_iv_mode', default_value='auto')
        self.stream_selection: str = get_value(dict=config, key='stream_selection', default_value='highest_bandwidth')
        self.max_parallel_conversions: int = normalize_max_parallel_conversions(
            get_value(dict=config, key='max_parallel_conversions', default_value=2)
        )

    @staticmethod
    def _normalize_output_directory(value: object) -> str | None:
        if value is None:
            return None
        value = str(value).strip()
        return value or None

    def to_local_dict(self) -> dict:
        return {
            'skip_first_part': self.skip_first_part,
            'output_file_name': self.output_file_name,
            'output_directory': self.output_directory,
            'reset_decryption_if_part_changed': self.reset_decryption_if_part_changed,
            'aes_iv_mode': self.aes_iv_mode,
            'max_parallel_conversions': self.max_parallel_conversions,
        }

    def apply_local_dict(self, data: dict) -> None:
        if 'skip_first_part' in data:
            self.skip_first_part = bool(data['skip_first_part'])
        if 'output_file_name' in data:
            self.output_file_name = str(data['output_file_name'])
        if 'output_directory' in data:
            self.output_directory = self._normalize_output_directory(data['output_directory'])
        if 'reset_decryption_if_part_changed' in data:
            self.reset_decryption_if_part_changed = bool(data['reset_decryption_if_part_changed'])
        if 'aes_iv_mode' in data:
            self.aes_iv_mode = str(data['aes_iv_mode'])
        if 'max_parallel_conversions' in data:
            self.max_parallel_conversions = normalize_max_parallel_conversions(data['max_parallel_conversions'])

    def reload_from_disk(self) -> None:
        """从默认配置与用户配置重新加载，覆盖当前内存值。"""
        fresh = get_global_config()
        self.skip_first_part = fresh.skip_first_part
        self.output_file_name = fresh.output_file_name
        self.output_directory = fresh.output_directory
        self.reset_decryption_if_part_changed = fresh.reset_decryption_if_part_changed
        self.aes_iv_mode = fresh.aes_iv_mode
        self.stream_selection = fresh.stream_selection
        self.max_parallel_conversions = fresh.max_parallel_conversions


def _load_yaml(path: Path) -> dict:
    content = file.read(path)
    data = yaml.safe_load(content)
    return data if isinstance(data, dict) else {}


def _resolve_user_override_path() -> Path | None:
    """优先 AppData；若不存在则回退到旧版程序目录 local_config.yaml。"""
    user_path = user_config_path()
    if user_path.is_file():
        return user_path
    legacy_path = legacy_local_config_path()
    if legacy_path.is_file():
        return legacy_path
    return None


def get_global_config() -> GlobalConfig:
    """加载默认 config.yaml，并用用户配置中的同名字段覆盖。"""
    config = _load_yaml(CONFIG_FILE)

    override_path = _resolve_user_override_path()
    if override_path is not None:
        local_config = _load_yaml(override_path)
        if local_config:
            config.update(local_config)

    return GlobalConfig(config)


def save_local_config(global_config: GlobalConfig) -> None:
    """将 GUI 修改的配置写入 %APPDATA%\\m3u8-to-mp4\\config.yaml。"""
    path = user_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    content = yaml.safe_dump(
        global_config.to_local_dict(),
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
    )
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
