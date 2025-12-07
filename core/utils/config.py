import json
import core.utils.file as file
import os
from pathlib import Path
from core.utils.value import get_value

CONFIG_FILE = Path(__file__).resolve().parent.parent.parent / 'config.json'
# 和 config.json 的区别是 local config 的配置不会被提交到远端，相同配置优先使用 local_config.json 下的值
LOCAL_CONFIG_FILE = Path(__file__).resolve().parent.parent.parent / 'local_config.json'

class GlobalConfig:
    def __init__(self, config: dict):
        self.skip_first_part: bool = get_value(dict=config, key='skip_first_part', default_value=False)
        self.output_file_name: str = get_value(dict=config, key='output_file_name', default_value='output.mp4')

def get_global_config() -> GlobalConfig:
    config_str = file.read(CONFIG_FILE)
    config = json.loads(config_str)

    local_config = None
    if os.path.exists(LOCAL_CONFIG_FILE):
        local_config_str = file.read(LOCAL_CONFIG_FILE)
        local_config = json.loads(local_config_str)
    
    if local_config:
        config.update(local_config)

    return GlobalConfig(config)
