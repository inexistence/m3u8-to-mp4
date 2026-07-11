"""GUI 主窗口。"""
from __future__ import annotations

from pathlib import Path

import customtkinter as ctk
from tkinter import messagebox
from tkinterdnd2 import TkinterDnD

from core.discovery import M3u8Entry, find_entry_m3u8_from_paths
from core.utils.config import get_global_config
from core.utils.ffmpeg_check import find_ffmpeg, ffmpeg_missing_message
from gui import theme as t
from gui.settings_dialog import SettingsDialog
from gui.drop_zone import DropZone
from gui.models import ConversionTask, TaskStatus
from gui.task_list import TaskList
from gui.worker import ConversionWorker, WorkerEvent


class M3u8GuiApp(TkinterDnD.Tk):
    def __init__(self):
        super().__init__()
        t.init_theme()

        self.title('m3u8 → mp4')
        self.geometry('900x700')
        self.minsize(760, 560)

        self.global_config = get_global_config()
        self.tasks: list[ConversionTask] = []
        self.worker: ConversionWorker | None = None
        self.is_converting = False
        self._cancel_requested = False
        self._settings_dialog: SettingsDialog | None = None

        self._apply_root_background()
        self._build_ui()
        self.after(200, self._warn_if_ffmpeg_missing)

    def _warn_if_ffmpeg_missing(self) -> None:
        if find_ffmpeg() is None:
            messagebox.showwarning('缺少 FFmpeg', ffmpeg_missing_message(), parent=self)

    def _apply_root_background(self) -> None:
        self.configure(bg=t.frame_bg())

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._build_header()
        self._build_body()
        self._build_footer()

    def _build_header(self) -> None:
        header = ctk.CTkFrame(self, fg_color='transparent')
        header.grid(row=0, column=0, sticky='ew', padx=t.SPACE_LG, pady=(t.SPACE_LG, t.SPACE_SM))
        header.grid_columnconfigure(1, weight=1)

        accent_bar = ctk.CTkFrame(header, width=4, height=40, corner_radius=2, fg_color=t.ACCENT)
        accent_bar.grid(row=0, column=0, rowspan=2, sticky='ns', padx=(0, t.SPACE_MD))

        title_block = ctk.CTkFrame(header, fg_color='transparent')
        title_block.grid(row=0, column=1, sticky='w')

        ctk.CTkLabel(
            title_block,
            text='m3u8 → mp4',
            font=t.font_title(),
        ).pack(anchor='w')

        ctk.CTkLabel(
            title_block,
            text='本地 HLS 分片合并为 MP4',
            font=t.font_subtitle(),
            text_color=t.MUTED,
        ).pack(anchor='w', pady=(2, 0))

        self.settings_btn = t.style_secondary_button(
            ctk.CTkButton(header, text='⚙  设置', command=self.open_settings),
            width=96,
        )
        self.settings_btn.grid(row=0, column=2, rowspan=2, sticky='e')

    def _build_body(self) -> None:
        body = ctk.CTkFrame(self, fg_color='transparent')
        body.grid(row=1, column=0, sticky='nsew', padx=t.SPACE_LG, pady=t.SPACE_SM)
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(2, weight=1)

        t.style_section_label(
            ctk.CTkLabel(body, text='导入'),
            '导入',
        ).grid(row=0, column=0, sticky='w', pady=(0, t.SPACE_SM))

        self.drop_zone = DropZone(body, on_paths_dropped=self.add_paths, height=140)
        self.drop_zone.grid(row=1, column=0, sticky='ew', pady=(0, t.SPACE_LG))

        queue_header = ctk.CTkFrame(body, fg_color='transparent')
        queue_header.grid(row=2, column=0, sticky='new', pady=(0, t.SPACE_SM))
        queue_header.grid_columnconfigure(0, weight=1)

        t.style_section_label(
            ctk.CTkLabel(queue_header, text='任务队列'),
            '任务队列',
        ).grid(row=0, column=0, sticky='w')

        queue_card = t.style_card(ctk.CTkFrame(body))
        queue_card.grid(row=3, column=0, sticky='nsew')
        queue_card.grid_columnconfigure(0, weight=1)
        queue_card.grid_rowconfigure(0, weight=1)
        body.grid_rowconfigure(3, weight=1)

        self.task_list = TaskList(queue_card, on_selection_changed=self._update_convert_button)
        self.task_list.grid(row=0, column=0, sticky='nsew', padx=t.SPACE_MD, pady=t.SPACE_MD)

    def _build_footer(self) -> None:
        footer = ctk.CTkFrame(self, fg_color='transparent')
        footer.grid(row=2, column=0, sticky='ew', padx=t.SPACE_LG, pady=(t.SPACE_SM, t.SPACE_LG))
        footer.grid_columnconfigure(0, weight=1)

        progress_row = ctk.CTkFrame(footer, fg_color='transparent')
        progress_row.grid(row=0, column=0, sticky='ew', pady=(0, t.SPACE_SM))
        progress_row.grid_columnconfigure(0, weight=1)

        self.progress_label = ctk.CTkLabel(
            progress_row,
            text='',
            font=t.font_caption(),
            text_color=t.MUTED,
            anchor='w',
        )
        self.progress_label.grid(row=0, column=0, sticky='w', pady=(0, t.SPACE_XS))

        self.progress = ctk.CTkProgressBar(progress_row, height=8, corner_radius=4)
        self.progress.grid(row=1, column=0, sticky='ew')
        self.progress.set(0)

        actions = ctk.CTkFrame(footer, fg_color='transparent')
        actions.grid(row=1, column=0, sticky='ew', pady=(t.SPACE_MD, t.SPACE_MD))
        actions.grid_columnconfigure(0, weight=1)

        self.convert_btn = t.style_primary_button(
            ctk.CTkButton(actions, text='开始转换', command=self.start_conversion),
            width=140,
        )
        self.convert_btn.pack(side='right')

        self.cancel_btn = t.style_danger_button(
            ctk.CTkButton(actions, text='取消', command=self.cancel_conversion, state='disabled'),
            width=100,
        )
        self.cancel_btn.pack(side='right', padx=(0, t.SPACE_SM))

        self.clear_btn = t.style_secondary_button(
            ctk.CTkButton(actions, text='清空列表', command=self.clear_tasks),
            width=100,
        )
        self.clear_btn.pack(side='right', padx=(0, t.SPACE_SM))

        log_header = ctk.CTkFrame(footer, fg_color='transparent')
        log_header.grid(row=2, column=0, sticky='ew', pady=(0, t.SPACE_XS))

        t.style_section_label(
            ctk.CTkLabel(log_header, text='运行日志'),
            '运行日志',
        ).pack(side='left')

        self.log_box = ctk.CTkTextbox(
            footer,
            height=110,
            font=t.font_mono(),
            fg_color=t.LOG_BG,
            text_color=t.LOG_FG,
            corner_radius=t.RADIUS_SM,
        )
        self.log_box.grid(row=3, column=0, sticky='ew')
        self.log_box.configure(state='disabled')

    def open_settings(self) -> None:
        if self.is_converting:
            messagebox.showwarning('提示', '转换进行中，请等待完成后再修改设置')
            return
        self.global_config.reload_from_disk()
        if self._settings_dialog is not None and self._settings_dialog.winfo_exists():
            self._settings_dialog.lift(self)
            self._settings_dialog.focus_force()
            return
        self._settings_dialog = SettingsDialog(
            self,
            self.global_config,
            on_saved=lambda: self._append_log('设置已更新'),
        )

    def add_paths(self, paths: list[Path]) -> None:
        if self.is_converting:
            messagebox.showwarning('提示', '转换进行中，请等待完成后再添加文件')
            return

        entries = find_entry_m3u8_from_paths(paths)
        if not entries:
            messagebox.showinfo('未找到文件', '没有找到可用的 .m3u8 入口文件')
            return

        existing = {task.path.resolve() for task in self.tasks}
        added = 0
        for entry_path in entries:
            if entry_path in existing:
                continue
            entry = M3u8Entry.from_path(entry_path)
            self.tasks.append(ConversionTask(entry=entry))
            existing.add(entry_path)
            added += 1

        self.tasks.sort(key=lambda task: str(task.path).lower())
        self.task_list.set_tasks(self.tasks)
        self._append_log(f'扫描完成，新增 {added} 个文件，共 {len(self.tasks)} 个')

    def clear_tasks(self) -> None:
        if self.is_converting:
            return
        self.tasks.clear()
        self.task_list.set_tasks(self.tasks)
        self.progress.set(0)
        self.progress_label.configure(text='')
        self._append_log('已清空任务列表')

    def _update_convert_button(self) -> None:
        selected = any(task.selected for task in self.tasks)
        if not self.is_converting:
            self.convert_btn.configure(state='normal' if selected else 'disabled')

    def start_conversion(self) -> None:
        if self.is_converting:
            return
        if find_ffmpeg() is None:
            messagebox.showerror('缺少 FFmpeg', ffmpeg_missing_message(), parent=self)
            return
        selected_tasks = [task for task in self.tasks if task.selected]
        if not selected_tasks:
            messagebox.showinfo('提示', '请至少选择一个文件')
            return

        for task in self.tasks:
            if task.selected:
                task.status = TaskStatus.PENDING
                task.error_message = ''
        self.task_list.refresh_rows()

        self.global_config.reload_from_disk()
        self._append_log(f'输出文件名配置: {self.global_config.output_file_name}')

        self.is_converting = True
        self._cancel_requested = False
        self.convert_btn.configure(state='disabled', text='转换中…')
        self.cancel_btn.configure(state='normal')
        self.clear_btn.configure(state='disabled')
        self.settings_btn.configure(state='disabled')
        self.task_list.set_interactive(False)
        self.drop_zone.set_enabled(False)
        self.progress.set(0)
        self.progress_label.configure(text='准备开始…')

        self.worker = ConversionWorker(self.tasks, self.global_config, self._on_worker_event)
        self.worker.start()

    def cancel_conversion(self) -> None:
        if not self.is_converting or self.worker is None:
            return
        self._cancel_requested = True
        self.worker.cancel()
        self.cancel_btn.configure(state='disabled')
        self._append_log('正在取消…（当前任务完成后停止）')

    def _on_worker_event(self, event: WorkerEvent) -> None:
        self.after(0, lambda: self._handle_worker_event(event))

    def _handle_worker_event(self, event: WorkerEvent) -> None:
        if event.kind == 'log':
            self._append_log(event.message)
            return

        if event.kind == 'started':
            self.progress_label.configure(text=f'共 {event.total_count} 个任务')
            return

        if event.kind == 'task_started':
            self.progress_label.configure(text=f'正在转换 ({event.done_count + 1}/{event.total_count}): {event.message}')
            self.task_list.refresh_rows()
            return

        if event.kind == 'task_done':
            if event.total_count:
                self.progress.set(event.done_count / event.total_count)
            self._append_log(event.message)
            self.task_list.refresh_rows()
            return

        if event.kind == 'task_error':
            self._append_log(event.message)
            self.task_list.refresh_rows()
            return

        if event.kind == 'error':
            messagebox.showerror('错误', event.message)
            return

        if event.kind == 'finished':
            self._finish_conversion(event.done_count, event.total_count)

    def _finish_conversion(self, done_count: int, total_count: int) -> None:
        was_cancelled = self._cancel_requested
        self.is_converting = False
        self._cancel_requested = False
        self.convert_btn.configure(state='normal', text='开始转换')
        self.cancel_btn.configure(state='disabled')
        self.clear_btn.configure(state='normal')
        self.settings_btn.configure(state='normal')
        self.task_list.set_interactive(True)
        self.drop_zone.set_enabled(True)
        self._update_convert_button()
        self.task_list.refresh_rows()

        failed = sum(1 for task in self.tasks if task.status == TaskStatus.ERROR)
        skipped = sum(1 for task in self.tasks if task.status == TaskStatus.SKIPPED)
        if total_count == 0:
            self.progress_label.configure(text='')
            return

        self.progress.set(done_count / total_count if total_count else 1)
        summary = f'完成 {done_count}/{total_count}'
        if skipped:
            summary += f'，{skipped} 个已跳过'
        if failed:
            summary += f'，{failed} 个失败'
        self.progress_label.configure(text=summary)
        self._append_log(summary)

        if was_cancelled:
            messagebox.showinfo('已取消', summary)
        elif failed:
            messagebox.showwarning('转换完成', summary)
        else:
            messagebox.showinfo('转换完成', summary)

    def _append_log(self, message: str) -> None:
        self.log_box.configure(state='normal')
        self.log_box.insert('end', message + '\n')
        self.log_box.see('end')
        self.log_box.configure(state='disabled')


def run_app() -> None:
    app = M3u8GuiApp()
    app.mainloop()
