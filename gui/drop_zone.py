"""拖放区域。"""
from __future__ import annotations

from pathlib import Path
from tkinter import filedialog
from typing import Callable

import customtkinter as ctk
from tkinterdnd2 import DND_FILES

from gui import theme as t


class DropZone(ctk.CTkFrame):
    def __init__(self, master, on_paths_dropped: Callable[[list[Path]], None], **kwargs):
        super().__init__(
            master,
            fg_color=t.DROP_BG,
            border_color=t.DROP_BORDER,
            border_width=2,
            corner_radius=t.RADIUS_LG,
            **kwargs,
        )
        self.on_paths_dropped = on_paths_dropped
        self._enabled = True

        inner = ctk.CTkFrame(self, fg_color='transparent')
        inner.pack(expand=True, fill='both', padx=t.SPACE_XL, pady=t.SPACE_XL)

        self.icon_label = ctk.CTkLabel(inner, text='⬇', font=t.font_icon(), text_color=t.ACCENT)
        self.icon_label.pack(pady=(0, t.SPACE_SM))

        self.label = ctk.CTkLabel(
            inner,
            text='拖放 .m3u8 文件或文件夹到此处',
            font=t.font_body(),
        )
        self.label.pack(pady=(0, t.SPACE_XS))

        self.hint = ctk.CTkLabel(
            inner,
            text='支持同时拖入多个文件 / 文件夹，自动扫描入口索引',
            font=t.font_caption(),
            text_color=t.MUTED,
        )
        self.hint.pack(pady=(0, t.SPACE_MD))

        btn_row = ctk.CTkFrame(inner, fg_color='transparent')
        btn_row.pack()

        self.browse_file_btn = t.style_secondary_button(
            ctk.CTkButton(btn_row, text='选择文件', command=self._browse_files),
            width=110,
        )
        self.browse_file_btn.pack(side='left', padx=(0, t.SPACE_SM))

        self.browse_dir_btn = t.style_secondary_button(
            ctk.CTkButton(btn_row, text='选择文件夹', command=self._browse_dir),
            width=110,
        )
        self.browse_dir_btn.pack(side='left')

        self._register_dnd()

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled
        state = 'normal' if enabled else 'disabled'
        self.browse_file_btn.configure(state=state)
        self.browse_dir_btn.configure(state=state)
        self.configure(fg_color=t.DROP_BG if enabled else t.SECONDARY)
        self.icon_label.configure(text_color=t.ACCENT if enabled else t.MUTED)
        self.label.configure(text_color=('#1e293b', '#e2e8f0') if enabled else t.MUTED)
        self.hint.configure(text_color=t.MUTED)

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
        if not self._enabled:
            return
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
