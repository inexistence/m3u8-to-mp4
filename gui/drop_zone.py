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
            border_width=1,
            corner_radius=t.RADIUS_MD,
            **kwargs,
        )
        self.on_paths_dropped = on_paths_dropped
        self._enabled = True
        self._compact = False

        self._content = ctk.CTkFrame(self, fg_color='transparent')
        self._content.pack(expand=True, fill='both', padx=t.SPACE_XL, pady=t.SPACE_XL)

        self.icon_label = ctk.CTkLabel(self._content, text='＋', font=t.font_icon(), text_color=t.MUTED)
        self.icon_label.pack(pady=(0, t.SPACE_SM))

        self.label = ctk.CTkLabel(
            self._content,
            text='拖放 .m3u8 文件或文件夹到此处',
            font=t.font_body(),
        )
        self.label.pack(pady=(0, t.SPACE_XS))

        self.hint = ctk.CTkLabel(
            self._content,
            text='支持同时拖入多个文件 / 文件夹，自动扫描入口索引',
            font=t.font_caption(),
            text_color=t.MUTED,
        )
        self.hint.pack(pady=(0, t.SPACE_MD))

        self.browse_file_btn = t.style_secondary_button(
            ctk.CTkButton(self._content, text='选择文件', command=self.browse_files),
            width=110,
        )
        self.browse_file_btn.pack(pady=(0, t.SPACE_XS))
        self.browse_dir_btn = t.style_secondary_button(
            ctk.CTkButton(self._content, text='选择文件夹', command=self.browse_directory),
            width=110,
        )
        self.browse_dir_btn.pack()

        self._register_dnd()

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled
        state = 'normal' if enabled else 'disabled'
        self.browse_file_btn.configure(state=state)
        self.browse_dir_btn.configure(state=state)
        self.configure(fg_color=t.DROP_BG if enabled else t.SECONDARY)
        self.icon_label.configure(text_color=t.MUTED)
        self.label.configure(text_color=('gray25', 'gray85') if enabled else t.MUTED)
        self.hint.configure(text_color=t.MUTED)

    def set_compact(self, compact: bool) -> None:
        """切换空队列与持续导入的紧凑提示，拖放目标始终保持可用。"""
        if self._compact == compact:
            return
        self._compact = compact
        if compact:
            self.configure(height=52)
            self._content.pack_forget()
            self._content.pack(fill='both', expand=True, padx=t.SPACE_MD, pady=t.SPACE_SM)
            self.icon_label.pack_forget()
            self.label.pack_forget()
            self.browse_file_btn.pack_forget()
            self.browse_dir_btn.pack_forget()
            self.label.configure(text='拖放 .m3u8 文件或文件夹到此处', font=t.font_caption())
            self.hint.pack_forget()
            self.browse_file_btn.configure(text='添加文件')
            self.browse_file_btn.pack(side='right')
            self.browse_dir_btn.configure(text='添加文件夹')
            self.browse_dir_btn.pack(side='right', padx=(0, t.SPACE_SM))
            self.label.pack(side='left', fill='x', expand=True, pady=0)
        else:
            self.configure(height=160)
            self._content.pack_forget()
            self._content.pack(expand=True, fill='both', padx=t.SPACE_XL, pady=t.SPACE_XL)
            self.label.pack_forget()
            self.browse_file_btn.pack_forget()
            self.browse_dir_btn.pack_forget()
            self.icon_label.pack(pady=(0, t.SPACE_SM))
            self.label.configure(text='拖放 .m3u8 文件或文件夹到此处', font=t.font_body())
            self.label.pack(pady=(0, t.SPACE_XS))
            self.hint.pack(pady=(0, t.SPACE_MD))
            self.browse_file_btn.configure(text='选择文件')
            self.browse_file_btn.pack(pady=(0, t.SPACE_XS))
            self.browse_dir_btn.configure(text='选择文件夹')
            self.browse_dir_btn.pack()

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

    def browse_files(self) -> None:
        file_paths = filedialog.askopenfilenames(
            title='选择 m3u8 文件',
            filetypes=[('M3U8 文件', '*.m3u8'), ('所有文件', '*.*')],
        )
        if file_paths:
            self.on_paths_dropped([Path(p) for p in file_paths])

    def browse_directory(self) -> None:
        dir_path = filedialog.askdirectory(title='选择文件夹')
        if dir_path:
            self.on_paths_dropped([Path(dir_path)])
