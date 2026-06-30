"""Windows GUI entry point for non-CLI users.

The GUI collects connection details, starts the WLC collection in a background
thread, and writes reports without storing passwords.
"""

from __future__ import annotations

import ctypes
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .collector import collect_from_controller
from .diagnostic_mode import run_diagnostic
from .diagnostics import classify_error_message, summarize_collection_failure
from .gui_support import GuiConnectionInput, build_target_from_gui_input, default_gui_output_dir
from .models import CollectionResult, CommandOutput
from .report import build_parsed_controllers, timestamp_slug, write_raw_result, write_reports
from .role_networks import RoleNetworkDefinitionError, RoleNetworkLoadSummary, load_role_network_definitions_with_summary


DEFAULT_WINDOW_SIZE = (1080, 720)
MIN_WINDOW_SIZE = (760, 520)
WINDOW_MARGIN = 48
APP_BG = "#edf2f7"
PANEL_BG = "#ffffff"
PANEL_SUBTLE_BG = "#f8fafc"
LINE_COLOR = "#d5dde8"
LINE_STRONG_COLOR = "#b8c4d4"
TEXT_COLOR = "#172033"
MUTED_COLOR = "#667085"
ACCENT_COLOR = "#155eef"
ACCENT_ACTIVE_COLOR = "#0f4fd3"
ACCENT_DARK_COLOR = "#123c69"
ACCENT_SOFT_BG = "#eaf3ff"
SUCCESS_COLOR = "#067647"
SUCCESS_SOFT_BG = "#ecfdf3"
WARNING_COLOR = "#b54708"
WARNING_SOFT_BG = "#fffaeb"
DANGER_COLOR = "#b42318"
DANGER_SOFT_BG = "#fef3f2"
LOG_BG = "#0f172a"
LOG_TEXT = "#dbeafe"
LOG_MUTED = "#94a3b8"
LOG_INFO = "#93c5fd"
LOG_SUCCESS = "#86efac"
LOG_WARNING = "#fcd34d"
LOG_ERROR = "#fca5a5"
WLC_IP_LABEL = "WLC IP"
REPORT_NAME_LABEL = "보고서 이름(선택)"
WLC_TARGET_NOTICE = "Mobility Master(MM)가 아니라 실제 WLC 컨트롤러 IP를 입력하세요."
COLLECTION_ACTION_LABEL = "수집 시작"
DIAGNOSTIC_ACTION_LABEL = "안전 진단"
ADVANCED_OPTIONS_SHOW_LABEL = "고급 옵션 표시"
ADVANCED_OPTIONS_HIDE_LABEL = "고급 옵션 숨김"
LOG_SHOW_LABEL = "수집 로그 표시"
LOG_HIDE_LABEL = "수집 로그 숨김"
OPEN_HTML_LABEL = "HTML 보고서 열기"
OPEN_XLSX_LABEL = "Excel 열기"
OPEN_FOLDER_LABEL = "결과 폴더 열기"
ROLE_NETWORK_LABEL = "사내 Role 대역표"
ROLE_NETWORK_HELP = (
    "선택하면 내부용 HTML/Excel 보고서에 실제 Role 대역과 WLC 비교 상태를 표시합니다."
)
ROLE_NETWORK_EMPTY_STATUS = "선택 사항: 사내에서 관리하는 표준 Role 대역표(.xlsx/.xlsm)를 선택하세요."
ROLE_NETWORK_SELECT_LABEL = "파일 선택"
ROLE_NETWORK_GUIDE_LABEL = "작성법"
ROLE_NETWORK_TEMPLATE_LABEL = "샘플 열기"
ROLE_NETWORK_TEMPLATE_NAME = "role_networks.example.xlsx"
ROLE_NETWORK_GUIDE_TITLE = "사내 Role 대역표 작성법"
ROLE_NETWORK_GUIDE_TEXT = """사내 Role 대역표 작성법

Sheet 선택 기준
- Role_Networks Sheet가 있으면 Sheet 순서와 관계없이 그 Sheet를 우선 읽습니다.
- Role_Networks Sheet가 없을 때만 첫 번째 Sheet를 읽고 화면에 fallback 안내를 표시합니다.
- 작성가이드 같은 안내 Sheet가 첫 번째에 있어도 Role_Networks Sheet가 있으면 안내 Sheet는 읽지 않습니다.

필수 컬럼
- Role 이름: WLC에서 수집되는 Role 이름과 정확히 맞춰 작성합니다.
- 네트워크 대역: 10.40.1.0/24 같은 CIDR 형식을 권장합니다.

선택 컬럼
- 서브넷마스크: CIDR을 쓰지 않고 10.40.1.0처럼 네트워크 주소만 쓸 때 입력합니다.
- 설명, 소유부서, 비고, 마지막 확인일: 사내 관리용으로 자유롭게 입력합니다.

작성 예시
Role 이름        네트워크 대역       설명
guest-logon     10.30.0.0/24       게스트 무선
corp-employee   10.40.1.0/24       임직원 무선
corp-employee   10.40.2.0/24       임직원 무선 추가 대역

작성 규칙
- 같은 Role에 여러 대역이 있으면 Role 이름을 반복해서 여러 행으로 작성합니다.
- CIDR 형식을 쓰면 서브넷마스크는 비워도 됩니다.
- CIDR을 쓰지 않으면 서브넷마스크가 반드시 필요합니다.
- CSV, HTML, 구형 .xls 파일의 확장자만 .xlsx로 바꾸면 열 수 없습니다.
- Excel 임시 잠금 파일(~$로 시작하는 파일)은 선택하지 마세요.

보고서 반영
- 이 파일을 선택하면 생성되는 HTML/Excel은 내부망 전용 보고서가 됩니다.
- 보고서에는 실제 Role 대역, WLC 수집값과의 일치/불일치, 누락 상태가 표시됩니다.
- 회사 외부 공유 전에는 내부 대역 정보가 포함되어 있는지 반드시 확인하세요."""
STAGE_SEQUENCE = ("ready", "connecting", "collecting", "reporting", "completed")
STAGE_LABELS = {
    "ready": "준비",
    "connecting": "접속 중",
    "collecting": "수집 중",
    "reporting": "보고서 생성",
    "completed": "완료",
    "failed": "실패",
}
STAGE_PROGRESS = {
    "ready": 0,
    "connecting": 20,
    "collecting": 50,
    "reporting": 80,
    "completed": 100,
    "failed": 100,
}


