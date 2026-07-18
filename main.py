from core.m3u8converter import M3U8Converter
from core.batch_convert import BatchCancelController, BatchCallbacks, run_batch_conversions
from core.discovery import find_entry_m3u8, M3u8Entry
import argparse
from core.utils.config import (get_global_config, GlobalConfig)
from core.utils.ffmpeg_check import ensure_ffmpeg, ffmpeg_missing_message
from core.models import ConversionTask
import os
import sys
from pathlib import Path

def handle_file(index_file_path: str|Path, config: GlobalConfig):
    print('start convert', index_file_path)
    converter = M3U8Converter(m3u8_index_file_path=index_file_path, config=config)
    converter.convert()


def main(path_name: Path):
    try:
        ensure_ffmpeg()
    except RuntimeError:
        print(ffmpeg_missing_message(), file=sys.stderr)
        sys.exit(1)

    config = get_global_config()

    if os.path.isfile(path_name):
        handle_file(index_file_path=path_name, config=config)
    elif os.path.isdir(path_name):
        index_files = find_entry_m3u8(path_name)
        if not index_files:
            print('no .m3u8 files found in', path_name)
            return
        print(f'found {len(index_files)} .m3u8 file(s)')
        tasks = [ConversionTask(entry=M3u8Entry(path=p)) for p in index_files]
        cancel = BatchCancelController.for_tasks(len(tasks))

        def on_started(index, task):
            print(f'[{index + 1}/{len(tasks)}] start', task.path)

        def on_done(index, task):
            print(f'[{index + 1}/{len(tasks)}] done', task.path)

        def on_error(index, task, exc):
            print(f'[{index + 1}/{len(tasks)}] fail', task.path, exc)

        done = run_batch_conversions(
            tasks,
            config,
            cancel=cancel,
            callbacks=BatchCallbacks(
                on_task_started=on_started,
                on_task_done=on_done,
                on_task_error=on_error,
            ),
        )
        print(f'finished {done}/{len(tasks)}')
    else:
        raise TypeError('not file nor dir')

if __name__ =='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('path', type=str)

    args = parser.parse_args()
    main(Path(args.path))
