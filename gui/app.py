"""GUI 主窗口。"""
from __future__ import annotations

from pathlib import Path

import customtkinter as ctk
from tkinter import messagebox
from tkinterdnd2 import TkinterDnD

from core.discovery import M3u8Entry, find_entry_m3u8_from_paths
from core.utils.config import get_global_config
from gui.settings_dialog import SettingsDialog
from gui.drop_zone import DropZone
from gui.models import ConversionTask, TaskStatus
from gui.task_list import TaskList
from gui.worker import ConversionWorker, WorkerEvent


class M3u8GuiApp(TkinterDnD.Tk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode('System')
        ctk.set_default_color_theme('blue')

        self.title('m3u8 → mp4 转换工具')
        self.geometry('860x640')
        self.minsize(720, 520)

        self.global_config = get_global_config()
        self.tasks: list[ConversionTask] = []
        self.worker: ConversionWorker | None = None
        self.is_converting = False
        self._settings_dialog: SettingsDialog | None = None

        self._apply_root_background()
        self._build_ui()

    def _apply_root_background(self) -> None:
        fg_color = ctk.ThemeManager.theme['CTkFrame']['fg_color']
        if isinstance(fg_color, (tuple, list)):
            bg = fg_color[1] if ctk.get_appearance_mode() == 'Dark' else fg_color[0]
        else:
            bg = fg_color
        self.configure(bg=bg)

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header_row = ctk.CTkFrame(self, fg_color='transparent')
        header_row.grid(row=0, column=0, sticky='ew', padx=16, pady=(16, 8))
        header_row.grid_columnconfigure(0, weight=1)

        header = ctk.CTkLabel(
            header_row,
            text='m3u8 → mp4 转换工具',
            font=ctk.CTkFont(size=20, weight='bold'),
        )
        header.grid(row=0, column=0, sticky='w')

        self.settings_btn = ctk.CTkButton(
            header_row,
            text='设置',
            width=80,
            command=self.open_settings,
        )
        self.settings_btn.grid(row=0, column=1, sticky='e')

        body = ctk.CTkFrame(self)
        body.grid(row=1, column=0, sticky='nsew', padx=16, pady=8)
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(1, weight=1)

        self.drop_zone = DropZone(body, on_paths_dropped=self.add_paths, height=120)
        self.drop_zone.grid(row=0, column=0, sticky='ew', padx=8, pady=8)

        self.task_list = TaskList(body, on_selection_changed=self._update_convert_button)
        self.task_list.grid(row=1, column=0, sticky='nsew', padx=8, pady=8)

        footer = ctk.CTkFrame(self, fg_color='transparent')
        footer.grid(row=2, column=0, sticky='ew', padx=16, pady=(0, 16))
        footer.grid_columnconfigure(0, weight=1)

        self.progress_label = ctk.CTkLabel(footer, text='', text_color='gray')
        self.progress_label.grid(row=0, column=0, sticky='w', pady=(0, 4))

        self.progress = ctk.CTkProgressBar(footer)
        self.progress.grid(row=1, column=0, sticky='ew', pady=(0, 8))
        self.progress.set(0)

        actions = ctk.CTkFrame(footer, fg_color='transparent')
        actions.grid(row=2, column=0, sticky='ew', pady=(0, 8))
        actions.grid_columnconfigure(0, weight=1)

        self.convert_btn = ctk.CTkButton(actions, text='开始转换', width=140, command=self.start_conversion)
        self.convert_btn.pack(side='right')

        self.clear_btn = ctk.CTkButton(actions, text='清空列表', width=100, fg_color='gray', command=self.clear_tasks)
        self.clear_btn.pack(side='right', padx=(0, 8))

        self.log_box = ctk.CTkTextbox(footer, height=120)
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
        self.convert_btn.configure(state='disabled', text='转换中…')
        self.clear_btn.configure(state='disabled')
        self.settings_btn.configure(state='disabled')
        self.task_list.set_interactive(False)
        self.drop_zone.set_enabled(False)
        self.progress.set(0)
        self.progress_label.configure(text='准备开始…')

        self.worker = ConversionWorker(self.tasks, self.global_config, self._on_worker_event)
        self.worker.start()

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
        self.is_converting = False
        self.convert_btn.configure(state='normal', text='开始转换')
        self.clear_btn.configure(state='normal')
        self.settings_btn.configure(state='normal')
        self.task_list.set_interactive(True)
        self.drop_zone.set_enabled(True)
        self._update_convert_button()

        failed = sum(1 for task in self.tasks if task.status == TaskStatus.ERROR)
        if total_count == 0:
            self.progress_label.configure(text='')
            return

        self.progress.set(done_count / total_count if total_count else 1)
        summary = f'完成 {done_count}/{total_count}'
        if failed:
            summary += f'，{failed} 个失败'
        self.progress_label.configure(text=summary)
        self._append_log(summary)

        if failed:
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
