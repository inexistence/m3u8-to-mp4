"""全局配置加载。"""
import os
from pathlib import Path

import yaml

import core.utils.file as file
from core.utils.value import get_value

CONFIG_FILE = Path(__file__).resolve().parent.parent.parent / 'config.yaml'
# 和 config.yaml 的区别是 local config 的配置不会被提交到远端，相同配置优先使用 local_config.yaml 下的值
LOCAL_CONFIG_FILE = Path(__file__).resolve().parent.parent.parent / 'local_config.yaml'

class GlobalConfig:
    """从 config.yaml / local_config.yaml 加载的运行时配置。"""
    def __init__(self, config: dict):
        self.skip_first_part: bool = get_value(dict=config, key='skip_first_part', default_value=False)
        self.output_file_name: str = get_value(dict=config, key='output_file_name', default_value='output.mp4')
        self.reset_decryption_if_part_changed: bool = get_value(dict=config, key='reset_decryption_if_part_changed', default_value=True)
        self.aes_iv_mode: str = get_value(dict=config, key='aes_iv_mode', default_value='auto')
        self.stream_selection: str = get_value(dict=config, key='stream_selection', default_value='highest_bandwidth')

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
