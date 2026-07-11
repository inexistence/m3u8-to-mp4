"""任务列表：勾选与码率选择。"""
from __future__ import annotations

from pathlib import Path
from typing import Callable

import customtkinter as ctk

from gui import theme as t
from gui.models import ConversionTask, TaskStatus


STATUS_LABELS = {
    TaskStatus.PENDING: '',
    TaskStatus.RUNNING: '转换中',
    TaskStatus.DONE: '完成',
    TaskStatus.ERROR: '失败',
    TaskStatus.SKIPPED: '已跳过',
}


def _short_path(path: Path) -> tuple[str, str]:
    """返回 (文件名, 目录路径)。"""
    return path.name, str(path.parent)


class TaskRow(ctk.CTkFrame):
    def __init__(
        self,
        master,
        task: ConversionTask,
        on_selection_changed: Callable[[], None],
        on_stream_changed: Callable[[], None],
        **kwargs,
    ):
        super().__init__(master, corner_radius=t.RADIUS_SM, border_width=1, **kwargs)
        self.task = task
        self.on_selection_changed = on_selection_changed
        self.on_stream_changed = on_stream_changed

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
            stream_row.grid(row=2, column=0, columnspan=3, sticky='ew', padx=t.SPACE_MD, pady=(0, t.SPACE_MD))
            stream_row.grid_columnconfigure(1, weight=1)

            ctk.CTkLabel(
                stream_row,
                text='码率',
                font=t.font_caption(),
                text_color=t.MUTED,
                width=36,
            ).grid(row=0, column=0, sticky='w')

            self.stream_menu = ctk.CTkOptionMenu(
                stream_row,
                values=task.stream_labels,
                command=self._on_stream_selected,
                height=28,
                font=t.font_caption(),
            )
            if task.stream_labels:
                self.stream_menu.set(task.stream_labels[task.selected_stream_index])
            self.stream_menu.grid(row=0, column=1, sticky='ew', padx=(t.SPACE_SM, 0))
        else:
            ctk.CTkLabel(
                self,
                text='单流',
                font=t.font_caption(),
                text_color=t.MUTED,
                anchor='w',
            ).grid(row=2, column=1, columnspan=2, sticky='w', padx=t.SPACE_XS, pady=(0, t.SPACE_MD))

        self.refresh_status()

    def _on_checkbox(self) -> None:
        self.task.selected = bool(self.checkbox.get())
        self.on_selection_changed()

    def _on_stream_selected(self, value: str) -> None:
        if value in self.task.stream_labels:
            self.task.selected_stream_index = self.task.stream_labels.index(value)
        self.on_stream_changed()

    def refresh_status(self) -> None:
        label = STATUS_LABELS.get(self.task.status, '')
        self.status_badge.configure(text=label)

        if self.task.status == TaskStatus.PENDING:
            self.status_badge.configure(fg_color='transparent', text_color=t.MUTED)
        elif self.task.status == TaskStatus.RUNNING:
            self.status_badge.configure(fg_color=t.ACCENT_MUTED, text_color=t.ACCENT)
        elif self.task.status == TaskStatus.DONE:
            self.status_badge.configure(fg_color=('#dcfce7', '#14532d'), text_color=t.SUCCESS)
        elif self.task.status == TaskStatus.ERROR:
            self.status_badge.configure(fg_color=('#fee2e2', '#7f1d1d'), text_color=t.ERROR)
        elif self.task.status == TaskStatus.SKIPPED:
            self.status_badge.configure(fg_color=('#fef3c7', '#78350f'), text_color=t.WARNING)
        else:
            self.status_badge.configure(fg_color='transparent', text_color=t.MUTED)

    def set_enabled(self, enabled: bool) -> None:
        state = 'normal' if enabled else 'disabled'
        self.checkbox.configure(state=state)
        if hasattr(self, 'stream_menu'):
            self.stream_menu.configure(state=state)


class TaskList(ctk.CTkFrame):
    def __init__(self, master, on_selection_changed: Callable[[], None], **kwargs):
        super().__init__(master, fg_color='transparent', **kwargs)
        self.on_selection_changed = on_selection_changed
        self.tasks: list[ConversionTask] = []
        self.rows: list[TaskRow] = []

        toolbar = ctk.CTkFrame(self, fg_color='transparent')
        toolbar.pack(fill='x', pady=(0, t.SPACE_SM))

        self.select_all_var = ctk.BooleanVar(value=True)
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
        self.summary_label.pack(side='right')

        self.scroll = ctk.CTkScrollableFrame(self, fg_color='transparent')
        self.scroll.pack(fill='both', expand=True)

        self.empty_label = ctk.CTkLabel(
            self.scroll,
            text='暂无任务，请拖入或选择 m3u8 文件',
            font=t.font_caption(),
            text_color=t.MUTED,
        )

    def set_tasks(self, tasks: list[ConversionTask]) -> None:
        self.tasks = tasks
        for row in self.rows:
            row.destroy()
        self.rows.clear()

        if not tasks:
            self.empty_label.pack(expand=True, pady=t.SPACE_XL)
        else:
            self.empty_label.pack_forget()

        for task in tasks:
            row = TaskRow(
                self.scroll,
                task=task,
                on_selection_changed=self._update_summary,
                on_stream_changed=self._update_summary,
            )
            row.pack(fill='x', pady=(0, t.SPACE_SM))
            self.rows.append(row)

        self.select_all_var.set(all(task.selected for task in tasks) if tasks else False)
        self._update_summary()

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
        self.on_selection_changed()

    def refresh_rows(self) -> None:
        for row in self.rows:
            row.refresh_status()

    def set_interactive(self, enabled: bool) -> None:
        state = 'normal' if enabled else 'disabled'
        self.select_all_cb.configure(state=state)
        for row in self.rows:
            row.set_enabled(enabled)
