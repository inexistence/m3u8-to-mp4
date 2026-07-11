"""任务列表：勾选与码率选择。"""
from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from gui.models import ConversionTask, TaskStatus


STATUS_LABELS = {
    TaskStatus.PENDING: '',
    TaskStatus.RUNNING: '转换中…',
    TaskStatus.DONE: '✓ 完成',
    TaskStatus.ERROR: '✗ 失败',
    TaskStatus.SKIPPED: '已跳过',
}


class TaskRow(ctk.CTkFrame):
    def __init__(
        self,
        master,
        task: ConversionTask,
        on_selection_changed: Callable[[], None],
        on_stream_changed: Callable[[], None],
        **kwargs,
    ):
        super().__init__(master, **kwargs)
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
        self.checkbox.grid(row=0, column=0, rowspan=2, padx=(8, 4), pady=8, sticky='n')
        if task.selected:
            self.checkbox.select()

        self.path_label = ctk.CTkLabel(
            self,
            text=str(task.path),
            anchor='w',
            justify='left',
        )
        self.path_label.grid(row=0, column=1, sticky='ew', padx=4, pady=(8, 0))

        self.status_label = ctk.CTkLabel(self, text='', text_color='gray', anchor='e')
        self.status_label.grid(row=0, column=2, padx=8, pady=(8, 0))

        if task.is_master_playlist:
            self.stream_menu = ctk.CTkOptionMenu(
                self,
                values=task.stream_labels,
                command=self._on_stream_selected,
            )
            if task.stream_labels:
                self.stream_menu.set(task.stream_labels[task.selected_stream_index])
            self.stream_menu.grid(row=1, column=1, columnspan=2, sticky='ew', padx=4, pady=(0, 8))
        else:
            single_label = ctk.CTkLabel(self, text='单流（无需选择码率）', text_color='gray', anchor='w')
            single_label.grid(row=1, column=1, columnspan=2, sticky='ew', padx=4, pady=(0, 8))

        self.refresh_status()

    def _on_checkbox(self) -> None:
        self.task.selected = bool(self.checkbox.get())
        self.on_selection_changed()

    def _on_stream_selected(self, value: str) -> None:
        if value in self.task.stream_labels:
            self.task.selected_stream_index = self.task.stream_labels.index(value)
        self.on_stream_changed()

    def refresh_status(self) -> None:
        self.status_label.configure(text=STATUS_LABELS.get(self.task.status, ''))
        if self.task.status == TaskStatus.DONE:
            self.status_label.configure(text_color='#2ecc71')
        elif self.task.status == TaskStatus.ERROR:
            self.status_label.configure(text_color='#e74c3c')
        elif self.task.status == TaskStatus.RUNNING:
            self.status_label.configure(text_color='#3498db')
        else:
            self.status_label.configure(text_color='gray')

    def set_enabled(self, enabled: bool) -> None:
        state = 'normal' if enabled else 'disabled'
        self.checkbox.configure(state=state)
        if hasattr(self, 'stream_menu'):
            self.stream_menu.configure(state=state)


class TaskList(ctk.CTkFrame):
    def __init__(self, master, on_selection_changed: Callable[[], None], **kwargs):
        super().__init__(master, **kwargs)
        self.on_selection_changed = on_selection_changed
        self.tasks: list[ConversionTask] = []
        self.rows: list[TaskRow] = []

        toolbar = ctk.CTkFrame(self, fg_color='transparent')
        toolbar.pack(fill='x', padx=8, pady=(8, 4))

        self.select_all_var = ctk.BooleanVar(value=True)
        self.select_all_cb = ctk.CTkCheckBox(
            toolbar,
            text='全选',
            variable=self.select_all_var,
            command=self._toggle_select_all,
        )
        self.select_all_cb.pack(side='left')

        self.summary_label = ctk.CTkLabel(toolbar, text='已选 0 / 共 0', text_color='gray')
        self.summary_label.pack(side='right')

        self.scroll = ctk.CTkScrollableFrame(self)
        self.scroll.pack(fill='both', expand=True, padx=8, pady=(0, 8))

    def set_tasks(self, tasks: list[ConversionTask]) -> None:
        self.tasks = tasks
        for row in self.rows:
            row.destroy()
        self.rows.clear()

        for task in tasks:
            row = TaskRow(
                self.scroll,
                task=task,
                on_selection_changed=self._update_summary,
                on_stream_changed=self._update_summary,
            )
            row.pack(fill='x', pady=4)
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
