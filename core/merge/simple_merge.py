from core.merge.ts_merge import TsMerger
from pathlib import Path

class SimpleMerger(TsMerger):

    def __init__(self, target_file_path: str|Path):
        if isinstance(target_file_path, str):
            self.target_file_path = Path(target_file_path)
        else:
            self.target_file_path = target_file_path
        self.target_file = None
    
    def start(self):
        self.target_file = open(self.target_file_path, 'wb')
    
    def append(self, data: bytearray):
        self.target_file.write(data)

    def finish(self):
        self.target_file.close()