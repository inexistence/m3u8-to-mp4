from __future__ import annotations

from pydantic import BaseModel, Field


class ScanRequest(BaseModel):
    paths: list[str]
    known_paths: list[str] = Field(default_factory=list)


class EntryOut(BaseModel):
    task_id: str
    path: str
    is_master_playlist: bool
    stream_labels: list[str]
    selected_stream_index: int


class ScanResult(BaseModel):
    entries: list[EntryOut]
    added: int
    duplicates: int
    unparseable: int
    message: str


class ConvertTaskIn(BaseModel):
    task_id: str
    path: str
    is_master_playlist: bool = False
    selected_stream_index: int = 0


class ConvertRequest(BaseModel):
    tasks: list[ConvertTaskIn]


class ConfigUpdate(BaseModel):
    skip_first_part: bool | None = None
    output_file_name: str | None = None
    output_directory: str | None = None
    reset_decryption_if_part_changed: bool | None = None
    aes_iv_mode: str | None = None
    max_parallel_conversions: int | None = None