def _enable_windows_dpi_awareness() -> None:
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def _window_work_area(window_id: int) -> tuple[int, int, int, int] | None:
    if sys.platform != "win32":
        return None

    class RECT(ctypes.Structure):
        _fields_ = [
            ("left", ctypes.c_long),
            ("top", ctypes.c_long),
            ("right", ctypes.c_long),
            ("bottom", ctypes.c_long),
        ]

    class MONITORINFO(ctypes.Structure):
        _fields_ = [
            ("cbSize", ctypes.c_ulong),
            ("rcMonitor", RECT),
            ("rcWork", RECT),
            ("dwFlags", ctypes.c_ulong),
        ]

    monitor_default_to_nearest = 2
    monitor = ctypes.windll.user32.MonitorFromWindow(int(window_id), monitor_default_to_nearest)
    if not monitor:
        return None
    info = MONITORINFO()
    info.cbSize = ctypes.sizeof(MONITORINFO)
    if not ctypes.windll.user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
        return None
    work = info.rcWork
    return work.left, work.top, work.right, work.bottom


def _constrain_window_rect(
    x: int,
    y: int,
    width: int,
    height: int,
    work_area: tuple[int, int, int, int],
    *,
    min_size: tuple[int, int] = MIN_WINDOW_SIZE,
) -> tuple[int, int, int, int]:
    left, top, right, bottom = work_area
    work_width = max(1, right - left)
    work_height = max(1, bottom - top)
    min_width = min(min_size[0], work_width)
    min_height = min(min_size[1], work_height)
    width = min(max(width, min_width), work_width)
    height = min(max(height, min_height), work_height)
    x = min(max(x, left), right - width)
    y = min(max(y, top), bottom - height)
    return x, y, width, height


