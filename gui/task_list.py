"""任务列表：勾选与码率选择。"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import customtkinter as ctk
from tkinterdnd2 import DND_FILES

from gui import theme as t
from gui.drop_zone import DropZone
from gui.models import ConversionTask, TaskStatus


STATUS_LABELS = {
    TaskStatus.PENDING: '',
    TaskStatus.RUNNING: '转换中',
    TaskStatus.DONE: '完成',
    TaskStatus.ERROR: '失败',
    TaskStatus.SKIPPED: '已跳过',
}


def format_output_destination(output_directory: str | None) -> tuple[str, str]:
    """返回输出栏的模式标签与可展示路径。"""
    if output_directory is None or not output_directory.strip():
        return '源目录', '与每个 m3u8 所在目录相同'
    return '指定目录', f'{Path(output_directory).name} ↗'


def output_destination_detail(output_directory: str | None) -> str:
    """返回输出栏单行显示内容，链接名与路径绝不拆成两行。"""
    _, destination = format_output_destination(output_directory)
    if output_directory is None or not output_directory.strip():
        return destination
    return f'{destination} · {output_directory}'


def completed_task_summary() -> str:
    """返回已完成任务的最终阶段摘要。"""
    return '合片完成 · FFmpeg 封装完成'


def scan_feedback(added: int, duplicates: int, unparseable: int, total: int) -> str:
    """返回单行扫描结果，供工具栏内的提示区替换显示。"""
    return f'扫描完成：添加 {added}，重复 {duplicates}，无法解析 {unparseable}；共 {total} 个任务'


def conversion_feedback(done_count: int, total_count: int) -> str:
    """返回当前批次的单行转换状态。"""
    current = min(done_count + 1, total_count)
    return f'转换中：正在处理第 {current}/{total_count} 个任务'


def batch_feedback(success: int, failed: int, cancelled: int) -> str:
    """返回单行批次结果；失败时引导用户查看对应任务详情。"""
    message = f'本批完成：成功 {success}，失败 {failed}，取消 {cancelled}'
    if failed:
        return f'{message}；点击失败任务可查看详情'
    return message


def _short_path(path: Path) -> tuple[str, str]:
    """返回 (文件名, 目录路径)。"""
    directory = str(path.parent)
    if len(directory) > 72:
        directory = f'{directory[:34]}…{directory[-34:]}'
    return path.name, directory


@dataclass(frozen=True)
class QueueActionState:
    select_all_enabled: bool
    clear_enabled: bool
    start_enabled: bool
    cancel_visible: bool


@dataclass(frozen=True)
class QueueFeedback:
    """工具栏内反馈的可测试状态。"""
    message: str = ''
    tone: str = 'muted'
    persistent: bool = False


def should_clear_feedback(current: QueueFeedback, scheduled: QueueFeedback) -> bool:
    """仅清除仍为原短暂提示的反馈，避免延时任务覆盖新状态。"""
    return current == scheduled and bool(current.message) and not current.persistent


@dataclass(frozen=True)
class QueueContentLayout:
    drop_zone_height: int
    propagate: bool
    show_empty_state: bool
    show_task_rows: bool
    scrollable: bool


def queue_content_layout(task_count: int) -> QueueContentLayout:
    """计算独立添加入口与列表区的可测试布局状态。"""
    has_tasks = task_count > 0
    return QueueContentLayout(
        drop_zone_height=52,
        propagate=has_tasks,
        show_empty_state=not has_tasks,
        show_task_rows=has_tasks,
        scrollable=task_count > 1,
    )


def queue_action_state(task_count: int, selected_count: int, is_converting: bool) -> QueueActionState:
    """基于队列与选择状态计算可用操作，避免空队列出现可执行的假状态。"""
    has_tasks = task_count > 0
    return QueueActionState(
        select_all_enabled=has_tasks and not is_converting,
        clear_enabled=has_tasks and not is_converting,
        start_enabled=has_tasks and selected_count > 0 and not is_converting,
        cancel_visible=is_converting,
    )


class TaskRow(ctk.CTkFrame):
    def __init__(
        self,
        master,
        task: ConversionTask,
        on_selection_changed: Callable[[], None],
        on_stream_changed: Callable[[], None],
        on_copy_error: Callable[[ConversionTask], None] | None,
        on_view_error_log: Callable[[ConversionTask], None] | None = None,
        **kwargs,
    ):
        super().__init__(master, corner_radius=t.RADIUS_SM, border_width=1, **kwargs)
        self.task = task
        self.on_selection_changed = on_selection_changed
        self.on_stream_changed = on_stream_changed
        self.on_copy_error = on_copy_error

        self.grid_columnconfigure(1, weight=1)

        self.checkbox = ctk.CTkCheckBox(
            self,
            text='',
            width=24,
            command=self._on_checkbox,
        )
        self.checkbox.grid(row=0, column=0, rowspan=2, padx=(t.SPACE_MD, t.SPACE_XS), pady=t.SPACE_MD, sticky='n')
        if task.selected:
            self.checkbox.select()

        name, directory = _short_path(task.path)
        self.name_label = ctk.CTkLabel(
            self,
            text=name,
            font=t.font_body(),
            anchor='w',
        )
        self.name_label.grid(row=0, column=1, sticky='ew', padx=t.SPACE_XS, pady=(t.SPACE_MD, 0))

        self.path_label = ctk.CTkLabel(
            self,
            text=directory,
            font=t.font_caption(),
            text_color=t.MUTED,
            anchor='w',
        )
        self.path_label.grid(row=1, column=1, sticky='ew', padx=t.SPACE_XS, pady=(0, t.SPACE_MD))
        self.path_label.bind('<Button-1>', self._copy_path)
        self.path_label.configure(cursor='hand2')

        self.progress_frame = ctk.CTkFrame(self, fg_color='transparent')
        self.progress_frame.grid_columnconfigure(1, weight=1)
        self.progress_label = ctk.CTkLabel(
            self.progress_frame, text='等待开始', font=t.font_caption(), text_color=t.MUTED, width=180, anchor='w',
        )
        self.progress_label.grid(row=0, column=0, sticky='w')
        self.progress = ctk.CTkProgressBar(self.progress_frame, height=8, progress_color=t.ACCENT)
        self.progress.set(0)
        self.progress.grid(row=0, column=1, sticky='ew', padx=(t.SPACE_SM, 0))
        self.progress_frame.grid(row=2, column=1, sticky='ew', padx=t.SPACE_XS, pady=(0, t.SPACE_SM))
        self.progress_frame.grid_remove()

        self.status_badge = ctk.CTkLabel(
            self,
            text='',
            font=t.font_caption(),
            corner_radius=t.RADIUS_SM,
            fg_color='transparent',
            width=72,
            height=24,
        )
        self.status_badge.grid(row=0, column=2, rowspan=2, padx=t.SPACE_MD, pady=t.SPACE_MD, sticky='e')

        if task.is_master_playlist:
            stream_row = ctk.CTkFrame(self, fg_color='transparent')
            stream_row.grid(row=3, column=0, columnspan=3, sticky='ew', padx=t.SPACE_MD, pady=(0, t.SPACE_MD))
            stream_row.grid_columnconfigure(1, weight=1)

            ctk.CTkLabel(
                stream_row,
                text='码率',
                font=t.font_caption(),
                text_color=t.MUTED,
                width=36,
            ).grid(row=0, column=0, sticky='w')

            stream_control = ctk.CTkFrame(
                stream_row,
                fg_color=t.SURFACE_INPUT,
                border_width=1,
                border_color=t.BORDER_STRONG,
                corner_radius=t.RADIUS_SM,
            )
            stream_control.grid(row=0, column=1, sticky='ew', padx=(t.SPACE_SM, 0))
            stream_control.grid_columnconfigure(0, weight=1)
            self.stream_menu = ctk.CTkOptionMenu(
                stream_control,
                values=task.stream_labels,
                command=self._on_stream_selected,
                height=28,
                font=t.font_caption(),
                fg_color='transparent',
                button_color=t.ACCENT,
                button_hover_color=t.ACCENT_HOVER,
                text_color=t.TEXT_PRIMARY,
                corner_radius=t.RADIUS_SM,
                dynamic_resizing=False,
            )
            if task.stream_labels:
                self.stream_menu.set(task.stream_labels[task.selected_stream_index])
            self.stream_menu.grid(row=0, column=0, sticky='ew')
        else:
            single_stream_tag = ctk.CTkLabel(
                self,
                text='码率 · 单流',
                font=t.font_caption(),
                text_color=t.TEXT_SECONDARY,
                fg_color=t.SURFACE_MUTED,
                corner_radius=t.RADIUS_SM,
                padx=t.SPACE_SM,
                height=24,
            )
            single_stream_tag.grid(
                row=3,
                column=1,
                columnspan=2,
                sticky='w',
                padx=t.SPACE_XS,
                pady=(0, t.SPACE_MD),
            )

        self.error_frame = ctk.CTkFrame(
            self,
            fg_color=t.STATUS_META['error']['background'],
            corner_radius=t.RADIUS_SM,
        )
        self.error_frame.grid_columnconfigure(0, weight=1)
        self._error_expanded = True
        ctk.CTkLabel(
            self.error_frame,
            text='错误详情',
            font=t.font_caption(),
            text_color=t.ERROR,
            anchor='w',
        ).grid(row=0, column=0, sticky='w', padx=t.SPACE_SM, pady=t.SPACE_SM)
        self.error_toggle_btn = t.style_ghost_button(
            ctk.CTkButton(self.error_frame, text='收起', command=self._toggle_error_details),
            width=68,
        )
        self.error_toggle_btn.grid(row=0, column=1, sticky='e', padx=t.SPACE_SM, pady=t.SPACE_XS)
        self.error_summary = ctk.CTkLabel(
            self.error_frame,
            text='',
            font=t.font_caption(),
            text_color=t.ERROR,
            justify='left',
            anchor='w',
            wraplength=520,
        )
        self.error_summary.grid(row=1, column=0, columnspan=2, sticky='ew', padx=t.SPACE_SM, pady=(0, t.SPACE_XS))
        self.copy_error_btn = t.style_ghost_button(
            ctk.CTkButton(self.error_frame, text='复制详情', command=self._copy_error),
            width=92,
        )
        self.copy_error_btn.grid(
            row=2,
            column=0,
            columnspan=2,
            sticky='w',
            padx=t.SPACE_SM,
            pady=(0, t.SPACE_SM),
        )
        self.error_frame.grid(row=4, column=0, columnspan=3, sticky='ew', padx=t.SPACE_MD, pady=(0, t.SPACE_MD))
        self.error_frame.grid_remove()

        self.refresh_status()

    def _on_checkbox(self) -> None:
        self.task.selected = bool(self.checkbox.get())
        self.on_selection_changed()

    def _on_stream_selected(self, value: str) -> None:
        if value in self.task.stream_labels:
            self.task.selected_stream_index = self.task.stream_labels.index(value)
        self.on_stream_changed()

    def refresh_status(self) -> None:
        status_key = self.task.status.value
        meta = t.STATUS_META.get(status_key, t.STATUS_META['pending'])
        self.status_badge.configure(
            text=f"{meta['icon']} {meta['label']}",
            fg_color=meta['background'],
            text_color=meta['color'],
        )
        if self.task.status == TaskStatus.ERROR:
            self.error_summary.configure(text=f'错误摘要：{self.task.error_message or "未提供错误详情"}')
            self.error_frame.grid()
        else:
            self.error_frame.grid_remove()
        if self.task.status == TaskStatus.DONE:
            self.progress_label.configure(text=completed_task_summary(), text_color=t.SUCCESS)
            self.progress.stop()
            self.progress.grid_remove()
            self.progress_frame.grid()
        elif self.task.status in {TaskStatus.PENDING, TaskStatus.SKIPPED, TaskStatus.ERROR}:
            self.progress.stop()
            self.progress.grid()
            self.progress_frame.grid_remove()

    def set_progress(self, phase: str, message: str, percent: int | None) -> None:
        """仅由主线程调用，以当前真实阶段更新唯一进度条。"""
        if phase not in {'merging', 'packaging'}:
            return
        self.progress_label.configure(text=message, text_color=t.ACCENT if percent is not None else t.WARNING)
        self.progress.grid()
        if percent is None:
            self.progress.configure(mode='indeterminate')
            self.progress.start()
        else:
            self.progress.stop()
            self.progress.configure(mode='determinate')
            self.progress.set(percent / 100)
        self.progress_frame.grid()

    def _copy_error(self) -> None:
        if self.on_copy_error is not None:
            self.on_copy_error(self.task)

    def _copy_path(self, _event=None) -> None:
        """点击中间截断的路径即可复制完整路径。"""
        self.clipboard_clear()
        self.clipboard_append(str(self.task.path))
        self.update_idletasks()

    def _toggle_error_details(self) -> None:
        self._error_expanded = not self._error_expanded
        if self._error_expanded:
            self.error_summary.grid()
            self.copy_error_btn.grid()
            self.error_toggle_btn.configure(text='收起')
        else:
            self.error_summary.grid_remove()
            self.copy_error_btn.grid_remove()
            self.error_toggle_btn.configure(text='展开')

    def set_enabled(self, enabled: bool) -> None:
        state = 'normal' if enabled else 'disabled'
        self.checkbox.configure(state=state)
        if hasattr(self, 'stream_menu'):
            self.stream_menu.configure(state=state)

    def focus_error(self) -> None:
        """以键盘焦点和边框提示当前失败任务。"""
        if not self._error_expanded:
            self._toggle_error_details()
        self.configure(border_color=t.ACCENT, border_width=2)
        self.checkbox.focus_set()

    def clear_focus_highlight(self) -> None:
        self.configure(border_color=t.BORDER, border_width=1)


class TaskList(ctk.CTkFrame):
    def __init__(
        self,
        master,
        on_selection_changed: Callable[[], None],
        output_directory: str | None,
        on_output_directory_changed: Callable[[str | None], None],
        on_choose_output_directory: Callable[[], None],
        on_open_output_directory: Callable[[], None],
        on_paths_dropped: Callable[[list[Path]], None] | None = None,
        on_clear_tasks: Callable[[], None] | None = None,
        on_start_conversion: Callable[[], None] | None = None,
        on_cancel_conversion: Callable[[], None] | None = None,
        on_copy_error: Callable[[ConversionTask], None] | None = None,
        on_view_error_log: Callable[[ConversionTask], None] | None = None,
        **kwargs,
    ):
        super().__init__(master, fg_color='transparent', **kwargs)
        self.on_selection_changed = on_selection_changed
        self.output_directory = output_directory
        self.on_output_directory_changed = on_output_directory_changed
        self.on_choose_output_directory = on_choose_output_directory
        self.on_open_output_directory = on_open_output_directory
        self.on_copy_error = on_copy_error
        self.on_view_error_log = on_view_error_log
        self.tasks: list[ConversionTask] = []
        self.rows: list[TaskRow] = []
        self._is_converting = False
        self._interactive = True
        self._clear_allowed = True

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        output_bar = ctk.CTkFrame(
            self, fg_color=t.SURFACE_MUTED, border_width=1, border_color=t.BORDER, corner_radius=t.RADIUS_SM,
            height=46,
        )
        output_bar.grid(row=0, column=0, sticky='ew', pady=(0, t.SPACE_SM))
        output_bar.grid_propagate(False)
        output_bar.grid_columnconfigure(2, weight=1)
        ctk.CTkLabel(output_bar, text='输出到', font=t.font_section()).grid(
            row=0, column=0, padx=(t.SPACE_MD, t.SPACE_SM), pady=0,
        )
        output_mode_frame = ctk.CTkFrame(
            output_bar,
            fg_color=t.SURFACE_INPUT,
            border_width=1,
            border_color=t.BORDER_STRONG,
            corner_radius=t.RADIUS_SM,
        )
        output_mode_frame.grid(row=0, column=1, padx=(0, t.SPACE_MD), pady=t.SPACE_XS)
        self.output_source_btn = ctk.CTkButton(
            output_mode_frame,
            text='源目录',
            width=58,
            height=28,
            corner_radius=t.RADIUS_SM,
            command=self._select_source_output_mode,
        )
        self.output_source_btn.pack(side='left', padx=2, pady=2)
        self.output_custom_btn = ctk.CTkButton(
            output_mode_frame,
            text='指定目录',
            width=72,
            height=28,
            corner_radius=t.RADIUS_SM,
            command=self._select_custom_output_mode,
        )
        self.output_custom_btn.pack(side='left', padx=(0, 2), pady=2)
        self.output_path_label = ctk.CTkLabel(
            output_bar, font=t.font_body(), text_color=t.TEXT_PRIMARY, anchor='w',
        )
        self.output_path_label.grid(row=0, column=2, sticky='ew', padx=(0, t.SPACE_MD), pady=0)
        self.output_path_label.bind('<Button-1>', self._open_selected_output_directory)
        self._refresh_output_bar()

        toolbar = ctk.CTkFrame(self, fg_color='transparent')
        toolbar.grid(row=1, column=0, sticky='ew', pady=(0, t.SPACE_SM))

        self.select_all_var = ctk.BooleanVar(value=False)
        self.select_all_cb = ctk.CTkCheckBox(
            toolbar,
            text='全选',
            variable=self.select_all_var,
            command=self._toggle_select_all,
            font=t.font_body(),
        )
        self.select_all_cb.pack(side='left')

        self.summary_label = ctk.CTkLabel(
            toolbar,
            text='已选 0 / 共 0',
            font=t.font_caption(),
            text_color=t.MUTED,
        )
        self.summary_label.pack(side='left', padx=(t.SPACE_SM, 0))
        self.queue_feedback_label = ctk.CTkLabel(
            toolbar,
            text='',
            font=t.font_caption(),
            text_color=t.MUTED,
            anchor='w',
        )
        self.queue_feedback_label.pack(side='left', padx=(t.SPACE_SM, 0))

        self.clear_btn = t.style_ghost_button(
            ctk.CTkButton(toolbar, text='清空列表', command=on_clear_tasks or (lambda: None), state='disabled'),
            width=88,
        )
        self.clear_btn.pack(side='right', padx=(t.SPACE_SM, 0))

        self.start_btn = t.style_primary_button(
            ctk.CTkButton(toolbar, text='开始转换', command=on_start_conversion or (lambda: None), state='disabled'),
            width=108,
        )
        self.start_btn.pack(side='right')
        self.cancel_btn = t.style_danger_button(
            ctk.CTkButton(toolbar, text='取消', command=on_cancel_conversion or (lambda: None)),
            width=88,
        )
        self.cancel_btn.pack(side='right')
        self.cancel_btn.pack_forget()

        self.add_entry = ctk.CTkFrame(self, fg_color='transparent', height=52)
        self.add_entry.grid(row=2, column=0, sticky='ew', pady=(0, t.SPACE_SM))
        self.add_entry.grid_propagate(False)
        self.drop_zone = DropZone(
            self.add_entry,
            on_paths_dropped=on_paths_dropped or (lambda _paths: None),
        )
        self.drop_zone.set_compact(True)
        self.drop_zone.pack(fill='both', expand=True)

        self.list_area = ctk.CTkFrame(self, fg_color='transparent')
        self.list_area.grid(row=3, column=0, sticky='nsew')
        self.empty_state = ctk.CTkLabel(
            self.list_area,
            text='队列为空，请拖放或选择 .m3u8 文件添加任务',
            font=t.font_caption(),
            text_color=t.MUTED,
            anchor='w',
        )
        self.scroll = ctk.CTkScrollableFrame(self.list_area, fg_color='transparent', height=1)
        self.scroll.bind('<Configure>', lambda _event: self.after_idle(self._update_scrollbar_visibility))
        self.list_area.bind('<Configure>', lambda _event: self.after_idle(self._update_scrollbar_visibility))
        self.drop_target_register(DND_FILES)
        self.dnd_bind('<<Drop>>', self._on_drop)
        self._apply_action_state()
        self.empty_state.pack(anchor='w', pady=(t.SPACE_SM, 0))

    def set_tasks(self, tasks: list[ConversionTask]) -> None:
        self.tasks = tasks
        for row in self.rows:
            row.destroy()
        self.rows.clear()

        layout = queue_content_layout(len(tasks))
        row_master = self.scroll if layout.scrollable else self.list_area
        for task in tasks:
            row = TaskRow(
                row_master,
                task=task,
                on_selection_changed=self._update_summary,
                on_stream_changed=self._update_summary,
                on_copy_error=self.on_copy_error,
                on_view_error_log=self.on_view_error_log,
            )
            row.pack(fill='x', pady=(0, t.SPACE_SM))
            self.rows.append(row)

        self.select_all_var.set(bool(tasks) and all(task.selected for task in tasks))
        self.add_entry.configure(height=layout.drop_zone_height)
        self.empty_state.pack_forget()
        self.scroll.pack_forget()
        if layout.show_empty_state:
            self.empty_state.pack(anchor='w', pady=(t.SPACE_SM, 0))
        elif layout.scrollable:
            self.scroll.pack(fill='both', expand=True)
        else:
            for row in self.rows:
                row.pack(fill='x', pady=(0, t.SPACE_SM))
        self._update_summary()
        self.after_idle(self._update_scrollbar_visibility)

    def _on_drop(self, event) -> None:
        """让独立队列区域持续接收拖放。"""
        self.drop_zone._on_drop(event)

    def _update_scrollbar_visibility(self) -> None:
        """仅在任务内容超出当前可用队列空间时显示滚动条。"""
        if not self.rows:
            return
        canvas = getattr(self.scroll, '_parent_canvas', None)
        scrollbar = getattr(self.scroll, '_scrollbar', None)
        if canvas is None or scrollbar is None:
            return
        region = canvas.bbox('all')
        if region is None or canvas.winfo_height() <= 1:
            return
        content_height = region[3] - region[1]
        if content_height > canvas.winfo_height():
            scrollbar.grid()
        else:
            scrollbar.grid_remove()

    def _toggle_select_all(self) -> None:
        selected = self.select_all_var.get()
        for task in self.tasks:
            task.selected = selected
        for row in self.rows:
            if selected:
                row.checkbox.select()
            else:
                row.checkbox.deselect()
        self.on_selection_changed()
        self._update_summary()

    def _update_summary(self) -> None:
        total = len(self.tasks)
        selected = sum(1 for task in self.tasks if task.selected)
        self.summary_label.configure(text=f'已选 {selected} / 共 {total}')
        self.select_all_var.set(total > 0 and selected == total)
        self._apply_action_state()
        self.on_selection_changed()

    def set_queue_feedback(self, feedback: QueueFeedback) -> None:
        """将队列反馈内联显示在选择统计后，不改变工具栏高度。"""
        colors = {
            'muted': t.MUTED,
            'accent': t.ACCENT,
            'success': t.SUCCESS,
            'warning': t.WARNING,
            'error': t.ERROR,
        }
        self.queue_feedback_label.configure(
            text=feedback.message,
            text_color=colors.get(feedback.tone, t.MUTED),
        )

    def refresh_rows(self) -> None:
        for row in self.rows:
            row.refresh_status()
        self.after_idle(self._update_scrollbar_visibility)

    def set_task_progress(self, task_index: int, phase: str, message: str, percent: int | None) -> None:
        if 0 <= task_index < len(self.rows):
            self.rows[task_index].set_progress(phase, message, percent)
            self.after_idle(self._update_scrollbar_visibility)

    def _select_source_output_mode(self) -> None:
        if self._interactive:
            self.on_output_directory_changed(None)

    def _select_custom_output_mode(self) -> None:
        if self._interactive:
            self.on_choose_output_directory()

    def _open_selected_output_directory(self, _event=None) -> None:
        if self._interactive and self.output_directory:
            self.on_open_output_directory()

    def set_output_directory(self, output_directory: str | None) -> None:
        self.output_directory = output_directory
        self._refresh_output_bar()

    def _refresh_output_bar(self) -> None:
        mode, path = format_output_destination(self.output_directory)
        self.output_path_label.configure(text=output_destination_detail(self.output_directory))
        custom_directory_selected = mode == '指定目录'
        self.output_source_btn.configure(
            fg_color=t.ACCENT_MUTED if not custom_directory_selected else 'transparent',
            hover_color=t.ACCENT_MUTED if not custom_directory_selected else t.SURFACE_MUTED,
            text_color=t.ACCENT if not custom_directory_selected else t.TEXT_SECONDARY,
        )
        self.output_custom_btn.configure(
            fg_color=t.ACCENT_MUTED if custom_directory_selected else 'transparent',
            hover_color=t.ACCENT_MUTED if custom_directory_selected else t.SURFACE_MUTED,
            text_color=t.ACCENT if custom_directory_selected else t.TEXT_SECONDARY,
        )
        if self.output_directory:
            self.output_path_label.configure(text_color=t.ACCENT, cursor='hand2')
        else:
            self.output_path_label.configure(text_color=t.TEXT_PRIMARY, cursor='')

    def focus_first_error(self) -> ConversionTask | None:
        """滚动并将键盘焦点置于第一项失败任务，返回对应任务。"""
        error_row = next((row for row in self.rows if row.task.status == TaskStatus.ERROR), None)
        if error_row is None:
            return None

        for row in self.rows:
            row.clear_focus_highlight()

        self.update_idletasks()
        canvas = getattr(self.scroll, '_parent_canvas', None)
        if canvas is not None:
            scroll_region = canvas.bbox('all')
            if scroll_region is not None:
                _, top, _, bottom = scroll_region
                content_height = max(bottom - top, 1)
                canvas.yview_moveto(max(0, (error_row.winfo_y() - top) / content_height))

        error_row.focus_error()
        return error_row.task

    def set_interactive(self, enabled: bool) -> None:
        self._interactive = enabled
        for row in self.rows:
            row.set_enabled(enabled)
        self.set_output_controls_enabled(enabled)
        self._apply_action_state()

    def set_clear_enabled(self, enabled: bool) -> None:
        self._clear_allowed = enabled
        self._apply_action_state()

    def set_converting(self, is_converting: bool) -> None:
        self._is_converting = is_converting
        self._apply_action_state()

    def update_action_state(self) -> None:
        self._apply_action_state()

    def _apply_action_state(self) -> None:
        state = queue_action_state(
            task_count=len(self.tasks),
            selected_count=sum(1 for task in self.tasks if task.selected),
            is_converting=self._is_converting,
        )
        can_interact = self._interactive
        self.select_all_cb.configure(
            state='normal' if state.select_all_enabled and can_interact else 'disabled',
        )
        self.clear_btn.configure(
            state='normal' if state.clear_enabled and self._clear_allowed and can_interact else 'disabled',
        )
        t.set_primary_button_state(self.start_btn, state.start_enabled and can_interact)
        if state.cancel_visible:
            self.start_btn.pack_forget()
            self.cancel_btn.pack(side='right')
        else:
            self.cancel_btn.pack_forget()
            self.start_btn.pack(side='right')

    def set_output_controls_enabled(self, enabled: bool) -> None:
        state = 'normal' if enabled else 'disabled'
        self.output_source_btn.configure(state=state)
        self.output_custom_btn.configure(state=state)
