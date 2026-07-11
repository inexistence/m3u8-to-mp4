"""通过 FFmpeg 将解密后的 TS 流封装为 MP4。"""
import ffmpeg
from core.merge.ts_merge import TsMerger
from pathlib import Path
import shutil
import tempfile
from tqdm import tqdm


class FfmpegMerger(TsMerger):
    """将分片流式写入临时 merged.ts，再由 FFmpeg 以 copy 模式封装为 MP4。

    相比逐分片建临时文件，单文件流式写入在大量分片时性能更好，且跨平台兼容。
    """

    def __init__(self, target_file_path: str | Path):
        if isinstance(target_file_path, str):
            self.target_file_path = Path(target_file_path)
        else:
            self.target_file_path = target_file_path
        self.tmp_dir = None
        self.merged_ts_path = None
        self.merged_ts_file = None
        self._pbar: tqdm | None = None

    def start(self):
        tmp_dir_name = tempfile.mkdtemp()
        self.tmp_dir = Path(tmp_dir_name)
        self.merged_ts_path = self.tmp_dir / 'merged.ts'
        self.merged_ts_file = open(self.merged_ts_path, 'wb')
        tqdm.write(f'tmp dir {tmp_dir_name}')

    def set_progress_total(self, total: int):
        self._pbar = tqdm(total=total, unit='seg', desc='merging', dynamic_ncols=True)

    def append(self, data: bytearray):
        self.merged_ts_file.write(data)
        if self._pbar is not None:
            self._pbar.update(1)

    def finish(self):
        if self._pbar is not None:
            self._pbar.close()
            self._pbar = None

        self.merged_ts_file.close()
        tqdm.write('converting to mp4...')
        try:
            # 进度条已关闭，可直接输出 ffmpeg 日志
            ffmpeg.input(str(self.merged_ts_path)).output(str(self.target_file_path), c='copy').run()
            tqdm.write(f'merge success, output = {self.target_file_path}')
        finally:
            shutil.rmtree(self.tmp_dir)
