"""dy_threshold per-CSV configuration for Hayato upward movement."""

import tkinter as tk
import os
import pickle
from tkinter import ttk, messagebox
from src.gui.interfaces import LabelFrame, Frame
from src.common.interfaces import Configurable
from src.common import config


class DyThresholdSettings(Configurable):
    TARGET = 'hayato_dy_threshold'
    DEFAULT_CONFIG = {
        'default': 0.39,
    }

    def load_config(self):
        """重写加载逻辑，允许动态键（不限于 DEFAULT_CONFIG）"""
        path = os.path.join(self.DIRECTORY, self.TARGET)
        if os.path.isfile(path):
            with open(path, 'rb') as file:
                loaded = pickle.load(file)
                # 确保 'default' 存在，其他自定义键全部保留
                merged = dict(loaded)
                merged.setdefault('default', self.DEFAULT_CONFIG['default'])
                self.config = merged
        else:
            self.save_config()

    def get(self, csv_name):
        return self.config.get(csv_name, self.DEFAULT_CONFIG['default'])

    def set(self, csv_name, value):
        self.config[csv_name] = value

    def remove(self, csv_name):
        if csv_name != 'default' and csv_name in self.config:
            del self.config[csv_name]

    def get_all_entries(self):
        return {k: v for k, v in self.config.items() if k != 'default'}


class DyThreshold(LabelFrame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, 'Hayato Upward dY Threshold', **kwargs)

        self.settings = DyThresholdSettings('hayato_dy_threshold')

        # Default threshold row
        default_row = Frame(self)
        default_row.pack(side=tk.TOP, fill='x', expand=True, pady=5, padx=5)
        tk.Label(default_row, text='Default threshold:', anchor='w').pack(side=tk.LEFT, padx=(0, 5))
        self.default_var = tk.StringVar(value=str(self.settings.get('default')))
        default_entry = tk.Entry(default_row, textvariable=self.default_var, width=10)
        default_entry.pack(side=tk.LEFT, padx=(0, 5))
        tk.Button(default_row, text='Save Default', command=self._on_save_default).pack(side=tk.LEFT)

        # Separator
        ttk.Separator(self, orient=tk.HORIZONTAL).pack(fill='x', padx=5, pady=5)

        # Per-CSV override section
        header = Frame(self)
        header.pack(side=tk.TOP, fill='x', expand=True, pady=(5, 2), padx=5)
        tk.Label(header, text='Per-CSV Overrides:', anchor='w', font=('', 9, 'bold')).pack(side=tk.LEFT)

        # Add new entry row
        add_row = Frame(self)
        add_row.pack(side=tk.TOP, fill='x', expand=True, pady=2, padx=5)
        tk.Label(add_row, text='CSV name:', anchor='w').pack(side=tk.LEFT, padx=(0, 3))
        self.new_csv_var = tk.StringVar(value=self._get_current_routine_name())
        tk.Entry(add_row, textvariable=self.new_csv_var, width=18).pack(side=tk.LEFT, padx=(0, 3))
        tk.Label(add_row, text='Threshold:', anchor='w').pack(side=tk.LEFT, padx=(5, 3))
        self.new_threshold_var = tk.StringVar(value='0.39')
        tk.Entry(add_row, textvariable=self.new_threshold_var, width=8).pack(side=tk.LEFT, padx=(0, 3))
        tk.Button(add_row, text='Add', command=self._on_add_override).pack(side=tk.LEFT)

        # Scrollable list of existing overrides
        list_frame = Frame(self)
        list_frame.pack(side=tk.TOP, fill='both', expand=True, pady=5, padx=5)

        self.canvas = tk.Canvas(list_frame, height=120, highlightthickness=0)
        scrollbar = tk.Scrollbar(list_frame, orient='vertical', command=self.canvas.yview)
        self.scrollable_frame = Frame(self.canvas)
        self.scrollable_frame.bind(
            '<Configure>',
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox('all'))
        )
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor='nw')
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        self.override_rows = {}
        self.refresh_list()

    def refresh_list(self):
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        self.override_rows.clear()

        entries = self.settings.get_all_entries()
        if not entries:
            tk.Label(self.scrollable_frame, text='(no overrides)', fg='gray').pack(anchor='w', pady=5)
            return

        for csv_name, value in entries.items():
            row = Frame(self.scrollable_frame)
            row.pack(side=tk.TOP, fill='x', pady=1)

            var = tk.StringVar(value=str(value))

            tk.Label(row, text=csv_name, width=20, anchor='w').pack(side=tk.LEFT, padx=(0, 3))
            tk.Entry(row, textvariable=var, width=8).pack(side=tk.LEFT, padx=(0, 3))

            cmd = lambda c=csv_name, v=var: self._on_edit(c, v)
            tk.Button(row, text='Save', width=5, command=cmd).pack(side=tk.LEFT, padx=(0, 2))

            cmd_del = lambda c=csv_name: self._on_delete(c)
            tk.Button(row, text='X', width=2, command=cmd_del).pack(side=tk.LEFT)

            self.override_rows[csv_name] = var

    def _get_current_routine_name(self):
        """获取当前选择的 routine CSV 文件名"""
        try:
            if config.routine and config.routine.path:
                return os.path.basename(config.routine.path)
        except Exception:
            pass
        return ''

    def _validate_float(self, s):
        try:
            v = float(s)
            assert v > 0
            return True
        except (ValueError, AssertionError):
            return False

    def _on_save_default(self):
        val = self.default_var.get().strip()
        if not self._validate_float(val):
            messagebox.showerror('Error', 'Please enter a positive number.')
            return
        self.settings.set('default', float(val))
        self.settings.save_config()

    def _on_add_override(self):
        csv_name = self.new_csv_var.get().strip()
        threshold = self.new_threshold_var.get().strip()
        if not csv_name:
            messagebox.showerror('Error', 'CSV name cannot be empty.')
            return
        if not self._validate_float(threshold):
            messagebox.showerror('Error', 'Threshold must be a positive number.')
            return
        self.settings.set(csv_name, float(threshold))
        self.settings.save_config()
        self.new_csv_var.set('')
        self.refresh_list()

    def _on_edit(self, csv_name, var):
        val = var.get().strip()
        if not self._validate_float(val):
            messagebox.showerror('Error', 'Threshold must be a positive number.')
            return
        self.settings.set(csv_name, float(val))
        self.settings.save_config()

    def _on_delete(self, csv_name):
        self.settings.remove(csv_name)
        self.settings.save_config()
        self.refresh_list()
