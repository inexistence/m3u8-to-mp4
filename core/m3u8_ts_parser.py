"""媒体播放列表解析：读取 .ts 分片、解密并写入合并器。"""
from pathlib import Path

import core.utils.file as file
from core.decrypt import get_decryption
from core.decrypt.ts_decrypt import TsDecrypt
from core.decrypt.ts_decrypt_aes_128 import TsDecrypt_AES128_CBC
from core.merge.ts_merge import TsMerger
from core.utils.value import safe_int

KEY_DISCONTINUITY = '#EXT-X-DISCONTINUITY'
KEY_MEDIA_SEQUENCE = '#EXT-X-MEDIA-SEQUENCE:'
KEY_DECRYPT_KEY = '#EXT-X-KEY:'
KEY_METHOD = 'METHOD'
KEY_URI = 'URI'
KEY_IV = 'IV'


def parse_key_value(content: str, header: str) -> dict:
    """解析 m3u8 标签行（如 #EXT-X-KEY:）中的逗号分隔键值对。"""
    key_value_str = content.split(header)[1]
    res = {}
    arr = key_value_str.split(',')
    for entry in arr:
        # 只分割第一个 '='，避免 URI 等值中包含 '=' 时被截断
        pair = entry.split('=', 1)
        key = pair[0]
        value = pair[1] if len(pair) > 1 else ''
        res[key] = value
    return res


class SimpleM3U8TsParser:
    """媒体播放列表解析器：逐行读取 m3u8，解密 .ts 分片并写入 TsMerger。

    处理 #EXT-X-KEY 解密、#EXT-X-DISCONTINUITY 分段、#EXT-X-MEDIA-SEQUENCE 序号等标签。
    """
    def __init__(self, index_file_path: str | Path, ts_merger: TsMerger, aes_iv_mode: str = 'auto'):
        self.decryption = TsDecrypt()
        self.aes_iv_mode = aes_iv_mode

        if isinstance(index_file_path, str):
            self.index_file_path = Path(index_file_path)
        else:
            self.index_file_path = index_file_path

        self.ts_merger = ts_merger
        self.skip_first_part = False
        self.reset_decryption_if_part_changed = True
        self.current_part = 0
        # media_sequence: m3u8 头部 #EXT-X-MEDIA-SEQUENCE 声明的起始序号
        # segment_sequence: 当前处理到的分片序号，供标准 HLS IV 计算与自动检测使用
        self.media_sequence = 0
        self.segment_sequence: int | None = None
        self._current_key_uri: str | None = None

    def set_skip_first_part(self, skip: bool):
        self.skip_first_part = skip

    def set_reset_decryption_if_part_changed(self, reset: bool):
        self.reset_decryption_if_part_changed = reset

    def __maybe_change_part(self, line: str):
        if line == KEY_DISCONTINUITY:
            self.current_part = self.current_part + 1
            if self.reset_decryption_if_part_changed:
                self.decryption = TsDecrypt()
                self._current_key_uri = None
                self.__reset_decrypt_state()
            return

    def __reset_decrypt_state(self):
        if hasattr(self.decryption, 'reset_detect_mode'):
            self.decryption.reset_detect_mode()

    def __maybe_read_media_sequence(self, line: str):
        if not line.startswith(KEY_MEDIA_SEQUENCE):
            return
        self.media_sequence = safe_int(line.split(':', 1)[1])
        if self.segment_sequence is None:
            self.segment_sequence = self.media_sequence

    def __maybe_change_method(self, line: str):
        if not line.startswith(KEY_DECRYPT_KEY):
            return
        entry = parse_key_value(line, KEY_DECRYPT_KEY)
        method = entry[KEY_METHOD] if KEY_METHOD in entry else None
        uri = entry[KEY_URI] if KEY_URI in entry else None
        iv = entry[KEY_IV] if KEY_IV in entry else None
        if method is not None and uri is not None:
            uri = uri.strip('"')
            if uri != self._current_key_uri:
                key_path = self.index_file_path.resolve().parent / Path(uri)
                key = file.read(key_path)
                self.decryption = get_decryption(method, key, iv, iv_mode=self.aes_iv_mode)
                self._current_key_uri = uri
                if hasattr(self.decryption, 'set_key_start_sequence'):
                    if self.segment_sequence is None:
                        self.segment_sequence = self.media_sequence
                    self.decryption.set_key_start_sequence(self.segment_sequence)
        else:
            self.decryption = TsDecrypt()
            self._current_key_uri = None

    def __decrypt_and_merge_ts(self, line: str):
        if not line.endswith('.ts'):
            return
        ts_file = self.index_file_path.resolve().parent / Path(line)
        if self.segment_sequence is None:
            self.segment_sequence = self.media_sequence

        with open(ts_file, 'rb') as ts_file_handle:
            raw = ts_file_handle.read()

        # AES-128 解密需要分片序号以支持标准 HLS IV 及自动模式检测
        if isinstance(self.decryption, TsDecrypt_AES128_CBC):
            data = self.decryption.decrypt(raw, sequence_number=self.segment_sequence)
        else:
            data = self.decryption.decrypt(raw)

        if data is None:
            return

        self.segment_sequence += 1
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
        self.__maybe_read_media_sequence(line)
        self.__maybe_change_method(line)
        self.__decrypt_and_merge_ts(line)
        self.__maybe_change_part(line)

    def _count_ts_segments(self) -> int:
        count = 0

        def callback(index: int, line: str):
            nonlocal count
            line = line.strip() if line is not None else None
            if line is not None and line.endswith('.ts'):
                count += 1

        file.read_lines(self.index_file_path, callback)
        return count

    def merge(self):
        if self.skip_first_part == True:
            # if no KEY_DISCONTINUITY, can not skip first part
            self.skip_first_part = KEY_DISCONTINUITY in file.read(self.index_file_path)

        try:
            self.ts_merger.start()
            total = self._count_ts_segments()
            if total > 0:
                self.ts_merger.set_progress_total(total)
            file.read_lines(self.index_file_path, self.__handle_line)
        finally:
            self.ts_merger.finish()
