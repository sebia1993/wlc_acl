from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .collector import collect_from_controller
from .diagnostics import classify_error_message, summarize_collection_failure
from .gui_support import GuiConnectionInput, build_target_from_gui_input, default_gui_output_dir
from .models import CollectionResult, CommandOutput
from .report import build_parsed_controllers, timestamp_slug, write_raw_result, write_reports
from .role_networks import RoleNetworkDefinitionError, load_role_network_definitions


class WlcRoleAclCollectorGui(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("WLC Role ACL Collector")
        self.configure(bg="#f4f7fb")
        self.geometry("1120x760")
        self.minsize(820, 560)

        self.event_queue: "queue.Queue[tuple[str, object]]" = queue.Queue()
        self.worker: threading.Thread | None = None
        self.is_running = False
        self.last_run_dir: Path | None = None
        self.last_html: Path | None = None
        self.last_xlsx: Path | None = None

        self.host_var = tk.StringVar()
        self.name_var = tk.StringVar()
        self.protocol_var = tk.StringVar(value="ssh")
        self.port_var = tk.StringVar(value="22")
        self.username_var = tk.StringVar()
        self.password_var = tk.StringVar()
        self.enable_password_var = tk.StringVar()
        self.output_dir_var = tk.StringVar(value=str(default_gui_output_dir()))
        self.role_networks_path_var = tk.StringVar()
        self.timeout_var = tk.IntVar(value=60)
        self.status_var = tk.StringVar(value="Ready")

        self._style()
        self._layout()
        self.protocol_var.trace_add("write", self._on_protocol_changed)
        self.after(150, self._drain_events)

    def _style(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(
            "Accent.TButton",
            font=("Segoe UI Semibold", 10),
            foreground="#ffffff",
            background="#0f6cbd",
            borderwidth=0,
            padding=(16, 10),
        )
        style.map("Accent.TButton", background=[("active", "#0d5ea8"), ("disabled", "#98a2b3")])
        style.configure(
            "Soft.TButton",
            font=("Segoe UI", 10),
            foreground="#15324b",
            background="#e5eef8",
            borderwidth=0,
            padding=(14, 9),
        )
        style.map("Soft.TButton", background=[("active", "#d7e5f4"), ("disabled", "#eef2f6")])
        style.configure("TLabel", background="#ffffff", foreground="#172033", font=("Segoe UI", 10))
        style.configure("Muted.TLabel", background="#ffffff", foreground="#667085", font=("Segoe UI", 9))
        style.configure("TEntry", padding=(8, 6))
        style.configure("TCombobox", padding=(8, 6))

    def _layout(self) -> None:
        root = tk.Frame(self, bg="#f4f7fb", padx=18, pady=18)
        root.pack(fill="both", expand=True)
        root.grid_columnconfigure(0, weight=1)
        root.grid_rowconfigure(1, weight=1)

        header = tk.Frame(root, bg="#143d66", padx=22, pady=18)
        header.grid(row=0, column=0, sticky="ew")
        tk.Label(
            header,
            text="WLC Role ACL Collector",
            bg="#143d66",
            fg="#ffffff",
            font=("Segoe UI Semibold", 20),
        ).pack(anchor="w")
        tk.Label(
            header,
            text="SSID 기본 Role과 Role별 ACL 접근 범위를 Excel/HTML 문서로 생성합니다.",
            bg="#143d66",
            fg="#d9e8f6",
            font=("Segoe UI", 10),
        ).pack(anchor="w", pady=(4, 0))

        body = tk.Frame(root, bg="#f4f7fb")
        body.grid(row=1, column=0, sticky="nsew", pady=(16, 0))
        body.grid_columnconfigure(0, weight=0, minsize=350)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        left = tk.Frame(body, bg="#ffffff", highlightbackground="#d0d5dd", highlightthickness=1)
        left.grid(row=0, column=0, sticky="ns")
        left.grid_rowconfigure(0, weight=1)
        left.grid_columnconfigure(0, weight=1)

        form = self._scrollable_form(left)

        self._section_label(form, "Controller")
        self._entry(form, "WLC IP/Hostname", self.host_var)
        self._entry(form, "Controller name", self.name_var, hint="미입력 시 wlc-IP 형식으로 자동 지정")
        self._protocol_row(form)

        self._section_label(form, "Login")
        self._entry(form, "Username", self.username_var)
        self._entry(form, "Password", self.password_var, show="*")
        self._entry(form, "Enable password", self.enable_password_var, show="*")

        self._section_label(form, "Output")
        output_row = tk.Frame(form, bg="#ffffff")
        output_row.pack(fill="x", pady=(4, 8))
        ttk.Entry(output_row, textvariable=self.output_dir_var, width=34).pack(side="left", fill="x", expand=True)
        ttk.Button(output_row, text="Browse", style="Soft.TButton", command=self._browse_output).pack(
            side="left", padx=(8, 0)
        )
        self._role_networks_row(form)
        self._timeout_row(form)

        right = tk.Frame(body, bg="#f4f7fb")
        right.grid(row=0, column=1, sticky="nsew", padx=(16, 0))
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(1, weight=1)

        status_panel = tk.Frame(right, bg="#ffffff", padx=16, pady=14, highlightbackground="#d0d5dd", highlightthickness=1)
        status_panel.grid(row=0, column=0, sticky="ew")
        tk.Label(status_panel, textvariable=self.status_var, bg="#ffffff", fg="#172033", font=("Segoe UI Semibold", 11)).pack(
            anchor="w"
        )
        self.progress = ttk.Progressbar(status_panel, mode="indeterminate")
        self.progress.pack(fill="x", pady=(10, 0))
        self._action_panel(status_panel)

        log_panel = tk.Frame(right, bg="#ffffff", padx=12, pady=12, highlightbackground="#d0d5dd", highlightthickness=1)
        log_panel.grid(row=1, column=0, sticky="nsew", pady=(14, 0))
        log_panel.grid_columnconfigure(0, weight=1)
        log_panel.grid_rowconfigure(1, weight=1)
        top = tk.Frame(log_panel, bg="#ffffff")
        top.grid(row=0, column=0, sticky="ew")
        tk.Label(top, text="Run Log", bg="#ffffff", fg="#172033", font=("Segoe UI Semibold", 11)).pack(side="left")
        ttk.Button(top, text="Clear", style="Soft.TButton", command=self._clear_log).pack(side="right")
        self.log_text = tk.Text(
            log_panel,
            height=20,
            wrap="word",
            bg="#0f1720",
            fg="#d7e2ef",
            insertbackground="#ffffff",
            relief="flat",
            padx=10,
            pady=10,
        )
        self.log_text.grid(row=1, column=0, sticky="nsew", pady=(10, 0))
        self.log_text.configure(state="disabled")

    def _action_panel(self, parent: tk.Widget) -> None:
        actions = tk.Frame(parent, bg="#ffffff")
        actions.pack(fill="x", pady=(12, 0))
        actions.grid_columnconfigure(0, weight=1)

        self.start_button = ttk.Button(actions, text="수집 시작", style="Accent.TButton", command=self._start_collection)
        self.start_button.grid(row=0, column=0, sticky="ew")

        outputs = tk.Frame(parent, bg="#ffffff")
        outputs.pack(fill="x", pady=(8, 0))
        outputs.grid_columnconfigure(0, weight=1, uniform="result_actions")
        outputs.grid_columnconfigure(1, weight=1, uniform="result_actions")
        outputs.grid_columnconfigure(2, weight=1, uniform="result_actions")

        self.open_folder_button = ttk.Button(
            outputs, text="결과 폴더", style="Soft.TButton", command=self._open_output_folder, state="disabled"
        )
        self.open_folder_button.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.open_html_button = ttk.Button(
            outputs, text="HTML", style="Soft.TButton", command=self._open_html, state="disabled"
        )
        self.open_html_button.grid(row=0, column=1, sticky="ew", padx=6)
        self.open_xlsx_button = ttk.Button(
            outputs, text="Excel", style="Soft.TButton", command=self._open_xlsx, state="disabled"
        )
        self.open_xlsx_button.grid(row=0, column=2, sticky="ew", padx=(6, 0))

    def _scrollable_form(self, parent: tk.Widget) -> tk.Frame:
        canvas = tk.Canvas(parent, bg="#ffffff", highlightthickness=0, width=348)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        form = tk.Frame(canvas, bg="#ffffff", padx=18, pady=18)
        form_window = canvas.create_window((0, 0), window=form, anchor="nw")

        def resize_scroll_region(_event: tk.Event) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))

        def resize_form(event: tk.Event) -> None:
            canvas.itemconfigure(form_window, width=event.width)

        form.bind("<Configure>", resize_scroll_region)
        canvas.bind("<Configure>", resize_form)
        canvas.bind("<MouseWheel>", lambda event: canvas.yview_scroll(int(-1 * (event.delta / 120)), "units"))
        form.bind("<MouseWheel>", lambda event: canvas.yview_scroll(int(-1 * (event.delta / 120)), "units"))
        return form

    def _section_label(self, parent: tk.Widget, text: str) -> None:
        tk.Label(parent, text=text, bg="#ffffff", fg="#0f6cbd", font=("Segoe UI Semibold", 11)).pack(anchor="w", pady=(8, 8))

    def _entry(self, parent: tk.Widget, label: str, variable: tk.StringVar, *, show: str = "", hint: str = "") -> None:
        row = tk.Frame(parent, bg="#ffffff")
        row.pack(fill="x", pady=(0, 8))
        tk.Label(row, text=label, bg="#ffffff", fg="#344054", font=("Segoe UI", 9)).pack(anchor="w")
        ttk.Entry(row, textvariable=variable, show=show, width=42).pack(fill="x", pady=(3, 0))
        if hint:
            ttk.Label(row, text=hint, style="Muted.TLabel", wraplength=295).pack(anchor="w", pady=(3, 0))

    def _protocol_row(self, parent: tk.Widget) -> None:
        row = tk.Frame(parent, bg="#ffffff")
        row.pack(fill="x", pady=(0, 8))
        left = tk.Frame(row, bg="#ffffff")
        left.pack(side="left", fill="x", expand=True)
        right = tk.Frame(row, bg="#ffffff")
        right.pack(side="left", fill="x", expand=True, padx=(8, 0))
        tk.Label(left, text="Protocol", bg="#ffffff", fg="#344054", font=("Segoe UI", 9)).pack(anchor="w")
        protocol = ttk.Combobox(left, textvariable=self.protocol_var, values=("ssh", "telnet"), state="readonly", width=16)
        protocol.pack(fill="x", pady=(3, 0))
        tk.Label(right, text="Port", bg="#ffffff", fg="#344054", font=("Segoe UI", 9)).pack(anchor="w")
        ttk.Entry(right, textvariable=self.port_var, width=16).pack(fill="x", pady=(3, 0))

    def _timeout_row(self, parent: tk.Widget) -> None:
        row = tk.Frame(parent, bg="#ffffff")
        row.pack(fill="x", pady=(0, 8))
        tk.Label(row, text="Timeout seconds", bg="#ffffff", fg="#344054", font=("Segoe UI", 9)).pack(anchor="w")
        ttk.Spinbox(row, from_=5, to=600, textvariable=self.timeout_var, width=12).pack(anchor="w", pady=(3, 0))

    def _role_networks_row(self, parent: tk.Widget) -> None:
        row = tk.Frame(parent, bg="#ffffff")
        row.pack(fill="x", pady=(0, 8))
        tk.Label(row, text="Role network Excel (session only)", bg="#ffffff", fg="#344054", font=("Segoe UI", 9)).pack(anchor="w")
        input_row = tk.Frame(row, bg="#ffffff")
        input_row.pack(fill="x", pady=(3, 0))
        ttk.Entry(input_row, textvariable=self.role_networks_path_var, width=34).pack(side="left", fill="x", expand=True)
        ttk.Button(input_row, text="Browse", style="Soft.TButton", command=self._browse_role_networks).pack(
            side="left", padx=(8, 0)
        )
        ttk.Label(
            row,
            text="Optional. Loaded for this run only. Local networks are not exported to HTML/Excel in secure mode.",
            style="Muted.TLabel",
            wraplength=295,
        ).pack(anchor="w", pady=(3, 0))

    def _on_protocol_changed(self, *_args: object) -> None:
        current = self.port_var.get().strip()
        protocol = self.protocol_var.get().strip().lower()
        if protocol == "telnet" and current in {"", "22"}:
            self.port_var.set("23")
        elif protocol == "ssh" and current in {"", "23"}:
            self.port_var.set("22")

    def _browse_output(self) -> None:
        selected = filedialog.askdirectory(initialdir=self.output_dir_var.get() or str(Path.cwd()))
        if selected:
            self.output_dir_var.set(selected)

    def _browse_role_networks(self) -> None:
        selected = filedialog.askopenfilename(
            title="Select Role network Excel",
            filetypes=(("Excel workbooks", "*.xlsx *.xlsm"),),
        )
        if selected:
            self.role_networks_path_var.set(selected)

    def _start_collection(self) -> None:
        if self.is_running:
            return
        try:
            target = build_target_from_gui_input(self._read_form())
            timeout = self._read_timeout()
        except ValueError as exc:
            messagebox.showerror("입력 오류", str(exc))
            return

        try:
            role_networks_path = self.role_networks_path_var.get().strip()
            role_networks = (
                load_role_network_definitions(Path(role_networks_path)) if role_networks_path else []
            )
        except RoleNetworkDefinitionError as exc:
            messagebox.showerror("Role network Excel error", str(exc))
            return

        output_dir = Path(self.output_dir_var.get().strip() or "outputs")
        self._set_running(True)
        self._log("Starting collection")
        self.worker = threading.Thread(
            target=self._run_collection_worker,
            args=(target, output_dir, timeout, role_networks),
            daemon=True,
        )
        self.worker.start()

    def _read_form(self) -> GuiConnectionInput:
        return GuiConnectionInput(
            host=self.host_var.get(),
            name=self.name_var.get(),
            protocol=self.protocol_var.get(),
            port=self.port_var.get(),
            username=self.username_var.get(),
            password=self.password_var.get(),
            enable_password=self.enable_password_var.get(),
        )

    def _read_timeout(self) -> int:
        try:
            return max(5, int(self.timeout_var.get()))
        except (tk.TclError, ValueError) as exc:
            raise ValueError("Timeout seconds must be a number.") from exc

    def _run_collection_worker(self, target, output_dir: Path, timeout: int, role_networks) -> None:
        run_dir = output_dir / timestamp_slug()
        log_lines = [
            "WLC Role ACL Collector run log",
            f"Controller: {target.controller.name}",
            f"Host: {target.controller.host}",
            f"Protocol: {target.controller.protocol}",
            f"Port: {target.controller.port}",
            f"Timeout seconds: {timeout}",
        ]
        if role_networks:
            log_lines.append(f"Role network Excel rows loaded for session only: {len(role_networks)}")

        def progress(event: str, payload: dict[str, object]) -> None:
            status, lines = format_collection_progress(event, payload)
            if status:
                self.event_queue.put(("status", status))
            for line in lines:
                log_lines.append(line)
                self.event_queue.put(("log", line))

        try:
            self.event_queue.put(("status", f"Connecting to {target.controller.host}"))
            self.event_queue.put(("log", f"Controller: {target.controller.name} ({target.controller.protocol}:{target.controller.port})"))
            if role_networks:
                self.event_queue.put(("log", f"Loaded local Role networks for this session only: {len(role_networks)} row(s)"))
            result = collect_from_controller(
                target.controller,
                timeout=timeout,
                credentials=target.credentials,
                progress_callback=progress,
            )
            write_raw_result(result, run_dir / "raw")
            self.event_queue.put(("log", f"Raw saved: {result.raw_file}"))
            log_lines.append(f"Raw file: {result.raw_file}")
            if not result.command_output("configuration_effective"):
                failure = summarize_collection_failure(result)
                log_lines.extend([f"Failure category: {failure.category}", failure.as_text()])
                run_log = _write_run_log(run_dir, log_lines)
                self.event_queue.put(
                    (
                        "error",
                        {
                            "message": _collection_failure_message(failure.as_text(), result, run_log),
                            "run_dir": run_dir,
                            "run_log": run_log,
                        },
                    )
                )
                return
            self.event_queue.put(("status", "Building reports"))
            self.event_queue.put(("log", "Building Excel/HTML reports"))
            log_lines.append("Building Excel/HTML reports")
            parsed = build_parsed_controllers([result])
            files = write_reports(
                parsed_controllers=parsed,
                collection_results=[result],
                output_dir=run_dir,
                local_role_networks=role_networks,
                export_local_role_networks=False,
                access_history_enabled=False,
            )
            log_lines.extend(["Status: completed", f"Excel: {files['xlsx']}", f"HTML: {files['html']}"])
            _write_run_log(run_dir, log_lines)
            payload = {"run_dir": run_dir, "html": files["html"], "xlsx": files["xlsx"]}
            self.event_queue.put(("done", payload))
        except Exception as exc:
            failure = classify_error_message(str(exc))
            log_lines.extend([f"Failure category: {failure.category}", failure.as_text()])
            run_log = _write_run_log(run_dir, log_lines)
            self.event_queue.put(
                (
                    "error",
                    {
                        "message": _collection_failure_message(failure.as_text(), None, run_log),
                        "run_dir": run_dir,
                        "run_log": run_log,
                    },
                )
            )

    def _drain_events(self) -> None:
        try:
            while True:
                event, payload = self.event_queue.get_nowait()
                if event == "status":
                    self.status_var.set(str(payload))
                elif event == "log":
                    self._log(str(payload))
                elif event == "done":
                    paths = payload
                    self.last_run_dir = paths["run_dir"]
                    self.last_html = paths["html"]
                    self.last_xlsx = paths["xlsx"]
                    self._log(f"Excel: {self.last_xlsx}")
                    self._log(f"HTML: {self.last_html}")
                    self.status_var.set("Completed")
                    self._set_running(False)
                    self._set_result_buttons(folder_enabled=True, report_enabled=True)
                    messagebox.showinfo("완료", "보고서 생성이 완료되었습니다.")
                elif event == "error":
                    if isinstance(payload, dict):
                        message = str(payload.get("message", "Collection failed"))
                        self.last_run_dir = payload.get("run_dir")
                        self.last_html = None
                        self.last_xlsx = None
                        self._log(f"ERROR: {message}")
                        if payload.get("run_log"):
                            self._log(f"Run log: {payload['run_log']}")
                        self._set_result_buttons(folder_enabled=bool(self.last_run_dir), report_enabled=False)
                    else:
                        message = str(payload)
                        self._log(f"ERROR: {message}")
                        self._set_result_buttons(folder_enabled=False, report_enabled=False)
                    self.status_var.set("Failed")
                    self._set_running(False)
                    messagebox.showerror("실행 오류", message)
        except queue.Empty:
            pass
        self.after(150, self._drain_events)

    def _set_running(self, running: bool) -> None:
        self.is_running = running
        self.start_button.configure(state="disabled" if running else "normal")
        if running:
            self.progress.start(10)
            self._set_result_buttons(folder_enabled=False, report_enabled=False)
        else:
            self.progress.stop()

    def _set_result_buttons(self, *, folder_enabled: bool, report_enabled: bool) -> None:
        self.open_folder_button.configure(state="normal" if folder_enabled else "disabled")
        self.open_html_button.configure(state="normal" if report_enabled else "disabled")
        self.open_xlsx_button.configure(state="normal" if report_enabled else "disabled")

    def _log(self, text: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"{text}\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _clear_log(self) -> None:
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def _open_output_folder(self) -> None:
        if self.last_run_dir:
            _open_path(self.last_run_dir)

    def _open_html(self) -> None:
        if self.last_html:
            _open_path(self.last_html)

    def _open_xlsx(self) -> None:
        if self.last_xlsx:
            _open_path(self.last_xlsx)


def format_collection_progress(event: str, payload: dict[str, object]) -> tuple[str, list[str]]:
    command = str(payload.get("command") or "")
    command_id = str(payload.get("command_id") or "")
    timeout = payload.get("timeout")
    role = str(payload.get("role") or "")
    alias = str(payload.get("alias") or "")
    index = payload.get("index")
    total = payload.get("total")

    if event == "connect":
        host = payload.get("host", "")
        protocol = payload.get("protocol", "")
        port = payload.get("port", "")
        return f"Connecting to {host}", [f"CONNECT: {host} ({protocol}:{port})"]
    if event == "connect_done":
        host = payload.get("host", "")
        return f"Login succeeded: {host}", [f"CONNECT OK: {host}"]
    if event == "command_start":
        if alias:
            status = f"Alias {index}/{total} 수집 중: {alias}"
        elif role:
            status = f"Role {index}/{total} 수집 중: {role}"
        else:
            status = f"{command} 실행 중... 최대 {timeout}초 대기"
        return status, [f"START: {command_id} | {command}"]
    if event == "command_done":
        size = payload.get("output_length", 0)
        if alias:
            status = f"Alias {index}/{total} 완료: {alias}"
        elif role:
            status = f"Role {index}/{total} 완료: {role}"
        else:
            status = f"{command} 완료"
        return status, [f"DONE: {command_id} | {command} | {size} chars"]
    if event == "command_error":
        error = payload.get("error", "")
        if alias:
            status = f"Alias {index}/{total} 실패: {alias}"
        elif role:
            status = f"Role {index}/{total} 실패: {role}"
        else:
            status = f"{command or command_id} 실패"
        return status, [f"ERROR: {command_id} | {command} | {error}"]
    if event == "aliases_discovered":
        total = payload.get("total", 0)
        return f"Alias {total}개 발견", [f"ALIASES: discovered {total} netdestination alias(es)"]
    if event == "roles_discovered":
        total = payload.get("total", 0)
        return f"Role {total}개 발견", [f"ROLES: discovered {total} role(s)"]
    if event == "complete":
        count = payload.get("command_count", 0)
        return "Collection commands completed", [f"COMMANDS COMPLETE: {count} command result(s)"]
    return "", []


def _collection_failure_message(base_message: str, result: CollectionResult | None, run_log: Path | None) -> str:
    parts = [base_message]
    failed_command = _primary_failed_command(result) if result is not None else None
    if failed_command is not None:
        parts.extend(
            [
                "",
                f"Failed command: {failed_command.command_id}",
                f"Command: {failed_command.command}",
            ]
        )
    if run_log is not None:
        parts.extend(["", f"Run log: {run_log}"])
    return "\n".join(parts)


def _primary_failed_command(result: CollectionResult | None) -> CommandOutput | None:
    if result is None:
        return None
    failed_commands = [command for command in result.commands if command.error]
    for command_id in ("connect", "configuration_effective"):
        for command in failed_commands:
            if command.command_id == command_id:
                return command
    return failed_commands[0] if failed_commands else None


def _open_path(path: Path) -> None:
    if sys.platform.startswith("win"):
        os.startfile(path)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])


def _write_run_log(run_dir: Path, lines: list[str]) -> Path:
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "run.log"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def main() -> None:
    app = WlcRoleAclCollectorGui()
    app.mainloop()


if __name__ == "__main__":
    main()
