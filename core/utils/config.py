"""全局配置加载。"""
import os
import sys
from pathlib import Path

import yaml

import core.utils.file as file
from core.utils.value import get_value


def _app_root() -> Path:
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent.parent


def _bundled_config_path() -> Path:
    if getattr(sys, 'frozen', False):
        return Path(sys._MEIPASS) / 'config.yaml'
    return _app_root() / 'config.yaml'


CONFIG_FILE = _bundled_config_path()
LOCAL_CONFIG_FILE = _app_root() / 'local_config.yaml'

class GlobalConfig:
    """从 config.yaml / local_config.yaml 加载的运行时配置。"""
    def __init__(self, config: dict):
        self.skip_first_part: bool = get_value(dict=config, key='skip_first_part', default_value=False)
        self.output_file_name: str = get_value(dict=config, key='output_file_name', default_value='output.mp4')
        self.reset_decryption_if_part_changed: bool = get_value(dict=config, key='reset_decryption_if_part_changed', default_value=True)
        self.aes_iv_mode: str = get_value(dict=config, key='aes_iv_mode', default_value='auto')
        self.stream_selection: str = get_value(dict=config, key='stream_selection', default_value='highest_bandwidth')

    def to_local_dict(self) -> dict:
        return {
            'skip_first_part': self.skip_first_part,
            'output_file_name': self.output_file_name,
            'reset_decryption_if_part_changed': self.reset_decryption_if_part_changed,
            'aes_iv_mode': self.aes_iv_mode,
        }

    def apply_local_dict(self, data: dict) -> None:
        if 'skip_first_part' in data:
            self.skip_first_part = bool(data['skip_first_part'])
        if 'output_file_name' in data:
            self.output_file_name = str(data['output_file_name'])
        if 'reset_decryption_if_part_changed' in data:
            self.reset_decryption_if_part_changed = bool(data['reset_decryption_if_part_changed'])
        if 'aes_iv_mode' in data:
            self.aes_iv_mode = str(data['aes_iv_mode'])

    def reload_from_disk(self) -> None:
        """从 config.yaml / local_config.yaml 重新加载，覆盖当前内存值。"""
        fresh = get_global_config()
        self.skip_first_part = fresh.skip_first_part
        self.output_file_name = fresh.output_file_name
        self.reset_decryption_if_part_changed = fresh.reset_decryption_if_part_changed
        self.aes_iv_mode = fresh.aes_iv_mode
        self.stream_selection = fresh.stream_selection

def _load_yaml(path: Path) -> dict:
    content = file.read(path)
    data = yaml.safe_load(content)
    return data if isinstance(data, dict) else {}

def get_global_config() -> GlobalConfig:
    """加载 config.yaml，并用 local_config.yaml 中的同名字段覆盖。"""
    config = _load_yaml(CONFIG_FILE)

    if os.path.exists(LOCAL_CONFIG_FILE):
        local_config = _load_yaml(LOCAL_CONFIG_FILE)
        if local_config:
            config.update(local_config)

    return GlobalConfig(config)


def save_local_config(global_config: GlobalConfig) -> None:
    """将 GUI 修改的配置写入 local_config.yaml。"""
    LOCAL_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    content = yaml.safe_dump(
        global_config.to_local_dict(),
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
    )
    with open(LOCAL_CONFIG_FILE, 'w', encoding='utf-8') as f:
        f.write(content)