class WlcRoleAclCollectorGui(tk.Tk):
    def __init__(self) -> None:
        _enable_windows_dpi_awareness()
        super().__init__()
        self.title("WLC Role ACL Collector")
        self.configure(bg=APP_BG)
        self.minsize(*MIN_WINDOW_SIZE)

        # Tkinter 화면은 메인 스레드에서만 안전하게 수정해야 합니다.
        # 백그라운드 수집 스레드는 event_queue에 메시지만 넣고, _drain_events가 화면을 갱신합니다.
        self.event_queue: "queue.Queue[tuple[str, object]]" = queue.Queue()
        self.worker: threading.Thread | None = None
        self.is_running = False
        self.advanced_options_visible = False
        self.log_visible = False
        self._fit_after_id: str | None = None
        self.stage_label_widgets: dict[str, tk.Label] = {}
        self.last_run_dir: Path | None = None
        self.last_html: Path | None = None
        self.last_xlsx: Path | None = None
        self.last_diagnostic_json: Path | None = None

        self.host_var = tk.StringVar()
        self.name_var = tk.StringVar()
        self.protocol_var = tk.StringVar(value="ssh")
        self.port_var = tk.StringVar(value="22")
        self.username_var = tk.StringVar()
        self.password_var = tk.StringVar()
        self.enable_password_var = tk.StringVar()
        self.output_dir_var = tk.StringVar(value=str(default_gui_output_dir()))
        self.role_networks_path_var = tk.StringVar()
        self.role_networks_status_var = tk.StringVar(value=ROLE_NETWORK_EMPTY_STATUS)
        self.timeout_var = tk.IntVar(value=60)
        self.status_var = tk.StringVar(value="준비되었습니다. 접속 정보를 입력한 뒤 수집을 시작하세요.")
        self.stage_var = tk.StringVar(value=STAGE_LABELS["ready"])

        self._style()
        self._set_initial_window_bounds()
        self._layout()
        self.protocol_var.trace_add("write", self._on_protocol_changed)
        self.bind("<Configure>", self._schedule_fit_to_monitor)
        self.after(300, self._fit_to_monitor)
        self.after(150, self._drain_events)

    def _style(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(
            "Accent.TButton",
            font=("Segoe UI Semibold", 10),
            foreground="#ffffff",
            background=ACCENT_COLOR,
            borderwidth=0,
            padding=(16, 10),
        )
        style.map("Accent.TButton", background=[("active", ACCENT_ACTIVE_COLOR), ("disabled", "#98a2b3")])
        style.configure(
            "Soft.TButton",
            font=("Segoe UI", 10),
            foreground=TEXT_COLOR,
            background="#e9eef5",
            borderwidth=0,
            padding=(14, 9),
        )
        style.map("Soft.TButton", background=[("active", "#dfe7f1"), ("disabled", "#f3f4f6")])
        style.configure("TLabel", background=PANEL_BG, foreground=TEXT_COLOR, font=("Segoe UI", 10))
        style.configure("Muted.TLabel", background=PANEL_BG, foreground=MUTED_COLOR, font=("Segoe UI", 9))
        style.configure("TEntry", padding=(9, 7), fieldbackground=PANEL_BG)
        style.configure("TCombobox", padding=(9, 7), fieldbackground=PANEL_BG)

    def _set_initial_window_bounds(self) -> None:
        work_area = _window_work_area(self.winfo_id())
        if work_area is None:
            self.geometry(f"{DEFAULT_WINDOW_SIZE[0]}x{DEFAULT_WINDOW_SIZE[1]}")
            return

        left, top, right, bottom = work_area
        work_width = right - left
        work_height = bottom - top
        self.minsize(min(MIN_WINDOW_SIZE[0], work_width), min(MIN_WINDOW_SIZE[1], work_height))
        width = min(DEFAULT_WINDOW_SIZE[0], max(min(MIN_WINDOW_SIZE[0], work_width), work_width - WINDOW_MARGIN))
        height = min(DEFAULT_WINDOW_SIZE[1], max(min(MIN_WINDOW_SIZE[1], work_height), work_height - WINDOW_MARGIN))
        x = left + max(0, (work_width - width) // 2)
        y = top + max(0, (work_height - height) // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")
        self.maxsize(work_width, work_height)

    def _schedule_fit_to_monitor(self, event: tk.Event | None = None) -> None:
        if event is not None and event.widget is not self:
            return
        if self._fit_after_id is not None:
            self.after_cancel(self._fit_after_id)
        self._fit_after_id = self.after(250, self._fit_to_monitor)

    def _fit_to_monitor(self) -> None:
        self._fit_after_id = None
        if self.state() == "iconic":
            return
        work_area = _window_work_area(self.winfo_id())
        if work_area is None:
            return
        left, top, right, bottom = work_area
        work_width = right - left
        work_height = bottom - top
        self.minsize(min(MIN_WINDOW_SIZE[0], work_width), min(MIN_WINDOW_SIZE[1], work_height))
        self.maxsize(work_width, work_height)
        x, y, width, height = _constrain_window_rect(
            self.winfo_x(),
            self.winfo_y(),
            self.winfo_width(),
            self.winfo_height(),
            work_area,
        )
        current = (self.winfo_x(), self.winfo_y(), self.winfo_width(), self.winfo_height())
        if current != (x, y, width, height):
            self.geometry(f"{width}x{height}+{x}+{y}")

    def _layout(self) -> None:
        root = tk.Frame(self, bg=APP_BG, padx=16, pady=16)
        root.pack(fill="both", expand=True)
        root.grid_columnconfigure(0, weight=1)
        root.grid_rowconfigure(1, weight=1)

        header = tk.Frame(root, bg=PANEL_BG, padx=18, pady=15, highlightbackground=LINE_COLOR, highlightthickness=1)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(0, weight=1)
        header.grid_columnconfigure(1, weight=0)
        tk.Label(
            header,
            text="WLC Role ACL Collector",
            bg=PANEL_BG,
            fg=TEXT_COLOR,
            font=("Segoe UI Semibold", 19),
        ).grid(row=0, column=0, sticky="w")
        tk.Label(
            header,
            text="접속 정보 입력, 수집 시작, 결과 확인 순서로 WLC Role ACL 보고서를 생성합니다.",
            bg=PANEL_BG,
            fg=MUTED_COLOR,
            font=("Segoe UI", 10),
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))
        badge_row = tk.Frame(header, bg=PANEL_BG)
        badge_row.grid(row=0, column=1, rowspan=2, sticky="e")
        self._pill(badge_row, "보안 모드", ACCENT_SOFT_BG, ACCENT_DARK_COLOR).pack(side="left", padx=(0, 7))
        self._pill(badge_row, "읽기 전용", SUCCESS_SOFT_BG, SUCCESS_COLOR).pack(side="left", padx=(0, 7))
        self._pill(badge_row, "AOS8 WLC", PANEL_SUBTLE_BG, TEXT_COLOR).pack(side="left")

        body = tk.Frame(root, bg=APP_BG)
        body.grid(row=1, column=0, sticky="nsew", pady=(14, 0))
        body.grid_columnconfigure(0, weight=0, minsize=336)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        left = tk.Frame(body, bg=PANEL_BG, highlightbackground=LINE_COLOR, highlightthickness=1)
        left.grid(row=0, column=0, sticky="ns")
        left.grid_rowconfigure(0, weight=1)
        left.grid_columnconfigure(0, weight=1)

        form = self._scrollable_form(left)

        self._section_label(form, "1. 접속 정보")
        self._notice(form, WLC_TARGET_NOTICE)
        self._entry(form, WLC_IP_LABEL, self.host_var)
        self._entry(form, REPORT_NAME_LABEL, self.name_var, hint="비워두면 wlc-IP 형식으로 자동 지정됩니다.")
        self._protocol_row(form)

        self._section_label(form, "2. 인증 정보")
        self._entry(form, "Username", self.username_var)
        self._entry(form, "Password", self.password_var, show="*")
        self._entry(form, "Enable password", self.enable_password_var, show="*")

        self._section_label(form, "3. 결과 저장")
        output_row = tk.Frame(form, bg=PANEL_BG)
        output_row.pack(fill="x", pady=(4, 8))
        ttk.Entry(output_row, textvariable=self.output_dir_var, width=34).pack(side="left", fill="x", expand=True)
        ttk.Button(output_row, text="폴더 선택", style="Soft.TButton", command=self._browse_output).pack(
            side="left", padx=(8, 0)
        )
        self.advanced_toggle_button = ttk.Button(
            form,
            text=ADVANCED_OPTIONS_SHOW_LABEL,
            style="Soft.TButton",
            command=self._toggle_advanced_options,
        )
        self.advanced_toggle_button.pack(fill="x", pady=(10, 0))
        self.advanced_options_container = tk.Frame(form, bg=PANEL_BG)
        self._section_label(self.advanced_options_container, "고급 옵션")
        self._role_networks_row(self.advanced_options_container)
        self._timeout_row(self.advanced_options_container)
        self._section_label(self.advanced_options_container, "문제 해결")
        ttk.Label(
            self.advanced_options_container,
            text="원본 장비 출력 없이 접속/명령 단계와 오류 코드만 확인할 때 사용합니다.",
            style="Muted.TLabel",
            wraplength=295,
        ).pack(anchor="w", pady=(0, 7))
        self.diagnostic_button = ttk.Button(
            self.advanced_options_container,
            text=DIAGNOSTIC_ACTION_LABEL,
            style="Soft.TButton",
            command=self._start_diagnostic,
        )
        self.diagnostic_button.pack(fill="x", pady=(0, 8))

        right = tk.Frame(body, bg=APP_BG)
        right.grid(row=0, column=1, sticky="nsew", padx=(14, 0))
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(1, weight=1)

        status_panel = tk.Frame(right, bg=PANEL_BG, padx=16, pady=14, highlightbackground=LINE_COLOR, highlightthickness=1)
        status_panel.grid(row=0, column=0, sticky="ew")
        self._status_panel(status_panel)
        self._action_panel(status_panel)

        self.log_panel = tk.Frame(right, bg=PANEL_BG, padx=12, pady=12, highlightbackground=LINE_COLOR, highlightthickness=1)
        self.log_panel.grid(row=1, column=0, sticky="nsew", pady=(12, 0))
        self.log_panel.grid_columnconfigure(0, weight=1)
        self.log_panel.grid_rowconfigure(1, weight=1)
        top = tk.Frame(self.log_panel, bg=PANEL_BG)
        top.grid(row=0, column=0, sticky="ew")
        tk.Label(top, text="수집 로그", bg=PANEL_BG, fg=TEXT_COLOR, font=("Segoe UI Semibold", 12)).pack(side="left")
        tk.Label(top, text="명령 실행 기록", bg=PANEL_BG, fg=MUTED_COLOR, font=("Segoe UI", 9)).pack(
            side="left", padx=(8, 0)
        )
        ttk.Button(top, text="지우기", style="Soft.TButton", command=self._clear_log).pack(side="right")
        self.log_text = tk.Text(
            self.log_panel,
            height=20,
            wrap="word",
            bg=LOG_BG,
            fg=LOG_TEXT,
            insertbackground=PANEL_BG,
            relief="flat",
            padx=10,
            pady=10,
        )
        self.log_text.grid(row=1, column=0, sticky="nsew", pady=(10, 0))
        self._configure_log_tags()
        self.log_text.configure(state="disabled")
        self._sync_advanced_options()
        self._sync_log_panel()

    def _pill(self, parent: tk.Widget, text: str, bg: str, fg: str) -> tk.Label:
        return tk.Label(
            parent,
            text=text,
            bg=bg,
            fg=fg,
            font=("Segoe UI Semibold", 9),
            padx=10,
            pady=5,
        )

    def _toggle_advanced_options(self) -> None:
        self.advanced_options_visible = not self.advanced_options_visible
        self._sync_advanced_options()

    def _sync_advanced_options(self) -> None:
        if self.advanced_options_visible:
            self.advanced_options_container.pack(fill="x", pady=(4, 0))
            self.advanced_toggle_button.configure(text=ADVANCED_OPTIONS_HIDE_LABEL)
        else:
            self.advanced_options_container.pack_forget()
            self.advanced_toggle_button.configure(text=ADVANCED_OPTIONS_SHOW_LABEL)

    def _toggle_log_panel(self) -> None:
        self.log_visible = not self.log_visible
        self._sync_log_panel()

    def _sync_log_panel(self) -> None:
        if self.log_visible:
            self.log_panel.grid()
            self.log_toggle_button.configure(text=LOG_HIDE_LABEL)
        else:
            self.log_panel.grid_remove()
            self.log_toggle_button.configure(text=LOG_SHOW_LABEL)

    def _status_panel(self, parent: tk.Widget) -> None:
        header = tk.Frame(parent, bg=PANEL_BG)
        header.pack(fill="x")
        tk.Label(header, text="수집 상태", bg=PANEL_BG, fg=TEXT_COLOR, font=("Segoe UI Semibold", 12)).pack(
            side="left"
        )
        tk.Label(
            header,
            textvariable=self.stage_var,
            bg=ACCENT_SOFT_BG,
            fg=ACCENT_DARK_COLOR,
            font=("Segoe UI Semibold", 9),
            padx=10,
            pady=5,
        ).pack(side="right")

        tk.Label(
            parent,
            textvariable=self.status_var,
            bg=PANEL_BG,
            fg=TEXT_COLOR,
            font=("Segoe UI Semibold", 11),
        ).pack(anchor="w", pady=(9, 0))

        stage_row = tk.Frame(parent, bg=PANEL_BG)
        stage_row.pack(fill="x", pady=(12, 0))
        for index, stage in enumerate(STAGE_SEQUENCE):
            stage_row.grid_columnconfigure(index, weight=1, uniform="stage")
            label = tk.Label(
                stage_row,
                text=STAGE_LABELS[stage],
                bg=PANEL_SUBTLE_BG,
                fg=MUTED_COLOR,
                font=("Segoe UI Semibold", 8),
                padx=7,
                pady=6,
                highlightbackground=LINE_COLOR,
                highlightthickness=1,
            )
            label.grid(row=0, column=index, sticky="ew", padx=(0 if index == 0 else 5, 0))
            self.stage_label_widgets[stage] = label
        self._set_stage("ready")

        self.progress = ttk.Progressbar(parent, mode="determinate", maximum=100)
        self.progress.pack(fill="x", pady=(12, 0))

        self.log_toggle_button = ttk.Button(
            parent,
            text=LOG_SHOW_LABEL,
            style="Soft.TButton",
            command=self._toggle_log_panel,
        )
        self.log_toggle_button.pack(anchor="w", pady=(10, 0))

    def _action_panel(self, parent: tk.Widget) -> None:
        tk.Label(parent, text="수집 실행", bg=PANEL_BG, fg=MUTED_COLOR, font=("Segoe UI Semibold", 9)).pack(
            anchor="w", pady=(13, 0)
        )
        actions = tk.Frame(parent, bg=PANEL_BG)
        actions.pack(fill="x", pady=(12, 0))
        actions.grid_columnconfigure(0, weight=1)

        self.start_button = ttk.Button(
            actions,
            text=COLLECTION_ACTION_LABEL,
            style="Accent.TButton",
            command=self._start_collection,
        )
        self.start_button.grid(row=0, column=0, sticky="ew")

        tk.Label(parent, text="결과 확인", bg=PANEL_BG, fg=MUTED_COLOR, font=("Segoe UI Semibold", 9)).pack(
            anchor="w", pady=(13, 0)
        )

        outputs = tk.Frame(parent, bg=PANEL_BG)
        outputs.pack(fill="x", pady=(9, 0))
        outputs.grid_columnconfigure(0, weight=1, uniform="result_actions")
        outputs.grid_columnconfigure(1, weight=1, uniform="result_actions")

        self.open_html_button = ttk.Button(
            outputs, text=OPEN_HTML_LABEL, style="Accent.TButton", command=self._open_html, state="disabled"
        )
        self.open_html_button.grid(row=0, column=0, columnspan=2, sticky="ew")
        self.open_xlsx_button = ttk.Button(
            outputs, text=OPEN_XLSX_LABEL, style="Soft.TButton", command=self._open_xlsx, state="disabled"
        )
        self.open_xlsx_button.grid(row=1, column=0, sticky="ew", padx=(0, 6), pady=(8, 0))
        self.open_folder_button = ttk.Button(
            outputs, text=OPEN_FOLDER_LABEL, style="Soft.TButton", command=self._open_output_folder, state="disabled"
        )
        self.open_folder_button.grid(row=1, column=1, sticky="ew", padx=(6, 0), pady=(8, 0))

    def _scrollable_form(self, parent: tk.Widget) -> tk.Frame:
        canvas = tk.Canvas(parent, bg=PANEL_BG, highlightthickness=0, width=336)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        form = tk.Frame(canvas, bg=PANEL_BG, padx=18, pady=16)
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
        container = tk.Frame(parent, bg=PANEL_BG)
        container.pack(fill="x", pady=(10, 8))
        tk.Label(
            container,
            text=text.upper(),
            bg=PANEL_BG,
            fg=ACCENT_DARK_COLOR,
            font=("Segoe UI Semibold", 9),
        ).pack(side="left")
        tk.Frame(container, bg=LINE_COLOR, height=1).pack(side="left", fill="x", expand=True, padx=(8, 0), pady=(8, 0))

    def _notice(self, parent: tk.Widget, text: str) -> None:
        frame = tk.Frame(parent, bg=WARNING_SOFT_BG, highlightbackground="#fedf89", highlightthickness=1)
        frame.pack(fill="x", pady=(0, 10))
        tk.Label(
            frame,
            text=text,
            bg=WARNING_SOFT_BG,
            fg=WARNING_COLOR,
            font=("Segoe UI Semibold", 9),
            justify="left",
            wraplength=280,
            padx=10,
            pady=8,
        ).pack(anchor="w", fill="x")

    def _entry(self, parent: tk.Widget, label: str, variable: tk.StringVar, *, show: str = "", hint: str = "") -> None:
        row = tk.Frame(parent, bg=PANEL_BG)
        row.pack(fill="x", pady=(0, 8))
        tk.Label(row, text=label, bg=PANEL_BG, fg="#344054", font=("Segoe UI", 9)).pack(anchor="w")
        ttk.Entry(row, textvariable=variable, show=show, width=42).pack(fill="x", pady=(3, 0))
        if hint:
            ttk.Label(row, text=hint, style="Muted.TLabel", wraplength=295).pack(anchor="w", pady=(3, 0))

    def _protocol_row(self, parent: tk.Widget) -> None:
        row = tk.Frame(parent, bg=PANEL_BG)
        row.pack(fill="x", pady=(0, 8))
        left = tk.Frame(row, bg=PANEL_BG)
        left.pack(side="left", fill="x", expand=True)
        right = tk.Frame(row, bg=PANEL_BG)
        right.pack(side="left", fill="x", expand=True, padx=(8, 0))
        tk.Label(left, text="Protocol", bg=PANEL_BG, fg="#344054", font=("Segoe UI", 9)).pack(anchor="w")
        protocol = ttk.Combobox(left, textvariable=self.protocol_var, values=("ssh", "telnet"), state="readonly", width=16)
        protocol.pack(fill="x", pady=(3, 0))
        tk.Label(right, text="Port", bg=PANEL_BG, fg="#344054", font=("Segoe UI", 9)).pack(anchor="w")
        ttk.Entry(right, textvariable=self.port_var, width=16).pack(fill="x", pady=(3, 0))

    def _timeout_row(self, parent: tk.Widget) -> None:
        row = tk.Frame(parent, bg=PANEL_BG)
        row.pack(fill="x", pady=(0, 8))
        tk.Label(row, text="Timeout seconds", bg=PANEL_BG, fg="#344054", font=("Segoe UI", 9)).pack(anchor="w")
        ttk.Spinbox(row, from_=5, to=600, textvariable=self.timeout_var, width=12).pack(anchor="w", pady=(3, 0))

    def _role_networks_row(self, parent: tk.Widget) -> None:
        row = tk.Frame(parent, bg=PANEL_BG)
        row.pack(fill="x", pady=(0, 8))
        tk.Label(row, text=ROLE_NETWORK_LABEL, bg=PANEL_BG, fg="#344054", font=("Segoe UI", 9)).pack(anchor="w")
        input_row = tk.Frame(row, bg=PANEL_BG)
        input_row.pack(fill="x", pady=(3, 0))
        ttk.Entry(input_row, textvariable=self.role_networks_path_var, width=34).pack(side="left", fill="x", expand=True)
        ttk.Button(input_row, text=ROLE_NETWORK_SELECT_LABEL, style="Soft.TButton", command=self._browse_role_networks).pack(
            side="left", padx=(8, 0)
        )
        help_row = tk.Frame(row, bg=PANEL_BG)
        help_row.pack(fill="x", pady=(6, 0))
        ttk.Button(
            help_row,
            text=ROLE_NETWORK_GUIDE_LABEL,
            style="Soft.TButton",
            command=self._show_role_network_guide,
        ).pack(side="left", fill="x", expand=True, padx=(0, 4))
        ttk.Button(
            help_row,
            text=ROLE_NETWORK_TEMPLATE_LABEL,
            style="Soft.TButton",
            command=self._open_role_network_template,
        ).pack(side="left", fill="x", expand=True, padx=(4, 0))
        ttk.Label(
            row,
            text=ROLE_NETWORK_HELP,
            style="Muted.TLabel",
            wraplength=295,
        ).pack(anchor="w", pady=(3, 0))
        ttk.Label(
            row,
            textvariable=self.role_networks_status_var,
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
            title="사내 Role 대역표 선택",
            filetypes=(("Excel workbooks", "*.xlsx *.xlsm"),),
        )
        if selected:
            self.role_networks_path_var.set(selected)
            try:
                self._load_role_networks_for_selected_path()
            except RoleNetworkDefinitionError as exc:
                self.role_networks_status_var.set(f"오류: {exc}")
                messagebox.showerror("Role 대역표 오류", str(exc))

    def _show_role_network_guide(self) -> None:
        window = tk.Toplevel(self)
        window.title(ROLE_NETWORK_GUIDE_TITLE)
        window.configure(bg=APP_BG)
        window.transient(self)
        window.minsize(560, 480)

        container = tk.Frame(window, bg=PANEL_BG, padx=16, pady=16)
        container.pack(fill="both", expand=True, padx=14, pady=14)
        tk.Label(
            container,
            text=ROLE_NETWORK_GUIDE_TITLE,
            bg=PANEL_BG,
            fg=TEXT_COLOR,
            font=("Segoe UI Semibold", 16),
        ).pack(anchor="w")
        tk.Label(
            container,
            text="샘플 Excel의 Role_Networks Sheet에 사내 기준 대역을 입력하세요. 해당 Sheet가 없으면 첫 번째 Sheet를 읽습니다.",
            bg=PANEL_BG,
            fg=MUTED_COLOR,
            font=("Segoe UI", 9),
            wraplength=500,
            justify="left",
        ).pack(anchor="w", pady=(3, 12))

        text_frame = tk.Frame(container, bg=PANEL_BG)
        text_frame.pack(fill="both", expand=True)
        scrollbar = ttk.Scrollbar(text_frame, orient="vertical")
        text = tk.Text(
            text_frame,
            wrap="word",
            bg="#ffffff",
            fg=TEXT_COLOR,
            relief="solid",
            borderwidth=1,
            padx=10,
            pady=10,
            height=18,
            yscrollcommand=scrollbar.set,
        )
        scrollbar.configure(command=text.yview)
        text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        text.insert("1.0", ROLE_NETWORK_GUIDE_TEXT)
        text.configure(state="disabled")

        actions = tk.Frame(container, bg=PANEL_BG)
        actions.pack(fill="x", pady=(12, 0))
        ttk.Button(
            actions,
            text=ROLE_NETWORK_TEMPLATE_LABEL,
            style="Soft.TButton",
            command=self._open_role_network_template,
        ).pack(side="left")
        ttk.Button(actions, text="닫기", style="Soft.TButton", command=window.destroy).pack(side="right")
        window.focus_set()

    def _open_role_network_template(self) -> None:
        template_path = _find_role_network_template()
        if template_path is None:
            messagebox.showerror(
                "샘플 대역표 없음",
                "config\\role_networks.example.xlsx 파일을 찾을 수 없습니다.\n"
                "배포 ZIP을 다시 확인하거나 config 폴더의 샘플 파일을 복원하세요.",
            )
            return
        _open_path(template_path)

    def _load_role_networks_for_selected_path(self):
        role_networks_path = self.role_networks_path_var.get().strip()
        if not role_networks_path:
            self.role_networks_status_var.set(ROLE_NETWORK_EMPTY_STATUS)
            return []
        summary = load_role_network_definitions_with_summary(Path(role_networks_path))
        self.role_networks_status_var.set(_role_networks_status_message(summary))
        return summary.definitions

    def _set_stage(self, stage: str) -> None:
        label = STAGE_LABELS.get(stage, STAGE_LABELS["ready"])
        self.stage_var.set(label)
        if hasattr(self, "progress"):
            self.progress.configure(value=STAGE_PROGRESS.get(stage, 0))
        active_index = STAGE_SEQUENCE.index(stage) if stage in STAGE_SEQUENCE else -1
        for index, step in enumerate(STAGE_SEQUENCE):
            widget = self.stage_label_widgets.get(step)
            if widget is None:
                continue
            if stage == "failed":
                widget.configure(bg=PANEL_SUBTLE_BG, fg=MUTED_COLOR, highlightbackground=LINE_COLOR)
            elif index < active_index:
                widget.configure(bg=SUCCESS_SOFT_BG, fg=SUCCESS_COLOR, highlightbackground="#abefc6")
            elif index == active_index:
                widget.configure(bg=ACCENT_SOFT_BG, fg=ACCENT_DARK_COLOR, highlightbackground="#b9dcff")
            else:
                widget.configure(bg=PANEL_SUBTLE_BG, fg=MUTED_COLOR, highlightbackground=LINE_COLOR)

    def _configure_log_tags(self) -> None:
        self.log_text.tag_configure("normal", foreground=LOG_TEXT)
        self.log_text.tag_configure("muted", foreground=LOG_MUTED)
        self.log_text.tag_configure("info", foreground=LOG_INFO)
        self.log_text.tag_configure("success", foreground=LOG_SUCCESS)
        self.log_text.tag_configure("warning", foreground=LOG_WARNING)
        self.log_text.tag_configure("error", foreground=LOG_ERROR)

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
            role_networks = self._load_role_networks_for_selected_path()
        except RoleNetworkDefinitionError as exc:
            messagebox.showerror("Role 대역표 오류", str(exc))
            return

        output_dir = Path(self.output_dir_var.get().strip() or "outputs")
        self._set_running(True)
        self._log("수집을 시작합니다.")
        self.worker = threading.Thread(
            target=self._run_collection_worker,
            args=(target, output_dir, timeout, role_networks),
            daemon=True,
        )
        self.worker.start()

    def _start_diagnostic(self) -> None:
        if self.is_running:
            return
        try:
            target = build_target_from_gui_input(self._read_form())
            timeout = self._read_timeout()
        except ValueError as exc:
            messagebox.showerror("입력 오류", str(exc))
            return

        output_dir = Path(self.output_dir_var.get().strip() or "outputs")
        self._set_running(True)
        self._log("안전 진단을 시작합니다.")
        self.worker = threading.Thread(
            target=self._run_diagnostic_worker,
            args=(target, output_dir, timeout),
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
            raise ValueError("Timeout seconds는 숫자로 입력하세요.") from exc

    def _run_collection_worker(self, target, output_dir: Path, timeout: int, role_networks) -> None:
        # 일반 수집 모드는 문제 분석을 위해 raw 명령 결과를 로컬 run_dir 아래에 저장합니다.
        # 단, user-table처럼 민감정보가 많은 출력은 report.py에서 원문 저장을 막습니다.
        run_dir = output_dir / timestamp_slug()
        log_lines = [
            "WLC Role ACL Collector run log",
            f"Controller: {target.controller.name}",
            f"WLC IP: {target.controller.host}",
            f"Protocol: {target.controller.protocol}",
            f"Port: {target.controller.port}",
            f"Timeout seconds: {timeout}",
        ]
        if role_networks:
            log_lines.append(f"Internal Role network rows loaded: {len(role_networks)}")

        def progress(event: str, payload: dict[str, object]) -> None:
            # collector.py의 진행 이벤트를 GUI 상태/로그 문구로 바꾸는 어댑터입니다.
            # 이 함수 안에서도 직접 위젯을 만지지 않고 queue에만 넣습니다.
            if event == "connect":
                self.event_queue.put(("stage", "connecting"))
            elif event in {"connect_done", "roles_discovered", "aliases_discovered", "command_start", "command_done"}:
                self.event_queue.put(("stage", "collecting"))
            status, lines = format_collection_progress(event, payload)
            if status:
                self.event_queue.put(("status", status))
            for line in lines:
                log_lines.append(line)
                self.event_queue.put(("log", line))

        try:
            self.event_queue.put(("status", f"{target.controller.host}에 접속 중입니다."))
            self.event_queue.put(("log", f"Controller: {target.controller.name} ({target.controller.protocol}:{target.controller.port})"))
            if role_networks:
                self.event_queue.put(("log", f"사내 Role 대역표 로드: {len(role_networks)}행"))
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
            self.event_queue.put(("stage", "reporting"))
            self.event_queue.put(("status", "HTML/Excel 보고서를 생성 중입니다."))
            self.event_queue.put(("log", "Building Excel/HTML reports"))
            log_lines.append("Building Excel/HTML reports")
            parsed = build_parsed_controllers([result])
            files = write_reports(
                parsed_controllers=parsed,
                collection_results=[result],
                output_dir=run_dir,
                local_role_networks=role_networks,
                export_local_role_networks=bool(role_networks),
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

    def _run_diagnostic_worker(self, target, output_dir: Path, timeout: int) -> None:
        try:
            # 안전 진단은 원본 장비 출력을 저장하지 않고 오류 코드와 단계만 남깁니다.
            # 회사 밖으로 공유해야 하는 상황에서는 이 결과만 전달하는 흐름을 의도합니다.
            self.event_queue.put(("stage", "connecting"))
            self.event_queue.put(("status", "안전 진단을 실행 중입니다."))
            self.event_queue.put(("log", "Safe diagnostic mode does not save raw device output."))
            diagnostic = run_diagnostic(target, output_root=output_dir, timeout=timeout)
            for line in format_diagnostic_progress(diagnostic.primary_code, diagnostic.report_paths, diagnostic.events):
                self.event_queue.put(("log", line))
            self.event_queue.put(
                (
                    "diagnostic_done",
                    {
                        "run_dir": diagnostic.run_dir,
                        "html": diagnostic.report_paths.get("html"),
                        "json": diagnostic.report_paths.get("json"),
                        "primary_code": diagnostic.primary_code,
                    },
                )
            )
        except Exception as exc:
            failure = classify_error_message(str(exc))
            self.event_queue.put(
                (
                    "error",
                    {
                        "message": failure.as_text(),
                        "run_dir": output_dir,
                        "run_log": None,
                    },
                )
            )

    def _drain_events(self) -> None:
        try:
            while True:
                event, payload = self.event_queue.get_nowait()
                if event == "status":
                    self.status_var.set(str(payload))
                elif event == "stage":
                    self._set_stage(str(payload))
                elif event == "log":
                    self._log(str(payload))
                elif event == "done":
                    paths = payload
                    self.last_run_dir = paths["run_dir"]
                    self.last_html = paths["html"]
                    self.last_xlsx = paths["xlsx"]
                    self._log(f"Excel: {self.last_xlsx}")
                    self._log(f"HTML: {self.last_html}")
                    self.status_var.set("완료되었습니다. HTML 보고서를 먼저 확인하세요.")
                    self._set_stage("completed")
                    self._set_running(False)
                    self._set_result_buttons(folder_enabled=True, report_enabled=True)
                    messagebox.showinfo("완료", "보고서 생성이 완료되었습니다.\nHTML 보고서를 먼저 확인하세요.")
                elif event == "diagnostic_done":
                    paths = payload
                    primary_code = str(paths.get("primary_code", "WLC-UNK-001"))
                    self.last_run_dir = paths["run_dir"]
                    self.last_html = paths.get("html")
                    self.last_xlsx = None
                    self.last_diagnostic_json = paths.get("json")
                    self.status_var.set(f"안전 진단 완료: {primary_code}")
                    self._set_stage("completed" if primary_code == "OK" else "failed")
                    self._set_running(False)
                    self._set_result_buttons(folder_enabled=True, report_enabled=True, xlsx_enabled=False)
                    message = (
                        f"안전 진단이 완료되었습니다.\nPrimary code: {primary_code}\n\n"
                        "외부 공유 시 primary code와 진단 요약 파일만 전달하세요."
                    )
                    if primary_code == "OK":
                        messagebox.showinfo("안전 진단 완료", message)
                    else:
                        messagebox.showwarning("안전 진단 코드 확인", message)
                elif event == "error":
                    self._set_stage("failed")
                    if isinstance(payload, dict):
                        message = str(payload.get("message", "수집에 실패했습니다."))
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
                    self.status_var.set("실패했습니다. 오류 메시지와 수집 로그를 확인하세요.")
                    self._set_running(False)
                    messagebox.showerror("실행 오류", message)
        except queue.Empty:
            pass
        self.after(150, self._drain_events)

    def _set_running(self, running: bool) -> None:
        self.is_running = running
        self.start_button.configure(state="disabled" if running else "normal")
        self.diagnostic_button.configure(state="disabled" if running else "normal")
        if running:
            self._set_stage("connecting")
            self._set_result_buttons(folder_enabled=False, report_enabled=False)
        else:
            if self.stage_var.get() not in {STAGE_LABELS["completed"], STAGE_LABELS["failed"]}:
                self._set_stage("ready")

    def _set_result_buttons(
        self,
        *,
        folder_enabled: bool,
        report_enabled: bool,
        xlsx_enabled: bool | None = None,
    ) -> None:
        if xlsx_enabled is None:
            xlsx_enabled = report_enabled
        self.open_folder_button.configure(state="normal" if folder_enabled else "disabled")
        self.open_html_button.configure(state="normal" if report_enabled else "disabled")
        self.open_xlsx_button.configure(state="normal" if xlsx_enabled else "disabled")

    def _log(self, text: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"{text}\n", (_log_tag_for_line(text),))
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


def _log_tag_for_line(text: str) -> str:
    normalized = text.strip().lower()
    if normalized.startswith("error:") or " failed" in normalized or normalized.startswith("failed"):
        return "error"
    if normalized.startswith("warning:"):
        return "warning"
    if normalized.startswith(
        ("done:", "connect ok:", "commands complete:", "excel:", "html:", "raw saved:", "diagnostic html:")
    ):
        return "success"
    if normalized.startswith(("connect:", "start:", "roles:", "aliases:", "diag:")) or "building" in normalized:
        return "info"
    if normalized.startswith(("run log:", "controller:", "wlc ip:", "protocol:", "port:", "timeout")):
        return "muted"
    return "normal"


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
        return f"{host}에 접속 중입니다.", [f"CONNECT: {host} ({protocol}:{port})"]
    if event == "connect_done":
        host = payload.get("host", "")
        return f"로그인 성공: {host}", [f"CONNECT OK: {host}"]
    if event == "command_start":
        if alias:
            status = f"Alias 수집 {index}/{total}: {alias}"
        elif role:
            status = f"Role 수집 {index}/{total}: {role}"
        else:
            status = f"{command} 실행 중입니다. 최대 {timeout}초 대기합니다."
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
        return "수집 명령이 완료되었습니다.", [f"COMMANDS COMPLETE: {count} command result(s)"]
    return "", []


def format_diagnostic_progress(primary_code: str, report_paths: dict[str, Path], events: list[object]) -> list[str]:
    lines = [f"Diagnostic primary code: {primary_code}"]
    for event in events:
        stage = getattr(event, "stage", "")
        status = getattr(event, "status", "")
        code = getattr(event, "code", "")
        command_id = getattr(event, "command_id", "")
        if code == "OK":
            code = ""
        parts = [part for part in (stage, status.upper(), code, command_id) if part]
        if parts:
            lines.append("DIAG: " + " | ".join(parts))
    if report_paths.get("json"):
        lines.append(f"Diagnostic JSON: {report_paths['json']}")
    if report_paths.get("html"):
        lines.append(f"Diagnostic HTML: {report_paths['html']}")
    return lines


def _collection_failure_message(base_message: str, result: CollectionResult | None, run_log: Path | None) -> str:
    parts = [base_message]
    failed_command = _primary_failed_command(result) if result is not None else None
    if failed_command is not None:
        parts.extend(
            [
                "",
                f"실패한 명령 ID: {failed_command.command_id}",
                f"명령어: {failed_command.command}",
            ]
        )
    if run_log is not None:
        parts.extend(["", f"Run log 위치: {run_log}"])
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


def _role_network_template_candidates() -> list[Path]:
    candidates: list[Path] = []
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).resolve().parent / "config" / ROLE_NETWORK_TEMPLATE_NAME)
    if hasattr(sys, "_MEIPASS"):
        candidates.append(Path(getattr(sys, "_MEIPASS")).resolve() / "config" / ROLE_NETWORK_TEMPLATE_NAME)
    candidates.extend(
        [
            Path.cwd() / "config" / ROLE_NETWORK_TEMPLATE_NAME,
            Path(__file__).resolve().parents[2] / "config" / ROLE_NETWORK_TEMPLATE_NAME,
        ]
    )

    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate)
        if key not in seen:
            unique.append(candidate)
            seen.add(key)
    return unique


def _find_role_network_template() -> Path | None:
    for candidate in _role_network_template_candidates():
        if candidate.exists():
            return candidate
    return None


def _role_networks_status_message(summary: RoleNetworkLoadSummary) -> str:
    duplicate_note = f" / 중복 {summary.duplicate_count}행 제외" if summary.duplicate_count else ""
    sheet_note = f" / Sheet: {summary.sheet_name}" if summary.sheet_name else ""
    message = f"로드됨: Role {summary.role_count}개 / 대역 {summary.network_count}개{duplicate_note}{sheet_note}."
    if summary.sheet_notice:
        message = f"{message} {summary.sheet_notice}"
    return f"{message} 이번 실행의 내부용 보고서에 표시됩니다."


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
