"""GUI 主窗口。"""
from __future__ import annotations

import os
from pathlib import Path

import customtkinter as ctk
from tkinter import TclError, filedialog, messagebox
from tkinterdnd2 import TkinterDnD

from core.discovery import M3u8Entry, find_entry_m3u8_from_paths
from core.utils.config import get_global_config, save_local_config
from core.utils.ffmpeg_check import find_ffmpeg, ffmpeg_missing_message, describe_ffmpeg_status
from gui import theme as t
from gui.settings_dialog import SettingsDialog
from gui.models import ConversionTask, TaskStatus
from gui.task_list import (
    QueueFeedback,
    TaskList,
    batch_feedback,
    conversion_feedback,
    scan_feedback,
    should_clear_feedback,
)
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
        self._active_batch: tuple[ConversionTask, ...] = ()
        self.worker: ConversionWorker | None = None
        self.is_converting = False
        self._cancel_requested = False
        self._settings_dialog: SettingsDialog | None = None
        self._appearance_mode = ctk.get_appearance_mode()
        self._appearance_check_job: str | None = None
        self._queue_feedback_clear_job: str | None = None
        self._queue_feedback = QueueFeedback()
        self._is_destroying = False

        self._apply_root_background()
        self._register_appearance_callback()
        self._build_ui()
        self._schedule_appearance_check()
        self.after(200, self._warn_if_ffmpeg_missing)

    def _warn_if_ffmpeg_missing(self) -> None:
        self._refresh_ffmpeg_status()
        if find_ffmpeg() is None:
            messagebox.showwarning('缺少 FFmpeg', ffmpeg_missing_message(), parent=self)

    def _apply_root_background(self) -> None:
        self.configure(bg=t.frame_bg())

    def _register_appearance_callback(self) -> None:
        """在 CustomTkinter 支持时同步原生 Tk 根窗口的背景色。"""
        register_callback = getattr(ctk, 'set_appearance_mode_callback', None)
        if callable(register_callback):
            register_callback(self._on_appearance_mode_changed)

    def _on_appearance_mode_changed(self, *_args) -> None:
        if not self._is_destroying:
            try:
                self._appearance_mode = ctk.get_appearance_mode()
                self._apply_root_background()
            except TclError:
                self._is_destroying = True

    def _schedule_appearance_check(self) -> None:
        if not self._is_destroying and self._appearance_check_job is None:
            self._appearance_check_job = self.after(250, self._check_appearance_mode)

    def _check_appearance_mode(self) -> None:
        self._appearance_check_job = None
        if self._is_destroying:
            return
        try:
            mode = ctk.get_appearance_mode()
            if mode != self._appearance_mode:
                self._appearance_mode = mode
                self._apply_root_background()
        except TclError:
            self._is_destroying = True
        else:
            self._schedule_appearance_check()

    def destroy(self) -> None:
        self._is_destroying = True
        if self._appearance_check_job is not None:
            try:
                self.after_cancel(self._appearance_check_job)
            except Exception:
                pass
            self._appearance_check_job = None
        if self._queue_feedback_clear_job is not None:
            try:
                self.after_cancel(self._queue_feedback_clear_job)
            except Exception:
                pass
            self._queue_feedback_clear_job = None
        super().destroy()

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._build_header()
        self._build_workspace()

    def _build_header(self) -> None:
        header = t.style_card(ctk.CTkFrame(self))
        header.grid(row=0, column=0, sticky='ew', padx=t.SPACE_LG, pady=(t.SPACE_LG, t.SPACE_SM))
        header.grid_columnconfigure(0, weight=1)

        title_block = ctk.CTkFrame(header, fg_color='transparent')
        title_block.grid(row=0, column=0, sticky='w', padx=t.SPACE_MD, pady=t.SPACE_MD)

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

        self.ffmpeg_status = ctk.CTkLabel(
            header,
            font=t.font_caption(),
            corner_radius=t.RADIUS_SM,
            height=28,
            padx=t.SPACE_SM,
        )
        self.ffmpeg_status.grid(row=0, column=1, sticky='e', padx=(t.SPACE_MD, t.SPACE_SM))
        self._refresh_ffmpeg_status()

        self.settings_btn = t.style_secondary_button(
            ctk.CTkButton(header, text='设置', command=self.open_settings),
            width=80,
        )
        self.settings_btn.grid(row=0, column=2, sticky='e', padx=t.SPACE_MD, pady=t.SPACE_MD)

    def _refresh_ffmpeg_status(self) -> None:
        available, label = describe_ffmpeg_status()
        self.ffmpeg_status.configure(
            text=label,
            fg_color=t.ACCENT_MUTED if available else t.STATUS_META['error']['background'],
            text_color=t.ACCENT if available else t.ERROR,
        )

    def _build_workspace(self) -> None:
        workspace = ctk.CTkFrame(self, fg_color='transparent')
        workspace.grid(row=1, column=0, sticky='nsew', padx=t.SPACE_LG, pady=t.SPACE_SM)
        workspace.grid_columnconfigure(0, weight=1)
        workspace.grid_rowconfigure(0, weight=1)

        queue_card = t.style_card(ctk.CTkFrame(workspace))
        queue_card.grid(row=0, column=0, sticky='nsew')
        queue_card.grid_columnconfigure(0, weight=1)
        queue_card.grid_rowconfigure(0, weight=1)

        self.task_list = TaskList(
            queue_card,
            on_selection_changed=self._update_convert_button,
            output_directory=self.global_config.output_directory,
            on_output_directory_changed=self._set_output_directory,
            on_choose_output_directory=self._choose_output_directory,
            on_open_output_directory=self._open_output_directory,
            on_paths_dropped=self.add_paths,
            on_clear_tasks=self.clear_tasks,
            on_start_conversion=self.start_conversion,
            on_cancel_conversion=self.cancel_conversion,
            on_cancel_task=self._cancel_task,
            on_copy_error=self._copy_error_details,
        )
        self.task_list.grid(row=0, column=0, sticky='nsew', padx=t.SPACE_MD, pady=t.SPACE_MD)

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
            on_saved=self._on_settings_saved,
        )

    def _on_settings_saved(self) -> None:
        self.task_list.set_output_directory(self.global_config.output_directory)
        self.task_list.set_tasks(self.tasks)
        self._set_queue_feedback('')

    def _set_output_directory(self, output_directory: str | None) -> None:
        if self.is_converting:
            return
        previous_directory = self.global_config.output_directory
        self.global_config.output_directory = output_directory
        try:
            save_local_config(self.global_config)
        except OSError as exc:
            self.global_config.output_directory = previous_directory
            messagebox.showerror('保存失败', f'无法写入配置文件：\n{exc}', parent=self)
        finally:
            self.task_list.set_output_directory(self.global_config.output_directory)

    def _choose_output_directory(self) -> None:
        if self.is_converting:
            return
        directory = filedialog.askdirectory(
            title='选择 MP4 输出目录',
            initialdir=self.global_config.output_directory or None,
            parent=self,
        )
        if not directory:
            return
        self._set_output_directory(directory)

    def _open_output_directory(self) -> None:
        output_directory = self.global_config.output_directory
        if not output_directory:
            return
        path = Path(output_directory)
        if not path.is_dir():
            messagebox.showwarning('无法打开目录', f'输出目录不存在：\n{path}', parent=self)
            return
        try:
            os.startfile(str(path.resolve()))
        except OSError as exc:
            messagebox.showerror('无法打开目录', f'无法打开输出目录：\n{exc}', parent=self)

    def _set_queue_feedback(
        self,
        message: str,
        tone: str = 'muted',
        *,
        persistent: bool = False,
        clear_after_ms: int | None = None,
    ) -> None:
        """替换工具栏反馈；短暂扫描结果不会覆盖后续转换或失败状态。"""
        if self._queue_feedback_clear_job is not None:
            self.after_cancel(self._queue_feedback_clear_job)
            self._queue_feedback_clear_job = None
        feedback = QueueFeedback(message, tone, persistent)
        self._queue_feedback = feedback
        self.task_list.set_queue_feedback(feedback)
        if message and clear_after_ms is not None and not persistent:
            self._queue_feedback_clear_job = self.after(
                clear_after_ms,
                lambda: self._clear_queue_feedback_if_current(feedback),
            )

    def _clear_queue_feedback_if_current(self, scheduled: QueueFeedback) -> None:
        self._queue_feedback_clear_job = None
        if should_clear_feedback(self._queue_feedback, scheduled):
            self._set_queue_feedback('')

    def add_paths(self, paths: list[Path]) -> None:
        try:
            entries = find_entry_m3u8_from_paths(paths)
        except (OSError, ValueError) as exc:
            self._set_queue_feedback(f'导入失败：{exc}', 'error', persistent=True)
            return
        if not entries:
            self._set_queue_feedback(
                '扫描完成：添加 0，重复 0，无法解析 0；未找到可用的 .m3u8 入口文件',
                'warning',
                clear_after_ms=4000,
            )
            return

        existing = {task.path.resolve() for task in self.tasks}
        added = 0
        duplicates = 0
        unparseable = 0
        for entry_path in entries:
            if entry_path in existing:
                duplicates += 1
                continue
            try:
                entry = M3u8Entry.from_path(entry_path)
            except Exception:
                unparseable += 1
                continue
            self.tasks.append(ConversionTask(entry=entry))
            existing.add(entry_path)
            added += 1

        self.tasks.sort(key=lambda task: str(task.path).lower())
        self.task_list.set_tasks(self.tasks)
        if self.is_converting:
            self.task_list.select_all_cb.configure(state='disabled')
            self.task_list.set_clear_enabled(False)
            self.task_list.set_output_controls_enabled(False)
            self._set_batch_rows_interactive(False)
        feedback = scan_feedback(added, duplicates, unparseable, len(self.tasks))
        if self.is_converting and added:
            feedback += '；新增任务将在下一批转换'
        self._set_queue_feedback(
            feedback,
            'success' if added else 'warning',
            clear_after_ms=4000,
        )

    def clear_tasks(self) -> None:
        if self.is_converting:
            return
        self.tasks.clear()
        self.task_list.set_tasks(self.tasks)
        self._set_queue_feedback('')

    def _update_convert_button(self) -> None:
        self.task_list.update_action_state()

    def _sync_queue_actions(self) -> None:
        self.task_list.set_converting(self.is_converting)

    def _set_batch_rows_interactive(self, enabled: bool) -> None:
        batch_tasks = set(map(id, self._active_batch))
        for row in self.task_list.rows:
            if id(row.task) in batch_tasks:
                row.set_enabled(enabled)

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
            if task in selected_tasks:
                task.status = TaskStatus.PENDING
                task.error_message = ''
        self.task_list.refresh_rows()
        self._active_batch = tuple(selected_tasks)
        self.task_list.set_cancellable_tasks(self._active_batch)

        self.global_config.reload_from_disk()
        self.task_list.set_output_directory(self.global_config.output_directory)
        self.task_list.set_tasks(self.tasks)

        self.is_converting = True
        self._cancel_requested = False
        self._set_queue_feedback(conversion_feedback(0, len(self._active_batch)), 'accent')
        self._sync_queue_actions()
        self.task_list.set_clear_enabled(False)
        self.task_list.set_output_controls_enabled(False)
        self.settings_btn.configure(state='disabled')
        self.task_list.set_interactive(False)
        self._set_batch_rows_interactive(False)

        self.worker = ConversionWorker(self._active_batch, self.global_config, self._on_worker_event)
        self.worker.start()

    def cancel_conversion(self) -> None:
        if not self.is_converting or self.worker is None:
            return
        self._cancel_requested = True
        self.worker.cancel()
        self.task_list.cancel_btn.configure(state='disabled', text='正在取消…')

    def _cancel_task(self, task: ConversionTask) -> None:
        if not self.is_converting or self.worker is None:
            return
        try:
            index = self._active_batch.index(task)
        except ValueError:
            return
        self.worker.cancel_task(index)

    def _on_worker_event(self, event: WorkerEvent) -> None:
        self.after(0, lambda: self._handle_worker_event(event))

    def _handle_worker_event(self, event: WorkerEvent) -> None:
        if event.kind == 'log':
            return

        if event.kind == 'started':
            self._set_queue_feedback(conversion_feedback(0, event.total_count), 'accent')
            return

        if event.kind == 'task_started':
            self._set_queue_feedback(
                conversion_feedback(event.done_count, event.total_count),
                'accent',
            )
            self.task_list.refresh_rows()
            return

        if event.kind == 'task_progress':
            if 0 <= event.task_index < len(self._active_batch):
                active_task = self._active_batch[event.task_index]
                row_index = next(
                    index for index, task in enumerate(self.tasks)
                    if task is active_task
                )
                self.task_list.set_task_progress(
                    row_index,
                    event.progress_phase,
                    event.message,
                    event.progress_percent,
                )
            return

        if event.kind == 'task_done':
            self.task_list.refresh_rows()
            return

        if event.kind == 'task_error':
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
        self.task_list.cancel_btn.configure(state='normal', text='取消全部')
        self.task_list.set_cancellable_tasks(())
        self._sync_queue_actions()
        self.task_list.set_clear_enabled(True)
        self.settings_btn.configure(state='normal')
        self.task_list.set_interactive(True)
        self._update_convert_button()
        self.task_list.refresh_rows()

        failed_tasks = [task for task in self._active_batch if task.status == TaskStatus.ERROR]
        completed_tasks = [task for task in self._active_batch if task.status == TaskStatus.DONE]
        cancelled_tasks = [task for task in self._active_batch if task.status == TaskStatus.SKIPPED]
        failed = len(failed_tasks)
        skipped = len(cancelled_tasks)
        summary = f'完成 {done_count}/{total_count}'
        if skipped:
            summary += f'，{skipped} 个已跳过'
        if failed:
            summary += f'，{failed} 个失败'
        self._set_queue_feedback(
            batch_feedback(len(completed_tasks), failed, skipped),
            'warning' if failed or skipped else 'success',
            persistent=bool(failed),
        )

        if was_cancelled:
            messagebox.showinfo('已取消', summary)
        elif failed:
            messagebox.showwarning('转换完成', summary)
        else:
            messagebox.showinfo('转换完成', summary)

    def _error_details(self, task: ConversionTask) -> str:
        return (
            f'任务：{task.path.name}\n'
            f'路径：{task.path}\n'
            f'错误详情：{task.error_message or "未提供错误详情"}'
        )

    def _copy_error_details(self, task: ConversionTask) -> None:
        self._copy_text(self._error_details(task))

    def _copy_text(self, text: str) -> bool:
        try:
            self.clipboard_clear()
            self.clipboard_append(text)
            self.update_idletasks()
            return True
        except TclError:
            messagebox.showwarning('无法复制', '当前系统剪贴板不可用', parent=self)
            return False

def run_app() -> None:
    app = M3u8GuiApp()
    app.mainloop()
