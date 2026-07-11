"""设置对话框。"""
from __future__ import annotations

import tkinter as tk
from typing import Callable

import customtkinter as ctk
from tkinter import messagebox

from core.utils.config import GlobalConfig, save_local_config

OUTPUT_DIR_NAME = '__DIR_NAME__'
OUTPUT_FIXED = 'output.mp4'

AES_IV_OPTIONS = {
    '自动检测（推荐）': 'auto',
    '分片前 16 字节（迅雷等）': 'prepended',
    '标准 HLS': 'hls',
}
AES_IV_LABELS = {value: label for label, value in AES_IV_OPTIONS.items()}


def _dialog_bg_color() -> str:
    fg_color = ctk.ThemeManager.theme['CTkFrame']['fg_color']
    if isinstance(fg_color, (tuple, list)):
        return fg_color[1] if ctk.get_appearance_mode() == 'Dark' else fg_color[0]
    return fg_color


class SettingsDialog(tk.Toplevel):
    """使用 tk.Toplevel 而非 CTkToplevel，避免 Windows 下主窗口变透明。"""

    def __init__(self, master, global_config: GlobalConfig, on_saved: Callable[[], None] | None = None):
        super().__init__(master)
        self.global_config = global_config
        self.on_saved = on_saved

        self.title('转换设置')
        self.geometry('520x480')
        self.resizable(False, False)
        self.transient(master)
        self.configure(bg=_dialog_bg_color())
        self.protocol('WM_DELETE_WINDOW', self._close)

        self.container = ctk.CTkFrame(self)
        self.container.pack(fill='both', expand=True)

        self._build_ui()
        self._load_values()

        self.update_idletasks()
        self._center_on_master(master)
        self.lift(master)
        self.focus_force()
        self.wait_visibility()
        self.grab_set()

    def _center_on_master(self, master) -> None:
        master.update_idletasks()
        x = master.winfo_x() + (master.winfo_width() - self.winfo_width()) // 2
        y = master.winfo_y() + (master.winfo_height() - self.winfo_height()) // 2
        self.geometry(f'+{max(x, 0)}+{max(y, 0)}')

    def _close(self) -> None:
        try:
            self.grab_release()
        except tk.TclError:
            pass
        self.destroy()

    def _build_ui(self) -> None:
        body = ctk.CTkScrollableFrame(self.container)
        body.pack(fill='both', expand=True, padx=16, pady=(16, 8))

        self._add_section_title(body, '输出文件名')
        self.output_mode = tk.StringVar(value='dir_name')
        ctk.CTkRadioButton(
            body,
            text='使用 m3u8 所在文件夹名（推荐）',
            variable=self.output_mode,
            value='dir_name',
            command=self._update_output_mode,
        ).pack(anchor='w', pady=2)
        ctk.CTkRadioButton(
            body,
            text='固定为 output.mp4',
            variable=self.output_mode,
            value='fixed',
            command=self._update_output_mode,
        ).pack(anchor='w', pady=2)
        ctk.CTkRadioButton(
            body,
            text='自定义文件名',
            variable=self.output_mode,
            value='custom',
            command=self._update_output_mode,
        ).pack(anchor='w', pady=2)

        self.custom_name_entry = ctk.CTkEntry(body, placeholder_text='例如：my_video.mp4')
        self.custom_name_entry.pack(fill='x', pady=(4, 0))

        self._add_section_title(body, 'AES-128 分片 IV 模式', top=16)
        self.aes_iv_menu = ctk.CTkOptionMenu(body, values=list(AES_IV_OPTIONS.keys()))
        self.aes_iv_menu.pack(fill='x', pady=(4, 0))
        ctk.CTkLabel(
            body,
            text='加密视频转换失败时可尝试切换此选项',
            text_color='gray',
            anchor='w',
        ).pack(fill='x', pady=(4, 0))

        self._add_section_title(body, '分段处理', top=16)
        self.skip_first_part_var = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            body,
            text='跳过分段前第一段内容',
            variable=self.skip_first_part_var,
        ).pack(anchor='w', pady=2)
        ctk.CTkLabel(
            body,
            text='仅在 m3u8 含 #EXT-X-DISCONTINUITY 时生效',
            text_color='gray',
            anchor='w',
        ).pack(fill='x')

        self.reset_decrypt_var = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            body,
            text='分段切换时重置解密器',
            variable=self.reset_decrypt_var,
        ).pack(anchor='w', pady=(8, 2))

        footer = ctk.CTkFrame(self.container, fg_color='transparent')
        footer.pack(fill='x', padx=16, pady=(0, 16))

        ctk.CTkButton(footer, text='取消', width=90, fg_color='gray', command=self._close).pack(side='right')
        ctk.CTkButton(footer, text='保存', width=90, command=self._save).pack(side='right', padx=(0, 8))

    def _add_section_title(self, parent, text: str, top: int = 0) -> None:
        ctk.CTkLabel(
            parent,
            text=text,
            font=ctk.CTkFont(size=14, weight='bold'),
            anchor='w',
        ).pack(fill='x', pady=(top, 4))

    def _load_values(self) -> None:
        output_name = self.global_config.output_file_name
        if output_name == OUTPUT_DIR_NAME:
            self.output_mode.set('dir_name')
        elif output_name == OUTPUT_FIXED:
            self.output_mode.set('fixed')
        else:
            self.output_mode.set('custom')
            self.custom_name_entry.insert(0, output_name)

        self.aes_iv_menu.set(AES_IV_LABELS.get(self.global_config.aes_iv_mode, '自动检测（推荐）'))
        self.skip_first_part_var.set(self.global_config.skip_first_part)
        self.reset_decrypt_var.set(self.global_config.reset_decryption_if_part_changed)
        self._update_output_mode()

    def _update_output_mode(self) -> None:
        enabled = self.output_mode.get() == 'custom'
        self.custom_name_entry.configure(state='normal' if enabled else 'disabled')

    def _resolve_output_name(self) -> str | None:
        mode = self.output_mode.get()
        if mode == 'dir_name':
            return OUTPUT_DIR_NAME
        if mode == 'fixed':
            return OUTPUT_FIXED

        custom = self.custom_name_entry.get().strip()
        if not custom:
            messagebox.showwarning('提示', '请输入自定义文件名', parent=self)
            return None
        if not custom.endswith('.mp4'):
            custom += '.mp4'
        return custom

    def _save(self) -> None:
        output_name = self._resolve_output_name()
        if output_name is None:
            return

        aes_label = self.aes_iv_menu.get()
        aes_mode = AES_IV_OPTIONS.get(aes_label, 'auto')

        self.global_config.output_file_name = output_name
        self.global_config.aes_iv_mode = aes_mode
        self.global_config.skip_first_part = self.skip_first_part_var.get()
        self.global_config.reset_decryption_if_part_changed = self.reset_decrypt_var.get()

        try:
            save_local_config(self.global_config)
        except OSError as exc:
            messagebox.showerror('保存失败', f'无法写入配置文件：\n{exc}', parent=self)
            return

        if self.on_saved:
            self.on_saved()
        messagebox.showinfo('已保存', '设置已保存，下次转换时生效', parent=self)
        self._close()
