from core.m3u8parser import M3U8Parser
import argparse


def main(index_file: str):
    M3U8Parser(index_file).parse()

if __name__ =='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('path', type=str)

    args = parser.parse_args()
    main(args.path)
