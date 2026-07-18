"""共享转换任务模型。"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from core.discovery import M3u8Entry


class TaskStatus(str, Enum):
    PENDING = 'pending'
    RUNNING = 'running'
    DONE = 'done'
    ERROR = 'error'
    SKIPPED = 'skipped'


@dataclass
class ConversionTask:
    entry: M3u8Entry
    selected: bool = True
    status: TaskStatus = TaskStatus.PENDING
    error_message: str = ''

    @property
    def path(self) -> Path:
        return self.entry.path

    @property
    def is_master_playlist(self) -> bool:
        return self.entry.is_master_playlist

    @property
    def stream_labels(self) -> list[str]:
        return self.entry.stream_labels

    @property
    def selected_stream_index(self) -> int:
        return self.entry.selected_stream_index

    @selected_stream_index.setter
    def selected_stream_index(self, value: int) -> None:
        self.entry.selected_stream_index = value
