from __future__ import annotations

import json
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .compiler import Compiler
from .errors import CompileError


APP_ROOT = Path(__file__).resolve().parent.parent
RUNTIME_ROOT = Path.cwd()
EXECUTABLE_ROOT = Path(getattr(__import__("sys"), "executable", __file__)).resolve().parent
IS_FROZEN = getattr(__import__("sys"), "frozen", False)
SETTINGS_ROOT = EXECUTABLE_ROOT if IS_FROZEN else APP_ROOT
SETTINGS_PATH = SETTINGS_ROOT / "gmam_gui_settings.json"
CONFIG_FILE_TYPES = [("GMAM GUI 配置", "*.json"), ("所有文件", "*.*")]


class GMAMGui:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("GMAM GUI")
        self.root.geometry("900x700")

        self.input_files: list[str] = []

        self.format_var = tk.StringVar(value="gms")
        self.output_type_var = tk.StringVar(value="timeline")
        self.time_scale_var = tk.StringVar(value="ask")
        self.output_path_var = tk.StringVar()
        self.status_var = tk.StringVar(value="就绪")
        self.last_input_dir = str(RUNTIME_ROOT)
        self.last_output_dir = str(RUNTIME_ROOT)

        self._build_ui()
        self._load_settings()
        self._sync_output_type_state()

    def _build_ui(self) -> None:
        container = ttk.Frame(self.root, padding=12)
        container.pack(fill=tk.BOTH, expand=True)
        container.columnconfigure(0, weight=3)
        container.columnconfigure(1, weight=2)
        container.rowconfigure(0, weight=1)
        container.rowconfigure(1, weight=0)
        container.rowconfigure(2, weight=0)
        container.rowconfigure(3, weight=1)
        container.rowconfigure(4, weight=0)

        files_frame = ttk.LabelFrame(container, text="输入文件", padding=8)
        files_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 6), pady=(0, 8))
        files_frame.columnconfigure(0, weight=1)
        files_frame.rowconfigure(1, weight=1)

        input_entry_frame = ttk.Frame(files_frame)
        input_entry_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        input_entry_frame.columnconfigure(0, weight=1)

        self.input_path_var = tk.StringVar()
        ttk.Entry(input_entry_frame, textvariable=self.input_path_var).grid(row=0, column=0, sticky="ew")
        ttk.Button(input_entry_frame, text="加入路径", command=self._add_input_path).grid(row=0, column=1, sticky="ew", padx=(8, 0))

        self.files_list = tk.Listbox(files_frame, height=8)
        self.files_list.grid(row=1, column=0, sticky="nsew", pady=(0, 8))
        files_scrollbar = ttk.Scrollbar(files_frame, orient="vertical", command=self.files_list.yview)
        files_scrollbar.grid(row=1, column=1, sticky="ns", pady=(0, 8), padx=(8, 0))
        self.files_list.configure(yscrollcommand=files_scrollbar.set)

        files_button_frame = ttk.Frame(files_frame)
        files_button_frame.grid(row=2, column=0, columnspan=2, sticky="ew")
        for col in range(3):
            files_button_frame.columnconfigure(col, weight=1)
        ttk.Button(files_button_frame, text="添加文件", command=self._add_files).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ttk.Button(files_button_frame, text="移除选中", command=self._remove_selected_file).grid(row=0, column=1, sticky="ew", padx=4)
        ttk.Button(files_button_frame, text="清空列表", command=self._clear_files).grid(row=0, column=2, sticky="ew", padx=(4, 0))

        options_frame = ttk.LabelFrame(container, text="编译选项", padding=8)
        options_frame.grid(row=0, column=1, sticky="nsew", padx=(6, 0), pady=(0, 8))
        for col in range(2):
            options_frame.columnconfigure(col, weight=1)

        ttk.Label(options_frame, text="格式").grid(row=0, column=0, sticky="w", pady=(0, 4))
        format_box = ttk.Combobox(
            options_frame,
            textvariable=self.format_var,
            values=("gms", "gm82"),
            state="readonly",
        )
        format_box.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        format_box.bind("<<ComboboxSelected>>", lambda _event: self._sync_output_type_state())

        ttk.Label(options_frame, text="输出类型").grid(row=2, column=0, sticky="w", pady=(0, 4))
        self.output_type_box = ttk.Combobox(
            options_frame,
            textvariable=self.output_type_var,
            values=("timeline", "step", "txt"),
            state="readonly",
        )
        self.output_type_box.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        self.output_type_box.bind("<<ComboboxSelected>>", lambda _event: None)

        ttk.Label(options_frame, text="时间缩放").grid(row=4, column=0, sticky="w", pady=(0, 4))
        time_scale_box = ttk.Combobox(
            options_frame,
            textvariable=self.time_scale_var,
            values=("ask", "adjust", "round"),
            state="readonly",
        )
        time_scale_box.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        time_scale_box.bind("<<ComboboxSelected>>", lambda _event: None)

        action_box = ttk.Frame(options_frame)
        action_box.grid(row=6, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        action_box.columnconfigure(0, weight=1)
        ttk.Button(action_box, text="开始编译", command=self._compile).grid(row=0, column=0, sticky="ew")

        output_frame = ttk.LabelFrame(container, text="输出文件", padding=8)
        output_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=8)
        output_frame.columnconfigure(0, weight=1)

        ttk.Entry(output_frame, textvariable=self.output_path_var).grid(row=0, column=0, sticky="ew")
        button_frame = ttk.Frame(output_frame)
        button_frame.grid(row=0, column=1, sticky="e", padx=(8, 0))
        ttk.Button(button_frame, text="应用路径", command=self._apply_output_path).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ttk.Button(button_frame, text="选择输出", command=self._choose_output).grid(row=0, column=1, sticky="ew")

        config_frame = ttk.Frame(container)
        config_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        config_frame.columnconfigure(0, weight=1)

        ttk.Label(config_frame, textvariable=self.status_var).grid(row=0, column=0, sticky="w")
        ttk.Button(config_frame, text="保存配置", command=self._save_named_settings).grid(row=0, column=1, sticky="e", padx=(8, 4))
        ttk.Button(config_frame, text="载入配置", command=self._load_named_settings).grid(row=0, column=2, sticky="e", padx=(4, 0))

        result_frame = ttk.LabelFrame(container, text="输出 / 报错", padding=8)
        result_frame.grid(row=3, column=0, columnspan=2, sticky="nsew", pady=(0, 8))
        result_frame.columnconfigure(0, weight=1)
        result_frame.rowconfigure(0, weight=1)

        self.result_text = tk.Text(result_frame, wrap="word", height=18)
        self.result_text.grid(row=0, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(result_frame, orient="vertical", command=self.result_text.yview)
        scrollbar.grid(row=0, column=1, sticky="ns", padx=(8, 0))
        self.result_text.configure(yscrollcommand=scrollbar.set)

        ttk.Button(result_frame, text="清空输出", command=self._clear_result).grid(row=1, column=0, sticky="e", pady=(8, 0))

    def _on_format_changed(self) -> None:
        self._sync_output_type_state()

    @staticmethod
    def _normalize_path_text(path: str) -> str:
        return path.strip().strip('"')

    def _resolve_path(self, path: str) -> Path:
        candidate = Path(self._normalize_path_text(path))
        if candidate.is_absolute():
            return candidate
        return RUNTIME_ROOT / candidate

    def _to_stored_path(self, path: str) -> str:
        normalized = self._normalize_path_text(path)
        if not normalized:
            return ""
        candidate = Path(normalized)
        if not candidate.is_absolute():
            return str(candidate)
        try:
            return str(candidate.relative_to(RUNTIME_ROOT))
        except ValueError:
            return str(candidate)

    def _collect_named_settings(self) -> dict[str, object]:
        return {
            "input_files": [self._to_stored_path(path) for path in self.input_files],
            "format": self.format_var.get(),
            "output_type": self.output_type_var.get(),
            "time_scale": self.time_scale_var.get(),
            "output_path": self._to_stored_path(self.output_path_var.get()),
            "input_path_text": self.input_path_var.get().strip(),
        }

    def _collect_runtime_settings(self) -> dict[str, object]:
        settings = self._collect_named_settings()
        settings["last_input_dir"] = self._to_stored_path(self.last_input_dir)
        settings["last_output_dir"] = self._to_stored_path(self.last_output_dir)
        return settings

    def _apply_settings(self, settings: dict[str, object]) -> None:
        self.files_list.delete(0, tk.END)
        self.input_files.clear()
        input_files = settings.get("input_files", [])
        if isinstance(input_files, list):
            for path in input_files:
                if isinstance(path, str):
                    resolved = self._resolve_path(path)
                    if resolved.exists():
                        display_path = path if not Path(path).is_absolute() else str(resolved)
                        if display_path not in self.input_files:
                            self.input_files.append(display_path)
                            self.files_list.insert(tk.END, display_path)
        if settings.get("format") in {"gms", "gm82"}:
            self.format_var.set(settings["format"])
        if settings.get("output_type") in {"timeline", "step", "txt"}:
            self.output_type_var.set(settings["output_type"])
        if settings.get("time_scale") in {"ask", "adjust", "round"}:
            self.time_scale_var.set(settings["time_scale"])
        output_path = settings.get("output_path")
        self.output_path_var.set(output_path if isinstance(output_path, str) else "")
        input_path_text = settings.get("input_path_text")
        self.input_path_var.set(input_path_text if isinstance(input_path_text, str) else "")
        last_input_dir = settings.get("last_input_dir")
        if isinstance(last_input_dir, str) and last_input_dir:
            self.last_input_dir = str(self._resolve_path(last_input_dir))
        last_output_dir = settings.get("last_output_dir")
        if isinstance(last_output_dir, str) and last_output_dir:
            self.last_output_dir = str(self._resolve_path(last_output_dir))
        self._sync_output_type_state()

    def _load_settings(self) -> None:
        if not SETTINGS_PATH.exists():
            return
        try:
            settings = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            self.status_var.set("设置文件读取失败，已使用默认选项")
            return
        self._apply_settings(settings)
        if self.input_files:
            self.status_var.set(f"已恢复 {len(self.input_files)} 个输入文件和上次选项")

    def _save_settings(self) -> None:
        try:
            SETTINGS_PATH.write_text(
                json.dumps(self._collect_runtime_settings(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError:
            self.status_var.set("设置保存失败")

    def _save_named_settings(self) -> None:
        path = filedialog.asksaveasfilename(
            title="保存配置",
            initialdir=self.last_output_dir,
            defaultextension=".json",
            filetypes=CONFIG_FILE_TYPES,
        )
        if not path:
            return
        target = self._resolve_path(path)
        self.last_output_dir = str(target.parent)
        try:
            target.write_text(
                json.dumps(self._collect_named_settings(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            self.status_var.set(f"已保存配置：{target}")
        except OSError as error:
            messagebox.showerror("GMAM GUI", f"保存配置失败：{error}")

    def _load_named_settings(self) -> None:
        path = filedialog.askopenfilename(
            title="载入配置",
            initialdir=self.last_input_dir,
            filetypes=CONFIG_FILE_TYPES,
        )
        if not path:
            return
        target = self._resolve_path(path)
        self.last_input_dir = str(target.parent)
        try:
            settings = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            messagebox.showerror("GMAM GUI", f"载入配置失败：{error}")
            return
        self._apply_settings(settings)
        self.status_var.set(f"已载入配置：{target}")

    def _sync_output_type_state(self) -> None:
        if self.output_type_var.get() not in {"timeline", "step", "txt"}:
            self.output_type_var.set("timeline")
        self.output_type_box.configure(state="readonly")

    def _add_input_path(self) -> None:
        path = self._normalize_path_text(self.input_path_var.get())
        if not path:
            messagebox.showerror("GMAM GUI", "请输入输入文件路径。")
            return
        resolved = self._resolve_path(path)
        if not resolved.exists():
            messagebox.showerror("GMAM GUI", f"输入文件不存在：{resolved}")
            return
        self.last_input_dir = str(resolved.parent)
        if path not in self.input_files:
            self.input_files.append(path)
            self.files_list.insert(tk.END, path)
        self.input_path_var.set("")
        self.status_var.set(f"已选择 {len(self.input_files)} 个输入文件")

    def _add_files(self) -> None:
        paths = filedialog.askopenfilenames(
            title="选择 GMAM 输入文件",
            initialdir=self.last_input_dir,
            filetypes=[("GMAM 文件", "*.tl"), ("所有文件", "*.*")],
        )
        if paths:
            self.last_input_dir = str(Path(paths[0]).resolve().parent)
        for path in paths:
            if path not in self.input_files:
                self.input_files.append(path)
                self.files_list.insert(tk.END, path)
        self.input_path_var.set("")
        self.status_var.set(f"已选择 {len(self.input_files)} 个输入文件")

    def _remove_selected_file(self) -> None:
        selected = list(self.files_list.curselection())
        if not selected:
            return
        for index in reversed(selected):
            self.files_list.delete(index)
            del self.input_files[index]
        self.status_var.set(f"剩余 {len(self.input_files)} 个输入文件")

    def _clear_files(self) -> None:
        self.files_list.delete(0, tk.END)
        self.input_files.clear()
        self.status_var.set("已清空输入文件")

    def _apply_output_path(self) -> None:
        path = self._normalize_path_text(self.output_path_var.get())
        self.output_path_var.set(path)
        if path:
            resolved = self._resolve_path(path)
            self.last_output_dir = str(resolved.parent)
            self.status_var.set(f"已设置输出路径：{resolved}")
        else:
            self.status_var.set("已清空输出路径")

    def _choose_output(self) -> None:
        extension = ".xml"
        selected_format = self.format_var.get()
        selected_output_type = self.output_type_var.get()
        if selected_output_type == "txt":
            extension = ".txt"
        elif selected_format == "gm82":
            extension = ".timeline.gm82"
        path = filedialog.asksaveasfilename(
            title="选择输出文件",
            initialdir=self.last_output_dir,
            defaultextension=extension,
            filetypes=[("所有文件", "*.*")],
        )
        if path:
            self.last_output_dir = str(Path(path).resolve().parent)
            self.output_path_var.set(path)

    def _confirm_time_scale(self, prompt: str) -> str:
        return messagebox.askyesno("时间缩放", f"{prompt}\n\n选择“是”表示调整，选择“否”表示四舍五入。") and "" or "round"

    def _clear_result(self) -> None:
        self.result_text.delete("1.0", tk.END)

    def _append_result(self, text: str) -> None:
        if self.result_text.get("1.0", tk.END).strip():
            self.result_text.insert(tk.END, "\n\n")
        self.result_text.insert(tk.END, text)
        self.result_text.see(tk.END)

    def _ensure_output_file(self, output_path: str) -> str | None:
        resolved_output = self._resolve_path(output_path)
        if resolved_output.exists():
            return str(resolved_output)
        if not messagebox.askyesno("GMAM GUI", f"输出文件不存在：{resolved_output}\n\n是否新建该文件？"):
            self.status_var.set("已取消创建输出文件")
            return None
        try:
            resolved_output.parent.mkdir(parents=True, exist_ok=True)
            resolved_output.touch(exist_ok=True)
        except OSError as error:
            messagebox.showerror("GMAM GUI", f"新建输出文件失败：{error}")
            self.status_var.set("输出文件创建失败")
            return None
        self.status_var.set(f"已新建输出文件：{resolved_output}")
        return str(resolved_output)

    def _compile(self) -> None:
        if not self.input_files:
            messagebox.showerror("GMAM GUI", "请至少选择一个输入文件。")
            return

        selected_format = self.format_var.get()
        output_type = self.output_type_var.get()
        output_path = self._normalize_path_text(self.output_path_var.get())

        compiler = Compiler()
        try:
            resolved_inputs = [str(self._resolve_path(path)) for path in self.input_files]
            timeline = compiler.compile_files(
                resolved_inputs,
                time_scale=self.time_scale_var.get(),
                confirm=self._confirm_time_scale,
                output_format=output_type,
            )

            input_path = self._resolve_path(self.input_files[-1])
            output_source_path = input_path.with_suffix(".out")
            with output_source_path.open("w", encoding="utf-8", newline="\n") as stream:
                compiler.write_output_source(stream)

            messages = [f"已生成计算结果文件：{output_source_path}"]

            if compiler.scaled_source is not None:
                scaled_path = input_path.with_name(f"{input_path.stem}.scaled.tl")
                with scaled_path.open("w", encoding="utf-8", newline="\n") as stream:
                    compiler.write_scaled_source(stream)
                messages.append(f"已生成放缩后的源文件：{scaled_path}")

            if output_path:
                resolved_output = self._ensure_output_file(output_path)
                if resolved_output is None:
                    return
                if selected_format == "gms" and output_type == "step":
                    Compiler.inject_gms_step(timeline, resolved_output)
                elif selected_format == "gm82" and output_type == "step":
                    Compiler.inject_gm82_step(timeline, resolved_output)
                else:
                    with open(resolved_output, "w", encoding="utf-8", newline="\n") as stream:
                        Compiler.write_output(timeline, stream, selected_format, output_type)
                messages.append(f"已写入输出文件：{resolved_output}")
                self._save_settings()
            else:
                from io import StringIO

                stream = StringIO()
                Compiler.write_output(timeline, stream, selected_format, output_type)
                messages.append("\n===== 输出内容 =====\n")
                messages.append(stream.getvalue())

            self._save_settings()
            self._append_result("\n".join(messages))
            self.status_var.set("编译成功")
        except (CompileError, ValueError) as error:
            self._append_result(str(error))
            self.status_var.set("编译失败")
            messagebox.showerror("GMAM GUI", str(error))


def main() -> int:
    root = tk.Tk()
    GMAMGui(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
