import core.utils.file as file
from core.utils.value import safe_int
from pathlib import Path
from core.decrypt import get_decryption
from core.decrypt.ts_decrypt import TsDecrypt
from core.decrypt.ts_decrypt_aes_128 import TsDecrypt_AES128_CBC
from core.merge.ts_merge import TsMerger
from core.merge.simple_merge import SimpleMerger
from core.merge.ffmpeg_merge import FfmpegMerger
from core.utils.config import GlobalConfig

KEY_EXT_X_STREAM_INF = '#EXT-X-STREAM-INF:'
KEY_PROGRAM_ID='PROGRAM-ID'
KEY_BANDWIDTH='BANDWIDTH'
KEY_RESOLUTION='RESOLUTION'

KEY_DISCONTINUITY='#EXT-X-DISCONTINUITY'
KEY_DECRYPT_KEY='#EXT-X-KEY:'
KEY_METHOD='METHOD'
KEY_URI='URI'
KEY_IV='IV'

def parse_key_value(content: str, header: str) -> dict:
    key_value_str = content.split(header)[1]
    res = {}
    arr = key_value_str.split(',')
    for entry in arr:
        pair = entry.split('=')
        key = pair[0]
        value = pair[1]
        res[key]=value
    return res

class SimpleM3U8TsParser:

    def __init__(self, index_file_path: str|Path, ts_merger: TsMerger):
        self.decryption = TsDecrypt()

        if isinstance(index_file_path, str):
            self.index_file_path = Path(index_file_path)
        else:
            self.index_file_path = index_file_path
        
        self.ts_merger = ts_merger
        self.skip_first_part = False
        self.current_part = 0

    def set_skip_first_part(self, skip: bool):
        self.skip_first_part = skip

    def __maybe_change_part(self, line: str):
        if line == KEY_DISCONTINUITY:
            self.current_part = self.current_part+1
            # reset decryption
            self.decryption = TsDecrypt()
            return

    def __maybe_change_method(self, line: str):
        if not line.startswith(KEY_DECRYPT_KEY):
            return
        entry = parse_key_value(line, KEY_DECRYPT_KEY)
        method = entry[KEY_METHOD] if KEY_METHOD in entry else None
        uri = entry[KEY_URI] if KEY_URI in entry else None
        iv = entry[KEY_IV] if KEY_IV in entry else None
        if method is not None and uri is not None:
            uri = uri.strip('"')
            key_path = self.index_file_path.resolve().parent / Path(uri)
            key = file.read(key_path)
            self.decryption = get_decryption(method, key, iv)
        else:
            self.decryption = TsDecrypt()

    def __decrypt_and_merge_ts(self, line: str):
        if not line.endswith('.ts'):
            return
        ts_file = self.index_file_path.resolve().parent / Path(line)
        data = None
        with open(ts_file, 'rb') as file:
            data = self.decryption.decrypt(file.read())

        if data is None:
            return

        self.ts_merger.append(data)

    def __handle_line(self, index: int, line: str):
        line = line.strip() if line is not None else None
        if line is None:
            return

        if self.skip_first_part == True and self.current_part == 0:
            cur_part_tmp = self.current_part
            self.__maybe_change_part(line)
            if self.current_part != cur_part_tmp:
                print('part 0 is skipped')
            return
        self.__maybe_change_method(line)
        self.__decrypt_and_merge_ts(line)
        self.__maybe_change_part(line)

    def merge(self):
        if self.skip_first_part == True:
            # if no KEY_DISCONTINUITY, can not skip first part
            self.skip_first_part = KEY_DISCONTINUITY in file.read(self.index_file_path)

        # 写入二进制文件
        try:
            self.ts_merger.start()
            file.read_lines(self.index_file_path, self.__handle_line)
        finally:
            self.ts_merger.finish()


class M3U8StreamInfoParser:
    def __init__(self, m3u8_index_file_path: str|Path):
        if isinstance(m3u8_index_file_path, Path):
            self.m3u8_index_file_path = m3u8_index_file_path
        else:
            self.m3u8_index_file_path = Path(m3u8_index_file_path)
        self.m3u8_ts_info_file = None
        self.program_id=0
        self.band_width=0
        self.resolution=""

    def __parse_stream_info(self, line: str):
        if not line.startswith(KEY_EXT_X_STREAM_INF):
            return
        stream_info = line.split(KEY_EXT_X_STREAM_INF)[1]
        infos = stream_info.split(',')
        for info in infos:
            entry = info.split('=')
            key = entry[0]
            value = entry[1]
            if key == KEY_PROGRAM_ID:
                self.program_id = safe_int(value)
            elif key == KEY_BANDWIDTH:
                self.band_width = safe_int(value)
            elif key == KEY_RESOLUTION:
                self.resolution = value

    def __parse_m3u8_ts_info_file(self, line: str):
        if not line.endswith('.m3u8'):
            return
        self.m3u8_ts_info_file = self.m3u8_index_file_path.resolve().parent / Path(line)

    def __parse_line(self, index: int, line: str):
        line = line.strip() if line is not None else None
        if line is None:
            return

        self.__parse_stream_info(line)
        self.__parse_m3u8_ts_info_file(line)

    def parse(self):
        file.read_lines(self.m3u8_index_file_path, self.__parse_line)

    def print_stream_info(self):
        print('m3u8_ts_info_file =', self.m3u8_ts_info_file)
        print('program_id =', self.program_id)
        print('band_width =', self.band_width)
        print('resolution =', self.resolution)

class M3U8Converter:
    def __init__(self, m3u8_index_file_path: str|Path, config: GlobalConfig):
        self.m3u8_index_file_path: Path = Path(m3u8_index_file_path) if not isinstance(m3u8_index_file_path, Path) else m3u8_index_file_path
        self.dir: Path = Path(m3u8_index_file_path).resolve().parent
        self.config = config
        self.m3u8_stream_info_parser = M3U8StreamInfoParser(self.m3u8_index_file_path)
        
    def print_stream_info(self):
        self.m3u8_stream_info_parser.print_stream_info()

    def convert(self):
        # parse m3u8 index for stream info
        self.m3u8_stream_info_parser.parse()
        ts_infos_index_file_path = self.m3u8_stream_info_parser.m3u8_ts_info_file

        # can not found ts info index, try stream info index
        if ts_infos_index_file_path is None:
            ts_infos_index_file_path = self.m3u8_stream_info_parser.m3u8_index_file_path

        # parse m3u8 index2 for ts info
        out_put_file_name = self.config.output_file_name
        if out_put_file_name == '__DIR_NAME__':
            out_put_file_name = self.dir.name

        if not out_put_file_name.endswith('.mp4'):
            out_put_file_name = out_put_file_name + '.mp4'

        merger = FfmpegMerger(self.dir / out_put_file_name)
        ts_parser = SimpleM3U8TsParser(ts_infos_index_file_path, merger)
        ts_parser.set_skip_first_part(self.config.skip_first_part)
        ts_parser.merge()
        print('convert end')

        
