import ffmpeg
from core.merge.ts_merge import TsMerger
from pathlib import Path
import shutil
import tempfile
import uuid

class FfmpegMerger(TsMerger):

    def __init__(self, target_file_path: str|Path):
        if isinstance(target_file_path, str):
            self.target_file_path = Path(target_file_path)
        else:
            self.target_file_path = target_file_path
        self.tmp_dir = None
        self.list_file = None
    
    def start(self):
        tmp_dir_name = tempfile.mkdtemp()
        self.tmp_dir = Path(tmp_dir_name)
        self.list_file = open(self.tmp_dir / Path('file_list.txt'), 'w')
        print('tmp dir', tmp_dir_name)
    
    def append(self, data: bytearray):
        temp_file_path = self.tmp_dir / Path(str(uuid.uuid4()))
        with open(temp_file_path, 'wb') as f:
            f.write(data)
        self.list_file.write(f"file '{temp_file_path}'\n")

    def finish(self):
        self.list_file.close()
        try:
            ffmpeg.input(self.list_file.name, format='concat', safe=0).output(str(self.target_file_path), c='copy').run()
            print('merge success, output =', self.target_file_path)
        finally:
            shutil.rmtree(self.tmp_dir)
            print('clean tmp dir', self.tmp_dir)