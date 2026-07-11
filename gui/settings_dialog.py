"""设置对话框。"""
from __future__ import annotations

import tkinter as tk
from typing import Callable

import customtkinter as ctk
from tkinter import messagebox

from core.utils.config import GlobalConfig, save_local_config
from gui import theme as t

OUTPUT_DIR_NAME = '__DIR_NAME__'
OUTPUT_FIXED = 'output.mp4'

AES_IV_OPTIONS = {
    '自动检测（推荐）': 'auto',
    '分片前 16 字节（迅雷等）': 'prepended',
    '标准 HLS': 'hls',
}
AES_IV_LABELS = {value: label for label, value in AES_IV_OPTIONS.items()}


class SettingsDialog(tk.Toplevel):
    """使用 tk.Toplevel 而非 CTkToplevel，避免 Windows 下主窗口变透明。"""

    def __init__(self, master, global_config: GlobalConfig, on_saved: Callable[[], None] | None = None):
        super().__init__(master)
        self.global_config = global_config
        self.on_saved = on_saved

        self.title('转换设置')
        self.geometry('540x520')
        self.resizable(False, False)
        self.transient(master)
        self.configure(bg=t.frame_bg())
        self.protocol('WM_DELETE_WINDOW', self._close)

        self.container = t.style_card(ctk.CTkFrame(self))
        self.container.pack(fill='both', expand=True, padx=t.SPACE_LG, pady=t.SPACE_LG)

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
        header = ctk.CTkFrame(self.container, fg_color='transparent')
        header.pack(fill='x', padx=t.SPACE_LG, pady=(t.SPACE_LG, t.SPACE_SM))

        ctk.CTkLabel(header, text='转换设置', font=t.font_title()).pack(anchor='w')
        ctk.CTkLabel(
            header,
            text='以下设置保存后，下次转换时生效',
            font=t.font_caption(),
            text_color=t.MUTED,
        ).pack(anchor='w', pady=(2, 0))

        body = ctk.CTkScrollableFrame(self.container, fg_color='transparent')
        body.pack(fill='both', expand=True, padx=t.SPACE_LG, pady=t.SPACE_SM)

        self._add_section(body, '输出文件名')
        self.output_mode = tk.StringVar(value='dir_name')
        for text, value in (
            ('使用 m3u8 所在文件夹名（推荐）', 'dir_name'),
            ('固定为 output.mp4', 'fixed'),
            ('自定义文件名', 'custom'),
        ):
            ctk.CTkRadioButton(
                body,
                text=text,
                variable=self.output_mode,
                value=value,
                command=self._update_output_mode,
                font=t.font_body(),
            ).pack(anchor='w', pady=3)

        self.custom_name_entry = ctk.CTkEntry(
            body,
            placeholder_text='例如：my_video.mp4',
            height=32,
            font=t.font_body(),
        )
        self.custom_name_entry.pack(fill='x', pady=(t.SPACE_XS, 0))

        self._add_section(body, 'AES-128 分片 IV 模式')
        self.aes_iv_menu = ctk.CTkOptionMenu(
            body,
            values=list(AES_IV_OPTIONS.keys()),
            height=32,
            font=t.font_body(),
        )
        self.aes_iv_menu.pack(fill='x', pady=(t.SPACE_XS, 0))
        ctk.CTkLabel(
            body,
            text='加密视频转换失败时可尝试切换此选项',
            font=t.font_caption(),
            text_color=t.MUTED,
            anchor='w',
        ).pack(fill='x', pady=(t.SPACE_XS, 0))

        self._add_section(body, '分段处理')
        self.skip_first_part_var = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            body,
            text='跳过分段前第一段内容',
            variable=self.skip_first_part_var,
            font=t.font_body(),
        ).pack(anchor='w', pady=3)
        ctk.CTkLabel(
            body,
            text='仅在 m3u8 含 #EXT-X-DISCONTINUITY 时生效',
            font=t.font_caption(),
            text_color=t.MUTED,
            anchor='w',
        ).pack(fill='x')

        self.reset_decrypt_var = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            body,
            text='分段切换时重置解密器',
            variable=self.reset_decrypt_var,
            font=t.font_body(),
        ).pack(anchor='w', pady=(t.SPACE_SM, 3))

        footer = ctk.CTkFrame(self.container, fg_color='transparent')
        footer.pack(fill='x', padx=t.SPACE_LG, pady=(t.SPACE_SM, t.SPACE_LG))

        t.style_secondary_button(
            ctk.CTkButton(footer, text='取消', command=self._close),
            width=90,
        ).pack(side='right')

        t.style_primary_button(
            ctk.CTkButton(footer, text='保存', command=self._save),
            width=90,
        ).pack(side='right', padx=(0, t.SPACE_SM))

    def _add_section(self, parent, text: str) -> None:
        ctk.CTkFrame(parent, height=1, fg_color=t.SECONDARY).pack(fill='x', pady=(t.SPACE_LG, t.SPACE_SM))
        t.style_section_label(ctk.CTkLabel(parent, text=text), text).pack(fill='x', pady=(0, t.SPACE_SM))

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
