"""拖放区域。"""
from __future__ import annotations

from pathlib import Path
from tkinter import filedialog
from typing import Callable

import customtkinter as ctk
from tkinterdnd2 import DND_FILES


class DropZone(ctk.CTkFrame):
    def __init__(self, master, on_paths_dropped: Callable[[list[Path]], None], **kwargs):
        super().__init__(master, **kwargs)
        self.on_paths_dropped = on_paths_dropped

        self.label = ctk.CTkLabel(
            self,
            text='拖放 .m3u8 文件或文件夹到此处',
            font=ctk.CTkFont(size=15),
        )
        self.label.pack(expand=True, pady=(24, 8))

        self.hint = ctk.CTkLabel(
            self,
            text='支持同时拖入多个文件/文件夹',
            text_color='gray',
        )
        self.hint.pack(pady=(0, 8))

        btn_row = ctk.CTkFrame(self, fg_color='transparent')
        btn_row.pack(pady=(0, 24))

        self.browse_file_btn = ctk.CTkButton(btn_row, text='选择文件', width=100, command=self._browse_files)
        self.browse_file_btn.pack(side='left', padx=(0, 8))

        self.browse_dir_btn = ctk.CTkButton(btn_row, text='选择文件夹', width=100, command=self._browse_dir)
        self.browse_dir_btn.pack(side='left')

        self._register_dnd()

    def set_enabled(self, enabled: bool) -> None:
        state = 'normal' if enabled else 'disabled'
        self.browse_file_btn.configure(state=state)
        self.browse_dir_btn.configure(state=state)

    def _register_dnd(self) -> None:
        self.drop_target_register(DND_FILES)
        self.dnd_bind('<<Drop>>', self._on_drop)

    def _parse_drop_data(self, data: str) -> list[Path]:
        paths: list[Path] = []
        token = ''
        in_braces = False
        for char in data:
            if char == '{':
                in_braces = True
                token = ''
                continue
            if char == '}':
                in_braces = False
                if token:
                    paths.append(Path(token))
                token = ''
                continue
            if char == ' ' and not in_braces:
                if token:
                    paths.append(Path(token))
                    token = ''
                continue
            token += char
        if token:
            paths.append(Path(token))
        return paths

    def _on_drop(self, event) -> None:
        paths = self._parse_drop_data(event.data)
        if paths:
            self.on_paths_dropped(paths)

    def _browse_files(self) -> None:
        file_paths = filedialog.askopenfilenames(
            title='选择 m3u8 文件',
            filetypes=[('M3U8 文件', '*.m3u8'), ('所有文件', '*.*')],
        )
        if file_paths:
            self.on_paths_dropped([Path(p) for p in file_paths])

    def _browse_dir(self) -> None:
        dir_path = filedialog.askdirectory(title='选择文件夹')
        if dir_path:
            self.on_paths_dropped([Path(dir_path)])
