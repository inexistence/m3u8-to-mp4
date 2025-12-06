from core.m3u8converter import M3U8Converter
import argparse


def main(index_file: str):
    M3U8Converter(index_file).convert()

if __name__ =='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('path', type=str)

    args = parser.parse_args()
    main(args.path)
