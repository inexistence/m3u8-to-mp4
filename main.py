from core.m3u8converter import M3U8Converter
import argparse
from core.utils.config import get_global_config

def main(index_file: str):
    config = get_global_config()

    converter = M3U8Converter(index_file)
    converter.set_skip_first_part(config.skip_first_part)
    converter.convert()

if __name__ =='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('path', type=str)

    args = parser.parse_args()
    main(args.path)
