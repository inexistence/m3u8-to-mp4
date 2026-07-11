from core.m3u8converter import M3U8Converter
from core.discovery import find_entry_m3u8
import argparse
from core.utils.config import (get_global_config, GlobalConfig)
import os
from pathlib import Path

def handle_file(index_file_path: str|Path, config: GlobalConfig):
    print('start convert', index_file_path)
    converter = M3U8Converter(m3u8_index_file_path=index_file_path, config=config)
    converter.convert()


def main(path_name: Path):
    config = get_global_config()

    if os.path.isfile(path_name):
        handle_file(index_file_path=path_name, config=config)
    elif os.path.isdir(path_name):
        index_files = find_entry_m3u8(path_name)
        if not index_files:
            print('no .m3u8 files found in', path_name)
            return
        print(f'found {len(index_files)} .m3u8 file(s)')
        # TODO multi thread
        for file in index_files:
            handle_file(index_file_path=file, config=config)
    else:
        raise TypeError('not file nor dir')

if __name__ =='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('path', type=str)

    args = parser.parse_args()
    main(Path(args.path))
