from core.m3u8converter import M3U8Converter
import argparse
from core.utils.config import (get_global_config, GlobalConfig)
import os
from pathlib import Path

def handle_file(index_file_path: str|Path, config: GlobalConfig):
    print('start convert', index_file_path)
    converter = M3U8Converter(m3u8_index_file_path=index_file_path, config=config)
    converter.convert()

def search_indexs(directory: Path) -> list[Path]:
    index_path_list = []
    for entry in directory.iterdir():
        if entry.is_file() and entry.name.endswith('.m3u8'):
            index_path_list.append(entry)
            return index_path_list
        elif entry.is_dir():
            indexes_in_sub_directories = search_indexs(entry)
            index_path_list += indexes_in_sub_directories
    return index_path_list


def main(path_name: Path):
    config = get_global_config()

    if os.path.isfile(path_name):
        handle_file(index_file_path=path_name, config=config)
    elif os.path.isdir(path_name):
        index_files = search_indexs(path_name)
        # TODO multi thread
        for file in index_files:
            handle_file(index_file_path=file, config=config)

if __name__ =='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('path', type=str)

    args = parser.parse_args()
    main(Path(args.path))
