"""Windows GUI entry point for non-CLI users.

The GUI collects connection details, starts the WLC collection in a background
thread, and writes reports without storing passwords.
"""

from __future__ import annotations

import ctypes
import os
import queue
import re
import subprocess
import sys
import threading
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from .collector import collect_from_controller
from .diagnostic_mode import run_diagnostic
from .diagnostics import classify_error_message, summarize_collection_failure
from .gui_support import GuiConnectionInput, build_target_from_gui_input, default_gui_output_dir
from .models import CollectionResult, CommandOutput, ParsedController, RoleNetworkDefinition
from .report import build_parsed_controllers, timestamp_slug, write_raw_result, write_reports
from .role_networks import RoleNetworkDefinitionError, RoleNetworkLoadSummary, load_role_network_definitions_with_summary


APP_TITLE = "Aruba WLC Ops Analyzer v2.0"
CUSTOMTKINTER_APPEARANCE_MODE = "Dark"
CUSTOMTKINTER_COLOR_THEME = "blue"
DEFAULT_WINDOW_SIZE = (1100, 750)
MIN_WINDOW_SIZE = (820, 560)
WINDOW_MARGIN = 48
APP_BG = "#0b1120"
PANEL_BG = "#111827"
PANEL_SUBTLE_BG = "#172033"
CONTROL_BG = "#1f2937"
CONTROL_HOVER_BG = "#263244"
LINE_COLOR = "#2b3648"
LINE_STRONG_COLOR = "#3c4a60"
TEXT_COLOR = "#e5e7eb"
MUTED_COLOR = "#9ca3af"
ACCENT_COLOR = "#2563eb"
ACCENT_ACTIVE_COLOR = "#1d4ed8"
ACCENT_DARK_COLOR = "#bfdbfe"
ACCENT_SOFT_BG = "#1e3a8a"
RUN_ACTION_COLOR = "#28A745"
RUN_ACTION_HOVER_COLOR = "#218838"
SUCCESS_COLOR = "#86efac"
SUCCESS_SOFT_BG = "#14532d"
WARNING_COLOR = "#fcd34d"
WARNING_SOFT_BG = "#422006"
DANGER_COLOR = "#fca5a5"
DANGER_SOFT_BG = "#450a0a"
LOG_BG = "#151515"
LOG_TEXT = "#DCDCDC"
LOG_MUTED = "#9CA3AF"
LOG_INFO = "#60A5FA"
LOG_SUCCESS = "#4ADE80"
LOG_WARNING = "#FACC15"
LOG_ERROR = "#F87171"
LOG_FONT = ("Consolas", 12)
LOG_LEVEL_TAGS = {
    "[INFO]": "info",
    "[SUCCESS]": "success",
    "[ERROR]": "error",
    "[WARNING]": "warning",
}
LOG_LEVEL_PATTERN = re.compile(r"(\[(?:INFO|SUCCESS|ERROR|WARNING)\])")
SIDEBAR_BG = "#0f172a"
SIDEBAR_ACTIVE_BG = "#1d4ed8"
SIDEBAR_WIDTH = 244
SETTINGS_MENU_LABEL = "설정"
COLLECTION_MENU_LABEL = "수집 및 분석"
DIAGNOSTIC_LOG_MENU_LABEL = "진단 로그"
REPORT_MANAGEMENT_MENU_LABEL = "보고서 관리"
MENU_LABELS = (
    SETTINGS_MENU_LABEL,
    COLLECTION_MENU_LABEL,
    DIAGNOSTIC_LOG_MENU_LABEL,
    REPORT_MANAGEMENT_MENU_LABEL,
)
SSH_STATUS_LABEL = "SSH Status"

ctk.set_appearance_mode(CUSTOMTKINTER_APPEARANCE_MODE)
ctk.set_default_color_theme(CUSTOMTKINTER_COLOR_THEME)
WLC_IP_LABEL = "WLC IP"
REPORT_NAME_LABEL = "보고서 이름(선택)"
WLC_TARGET_NOTICE = "Mobility Master(MM)가 아니라 실제 WLC 컨트롤러 IP를 입력하세요."
COLLECTION_ACTION_LABEL = "분석 시작"
DIAGNOSTIC_ACTION_LABEL = "안전 진단"
ADVANCED_OPTIONS_SHOW_LABEL = "고급 옵션 표시"
ADVANCED_OPTIONS_HIDE_LABEL = "고급 옵션 숨김"
LOG_SHOW_LABEL = "수집 로그 표시"
LOG_HIDE_LABEL = "수집 로그 숨김"
OPEN_HTML_LABEL = "HTML 보고서 열기"
OPEN_XLSX_LABEL = "Excel 열기"
OPEN_FOLDER_LABEL = "결과 폴더 열기"
RESULT_FOLDER_ACTION_LABEL = "Excel 결과 폴더 열기"
RESULT_HTML_ACTION_TEXT = f"[HTML] {OPEN_HTML_LABEL}"
RESULT_FOLDER_ACTION_TEXT = f"[DIR] {RESULT_FOLDER_ACTION_LABEL}"
RESULT_XLSX_ACTION_TEXT = f"[XLSX] {OPEN_XLSX_LABEL}"
REPORT_COMPLETE_TITLE = "보고서 생성 완료"
REPORT_COMPLETE_MESSAGE = "보고서 생성이 완료되었습니다"
ROLE_NETWORK_LABEL = "사내 Role 대역표(Excel)"
ROLE_NETWORK_HELP = (
    "선택하면 내부용 HTML/Excel 보고서에 실제 Role 대역과 WLC 비교 상태를 표시합니다."
)
ROLE_NETWORK_EMPTY_STATUS = "선택 사항: 사내에서 관리하는 표준 Role 대역표(.xlsx/.xlsm)를 선택하세요."
ROLE_NETWORK_SELECT_LABEL = "찾아보기"
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


@dataclass(frozen=True)
class ResultReportSummary:
    ssid_count: int = 0
    role_count: int = 0
    matched_count: int = 0
    mismatched_count: int = 0
    note: str = "수집 완료 후 표시됩니다."


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


class WlcRoleAclCollectorGui(ctk.CTk):
    def __init__(self) -> None:
        _enable_windows_dpi_awareness()
        super().__init__()
        self.title(APP_TITLE)
        self.configure(fg_color=APP_BG)
        self.minsize(*MIN_WINDOW_SIZE)

        # Tkinter 화면은 메인 스레드에서만 안전하게 수정해야 합니다.
        # 백그라운드 수집 스레드는 event_queue에 메시지만 넣고, _drain_events가 화면을 갱신합니다.
        self.event_queue: "queue.Queue[tuple[str, object]]" = queue.Queue()
        self.worker: threading.Thread | None = None
        self.is_running = False
        self.advanced_options_visible = False
        self.log_visible = False
        self._fit_after_id: str | None = None
        self.stage_label_widgets: dict[str, ctk.CTkLabel] = {}
        self.sidebar_menu_buttons: dict[str, ctk.CTkButton] = {}
        self.start_buttons: list[ctk.CTkButton] = []
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
        self.ssh_status_var = tk.StringVar(value="대기")
        self.running_progress_title_var = tk.StringVar(value="데이터 수집 진행 중")
        self.result_ssid_count_var = tk.StringVar(value="0")
        self.result_role_count_var = tk.StringVar(value="0")
        self.result_matched_count_var = tk.StringVar(value="0")
        self.result_mismatched_count_var = tk.StringVar(value="0")
        self.result_summary_note_var = tk.StringVar(value="수집 완료 후 표시됩니다.")

        self._style()
        self._set_initial_window_bounds()
        self._layout()
        self.protocol_var.trace_add("write", self._on_protocol_changed)
        self.bind("<Configure>", self._schedule_fit_to_monitor)
        self.after(300, self._fit_to_monitor)
        self.after(150, self._drain_events)

    def _style(self) -> None:
        ctk.set_appearance_mode(CUSTOMTKINTER_APPEARANCE_MODE)
        ctk.set_default_color_theme(CUSTOMTKINTER_COLOR_THEME)

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
        root = ctk.CTkFrame(self, fg_color=APP_BG, corner_radius=0)
        root.pack(fill="both", expand=True, padx=16, pady=16)
        root.grid_columnconfigure(0, weight=0, minsize=SIDEBAR_WIDTH)
        root.grid_columnconfigure(1, weight=1)
        root.grid_rowconfigure(0, weight=1)

        sidebar = ctk.CTkFrame(
            root,
            fg_color=SIDEBAR_BG,
            border_width=1,
            border_color=LINE_COLOR,
            corner_radius=8,
            width=SIDEBAR_WIDTH,
        )
        sidebar.grid(row=0, column=0, sticky="ns")
        sidebar.grid_propagate(False)
        sidebar.grid_columnconfigure(0, weight=1)
        sidebar.grid_rowconfigure(1, weight=1)
        self._sidebar(sidebar)

        main = ctk.CTkFrame(root, fg_color=APP_BG, corner_radius=0)
        main.grid(row=0, column=1, sticky="nsew", padx=(14, 0))
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(1, weight=1)

        self._main_header(main)

        self.main_tabview = ctk.CTkTabview(
            main,
            fg_color=PANEL_BG,
            border_width=1,
            border_color=LINE_COLOR,
            segmented_button_fg_color=CONTROL_BG,
            segmented_button_selected_color=ACCENT_COLOR,
            segmented_button_selected_hover_color=ACCENT_ACTIVE_COLOR,
            segmented_button_unselected_color=CONTROL_BG,
            segmented_button_unselected_hover_color=CONTROL_HOVER_BG,
            text_color=TEXT_COLOR,
            command=self._on_main_tab_changed,
            anchor="w",
        )
        self.main_tabview.grid(row=1, column=0, sticky="nsew", pady=(14, 0))

        settings_tab = self.main_tabview.add(SETTINGS_MENU_LABEL)
        collection_tab = self.main_tabview.add(COLLECTION_MENU_LABEL)
        diagnostic_tab = self.main_tabview.add(DIAGNOSTIC_LOG_MENU_LABEL)
        report_tab = self.main_tabview.add(REPORT_MANAGEMENT_MENU_LABEL)
        for tab in (settings_tab, collection_tab, diagnostic_tab, report_tab):
            tab.configure(fg_color=PANEL_BG)
            tab.grid_columnconfigure(0, weight=1)
            tab.grid_rowconfigure(0, weight=1)

        self._build_settings_tab(settings_tab)
        self._build_collection_tab(collection_tab)
        self._build_diagnostic_tab(diagnostic_tab)
        self._build_report_tab(report_tab)
        self._bottom_progress_bar(main)
        self._sync_advanced_options()
        self._sync_log_panel()
        self._sync_running_progress(False)
        self._select_menu_tab(COLLECTION_MENU_LABEL)

    def _main_header(self, parent: tk.Widget) -> None:
        header = ctk.CTkFrame(parent, fg_color=PANEL_BG, border_width=1, border_color=LINE_COLOR, corner_radius=8)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(0, weight=1)
        header.grid_columnconfigure(1, weight=0)
        ctk.CTkLabel(
            header,
            text="Aruba WLC Ops Analyzer",
            text_color=TEXT_COLOR,
            font=("Segoe UI Semibold", 19),
            anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=18, pady=(16, 0))
        ctk.CTkLabel(
            header,
            text="접속 정보 입력, 분석 시작, 결과 확인 순서로 WLC Role ACL 보고서를 생성합니다.",
            text_color=MUTED_COLOR,
            font=("Segoe UI", 10),
            anchor="w",
        ).grid(row=1, column=0, sticky="w", padx=18, pady=(4, 16))
        badge_row = ctk.CTkFrame(header, fg_color="transparent")
        badge_row.grid(row=0, column=1, rowspan=2, sticky="e", padx=18)
        self._pill(badge_row, "보안 모드", ACCENT_SOFT_BG, ACCENT_DARK_COLOR).pack(side="left", padx=(0, 7))
        self._pill(badge_row, "읽기 전용", SUCCESS_SOFT_BG, SUCCESS_COLOR).pack(side="left", padx=(0, 7))
        self._pill(badge_row, "AOS8 WLC", PANEL_SUBTLE_BG, TEXT_COLOR).pack(side="left")

    def _sidebar(self, parent: tk.Widget) -> None:
        brand = ctk.CTkFrame(parent, fg_color="transparent")
        brand.grid(row=0, column=0, sticky="ew", padx=16, pady=(18, 14))
        brand.grid_columnconfigure(1, weight=1)
        logo = ctk.CTkLabel(
            brand,
            text="A",
            width=42,
            height=42,
            fg_color=ACCENT_COLOR,
            text_color="#ffffff",
            corner_radius=8,
            font=("Segoe UI Semibold", 20),
        )
        logo.grid(row=0, column=0, rowspan=2, sticky="w")
        ctk.CTkLabel(
            brand,
            text="Aruba WLC",
            text_color=TEXT_COLOR,
            font=("Segoe UI Semibold", 15),
            anchor="w",
        ).grid(row=0, column=1, sticky="ew", padx=(10, 0))
        ctk.CTkLabel(
            brand,
            text="Ops Analyzer v2.0",
            text_color=MUTED_COLOR,
            font=("Segoe UI", 10),
            anchor="w",
        ).grid(row=1, column=1, sticky="ew", padx=(10, 0), pady=(2, 0))

        nav = ctk.CTkFrame(parent, fg_color="transparent")
        nav.grid(row=1, column=0, sticky="new", padx=12, pady=(6, 0))
        nav.grid_columnconfigure(0, weight=1)
        for index, label in enumerate(MENU_LABELS):
            button = self._sidebar_button(nav, label)
            button.grid(row=index, column=0, sticky="ew", pady=(0, 8))
            self.sidebar_menu_buttons[label] = button

        status = ctk.CTkFrame(
            parent,
            fg_color=PANEL_SUBTLE_BG,
            border_width=1,
            border_color=LINE_COLOR,
            corner_radius=8,
        )
        status.grid(row=2, column=0, sticky="ew", padx=12, pady=(12, 14))
        status.grid_columnconfigure(1, weight=1)
        self.ssh_status_dot = ctk.CTkFrame(status, width=10, height=10, fg_color=MUTED_COLOR, corner_radius=5)
        self.ssh_status_dot.grid(row=0, column=0, sticky="w", padx=(12, 8), pady=12)
        self.ssh_status_dot.grid_propagate(False)
        text = ctk.CTkFrame(status, fg_color="transparent")
        text.grid(row=0, column=1, sticky="ew", pady=10)
        ctk.CTkLabel(
            text,
            text=SSH_STATUS_LABEL,
            text_color=MUTED_COLOR,
            font=("Segoe UI Semibold", 9),
            anchor="w",
        ).pack(anchor="w")
        ctk.CTkLabel(
            text,
            textvariable=self.ssh_status_var,
            text_color=TEXT_COLOR,
            font=("Segoe UI", 10),
            anchor="w",
        ).pack(anchor="w", pady=(2, 0))

    def _sidebar_button(self, parent: tk.Widget, label: str) -> ctk.CTkButton:
        return ctk.CTkButton(
            parent,
            text=label,
            command=lambda name=label: self._select_menu_tab(name),
            height=40,
            corner_radius=6,
            fg_color="transparent",
            hover_color=CONTROL_HOVER_BG,
            text_color=TEXT_COLOR,
            anchor="w",
            font=("Segoe UI Semibold", 11),
        )

    def _select_menu_tab(self, label: str) -> None:
        self.main_tabview.set(label)
        self._set_active_sidebar_menu(label)

    def _on_main_tab_changed(self) -> None:
        self._set_active_sidebar_menu(self.main_tabview.get())

    def _set_active_sidebar_menu(self, active_label: str) -> None:
        for label, button in self.sidebar_menu_buttons.items():
            if label == active_label:
                button.configure(fg_color=SIDEBAR_ACTIVE_BG, text_color="#ffffff")
            else:
                button.configure(fg_color="transparent", text_color=TEXT_COLOR)

    def _build_settings_tab(self, parent: tk.Widget) -> None:
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(0, weight=1)
        form = self._scrollable_form(parent)

        self._connection_settings_group(form)
        self._analysis_settings_group(form)
        self._output_settings_group(form)
        self._settings_run_group(form)

    def _settings_group_frame(self, parent: tk.Widget, title: str, description: str = "") -> ctk.CTkFrame:
        frame = ctk.CTkFrame(
            parent,
            fg_color=PANEL_SUBTLE_BG,
            border_width=1,
            border_color=LINE_COLOR,
            corner_radius=8,
        )
        frame.pack(fill="x", pady=(0, 14))
        frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            frame,
            text=title,
            text_color=TEXT_COLOR,
            font=("Segoe UI Semibold", 13),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=14, pady=(14, 0))
        if description:
            ctk.CTkLabel(
                frame,
                text=description,
                text_color=MUTED_COLOR,
                font=("Segoe UI", 9),
                wraplength=620,
                anchor="w",
                justify="left",
            ).grid(row=1, column=0, sticky="ew", padx=14, pady=(3, 10))
        return frame

    def _connection_settings_group(self, parent: tk.Widget) -> None:
        group = self._settings_group_frame(
            parent,
            "장비 접속 설정",
            "WLC 접속에 필요한 장비 주소와 인증 정보를 입력합니다.",
        )
        content = ctk.CTkFrame(group, fg_color="transparent")
        content.grid(row=2, column=0, sticky="ew", padx=14, pady=(0, 14))
        self._notice(content, WLC_TARGET_NOTICE)
        self._entry(content, WLC_IP_LABEL, self.host_var)
        self._entry(content, "계정", self.username_var)
        self._entry(content, "암호", self.password_var, show="*")

    def _analysis_settings_group(self, parent: tk.Widget) -> None:
        group = self._settings_group_frame(
            parent,
            "분석 옵션",
            "보고서 이름, 접속 방식, 내부 Role 대역표를 설정합니다.",
        )
        content = ctk.CTkFrame(group, fg_color="transparent")
        content.grid(row=2, column=0, sticky="ew", padx=14, pady=(0, 14))
        self._entry(content, REPORT_NAME_LABEL, self.name_var, hint="비워두면 wlc-IP 형식으로 자동 지정됩니다.")
        self._protocol_row(content)
        self._role_networks_row(content)

        self.advanced_toggle_button = self._button(
            content,
            text=ADVANCED_OPTIONS_SHOW_LABEL,
            command=self._toggle_advanced_options,
        )
        self.advanced_toggle_button.pack(fill="x", pady=(10, 0))
        self.advanced_options_container = ctk.CTkFrame(content, fg_color="transparent")
        self._section_label(self.advanced_options_container, "고급 옵션")
        self._entry(self.advanced_options_container, "Enable password", self.enable_password_var, show="*")
        self._timeout_row(self.advanced_options_container)

    def _output_settings_group(self, parent: tk.Widget) -> None:
        group = self._settings_group_frame(
            parent,
            "결과 저장",
            "분석 결과가 저장될 로컬 폴더를 선택합니다.",
        )
        content = ctk.CTkFrame(group, fg_color="transparent")
        content.grid(row=2, column=0, sticky="ew", padx=14, pady=(0, 14))
        output_row = ctk.CTkFrame(content, fg_color="transparent")
        output_row.pack(fill="x", pady=(4, 8))
        ctk.CTkEntry(output_row, textvariable=self.output_dir_var, height=34, corner_radius=6).pack(
            side="left", fill="x", expand=True
        )
        self._button(output_row, text="폴더 선택", command=self._browse_output).pack(side="left", padx=(8, 0))

    def _settings_run_group(self, parent: tk.Widget) -> None:
        group = self._settings_group_frame(
            parent,
            "실행",
            "입력한 설정으로 WLC Role ACL 분석을 시작합니다.",
        )
        content = ctk.CTkFrame(group, fg_color="transparent")
        content.grid(row=2, column=0, sticky="ew", padx=14, pady=(0, 14))
        content.grid_columnconfigure(0, weight=1)
        self._start_action_button(content).grid(row=0, column=0, sticky="ew")

    def _build_collection_tab(self, parent: tk.Widget) -> None:
        content = ctk.CTkFrame(parent, fg_color="transparent")
        content.grid(row=0, column=0, sticky="nsew", padx=18, pady=18)
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(1, weight=1)

        status_panel = ctk.CTkFrame(
            content,
            fg_color=PANEL_SUBTLE_BG,
            border_width=1,
            border_color=LINE_COLOR,
            corner_radius=8,
        )
        status_panel.grid(row=0, column=0, sticky="ew")
        self._status_panel(status_panel)
        self._collection_action_panel(status_panel)

        guide = ctk.CTkFrame(
            content,
            fg_color=LOG_BG,
            border_width=1,
            border_color=LINE_COLOR,
            corner_radius=8,
        )
        guide.grid(row=1, column=0, sticky="nsew", pady=(14, 0))
        guide.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            guide,
            text="수집 및 분석 작업 영역",
            text_color=TEXT_COLOR,
            font=("Segoe UI Semibold", 14),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 4))
        ctk.CTkLabel(
            guide,
            text="설정 탭에서 WLC 접속 정보와 사내 Role 대역표를 준비한 뒤 수집을 시작하세요. 진행 단계와 결과 상태는 이 화면에서 추적합니다.",
            text_color=MUTED_COLOR,
            font=("Segoe UI", 10),
            wraplength=680,
            justify="left",
            anchor="w",
        ).grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 16))

    def _build_diagnostic_tab(self, parent: tk.Widget) -> None:
        content = ctk.CTkFrame(parent, fg_color="transparent")
        content.grid(row=0, column=0, sticky="nsew", padx=18, pady=18)
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(1, weight=1)

        diagnostic_panel = ctk.CTkFrame(
            content,
            fg_color=PANEL_SUBTLE_BG,
            border_width=1,
            border_color=LINE_COLOR,
            corner_radius=8,
        )
        diagnostic_panel.grid(row=0, column=0, sticky="ew")
        diagnostic_panel.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            diagnostic_panel,
            text="안전 진단",
            text_color=TEXT_COLOR,
            font=("Segoe UI Semibold", 13),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 0))
        ctk.CTkLabel(
            diagnostic_panel,
            text="원본 장비 출력 없이 접속/명령 단계와 오류 코드만 확인할 때 사용합니다.",
            text_color=MUTED_COLOR,
            font=("Segoe UI", 10),
            wraplength=680,
            justify="left",
            anchor="w",
        ).grid(row=1, column=0, sticky="ew", padx=16, pady=(4, 10))
        self.diagnostic_button = self._button(
            diagnostic_panel,
            text=DIAGNOSTIC_ACTION_LABEL,
            command=self._start_diagnostic,
        )
        self.diagnostic_button.grid(row=2, column=0, sticky="w", padx=16, pady=(0, 14))

        self.log_panel = ctk.CTkFrame(
            content,
            fg_color=LOG_BG,
            border_width=1,
            border_color=LINE_COLOR,
            corner_radius=8,
        )
        self.log_panel.grid(row=1, column=0, sticky="nsew", pady=(14, 0))
        self.log_panel.grid_columnconfigure(0, weight=1)
        self.log_panel.grid_rowconfigure(1, weight=1)
        top = ctk.CTkFrame(self.log_panel, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=14, pady=(14, 0))
        ctk.CTkLabel(top, text="수집 로그", text_color=TEXT_COLOR, font=("Segoe UI Semibold", 12)).pack(side="left")
        ctk.CTkLabel(top, text="명령 실행 기록", text_color=MUTED_COLOR, font=("Segoe UI", 9)).pack(
            side="left", padx=(8, 0)
        )
        self._button(top, text="지우기", command=self._clear_log).pack(side="right")
        self.log_text = ctk.CTkTextbox(
            self.log_panel,
            height=20,
            wrap="word",
            fg_color=LOG_BG,
            text_color=LOG_TEXT,
            border_width=1,
            border_color=LINE_COLOR,
            corner_radius=8,
            font=LOG_FONT,
        )
        self.log_text.grid(row=1, column=0, sticky="nsew", padx=14, pady=(10, 14))
        self._configure_log_tags()
        self.log_text.configure(state="disabled")

    def _build_report_tab(self, parent: tk.Widget) -> None:
        content = ctk.CTkFrame(parent, fg_color="transparent")
        content.grid(row=0, column=0, sticky="nsew", padx=18, pady=18)
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(1, weight=1)

        report_panel = ctk.CTkFrame(
            content,
            fg_color=PANEL_SUBTLE_BG,
            border_width=1,
            border_color=LINE_COLOR,
            corner_radius=8,
        )
        report_panel.grid(row=0, column=0, sticky="ew")
        self._report_panel(report_panel)

        detail = ctk.CTkFrame(
            content,
            fg_color=LOG_BG,
            border_width=1,
            border_color=LINE_COLOR,
            corner_radius=8,
        )
        detail.grid(row=1, column=0, sticky="nsew", pady=(14, 0))
        detail.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            detail,
            text="보고서 관리 작업 영역",
            text_color=TEXT_COLOR,
            font=("Segoe UI Semibold", 14),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 4))
        ctk.CTkLabel(
            detail,
            text="수집 또는 안전 진단이 완료되면 HTML, Excel, 결과 폴더 버튼이 활성화됩니다. 외부 공유 전에는 내부 Role 대역 정보 포함 여부를 확인하세요.",
            text_color=MUTED_COLOR,
            font=("Segoe UI", 10),
            wraplength=680,
            justify="left",
            anchor="w",
        ).grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 16))

    def _pill(self, parent: tk.Widget, text: str, bg: str, fg: str) -> ctk.CTkLabel:
        return ctk.CTkLabel(
            parent,
            text=text,
            fg_color=bg,
            text_color=fg,
            font=("Segoe UI Semibold", 9),
            height=34,
            corner_radius=6,
        )

    def _button(
        self,
        parent: tk.Widget,
        *,
        text: str,
        command=None,
        variant: str = "secondary",
        state: str = "normal",
    ) -> ctk.CTkButton:
        if variant == "run":
            return ctk.CTkButton(
                parent,
                text=text,
                command=command,
                state=state,
                height=44,
                corner_radius=6,
                fg_color=RUN_ACTION_COLOR,
                hover_color=RUN_ACTION_HOVER_COLOR,
                text_color="#ffffff",
                font=("Segoe UI Semibold", 12),
            )
        if variant == "primary":
            return ctk.CTkButton(
                parent,
                text=text,
                command=command,
                state=state,
                height=38,
                corner_radius=6,
                fg_color=ACCENT_COLOR,
                hover_color=ACCENT_ACTIVE_COLOR,
                text_color="#ffffff",
                font=("Segoe UI Semibold", 10),
            )
        return ctk.CTkButton(
            parent,
            text=text,
            command=command,
            state=state,
            height=36,
            corner_radius=6,
            fg_color=CONTROL_BG,
            hover_color=CONTROL_HOVER_BG,
            text_color=TEXT_COLOR,
            text_color_disabled="#6b7280",
            font=("Segoe UI", 10),
        )

    def _bottom_progress_bar(self, parent: tk.Widget) -> None:
        self.running_progress_panel = ctk.CTkFrame(
            parent,
            fg_color=PANEL_SUBTLE_BG,
            border_width=1,
            border_color=LINE_COLOR,
            corner_radius=8,
        )
        self.running_progress_panel.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        self.running_progress_panel.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(self.running_progress_panel, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=14, pady=(10, 5))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            header,
            textvariable=self.running_progress_title_var,
            text_color=TEXT_COLOR,
            font=("Segoe UI Semibold", 10),
            anchor="w",
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            header,
            textvariable=self.stage_var,
            text_color=ACCENT_DARK_COLOR,
            font=("Segoe UI Semibold", 9),
            anchor="e",
        ).grid(row=0, column=1, sticky="e")

        self.running_progress = ctk.CTkProgressBar(
            self.running_progress_panel,
            height=12,
            corner_radius=6,
            fg_color=CONTROL_BG,
            progress_color=RUN_ACTION_COLOR,
            mode="determinate",
        )
        self.running_progress.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 12))
        self.running_progress.set(0)
        self.running_progress_panel.grid_remove()

    def _sync_running_progress(self, running: bool) -> None:
        if not hasattr(self, "running_progress_panel"):
            return
        if running:
            self.running_progress_panel.grid()
        else:
            self.running_progress_panel.grid_remove()

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
        self.log_visible = True
        self._select_menu_tab(DIAGNOSTIC_LOG_MENU_LABEL)
        self._sync_log_panel()

    def _sync_log_panel(self) -> None:
        if hasattr(self, "log_toggle_button"):
            self.log_toggle_button.configure(text=LOG_SHOW_LABEL)

    def _status_panel(self, parent: tk.Widget) -> None:
        header = ctk.CTkFrame(parent, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(14, 0))
        ctk.CTkLabel(header, text="수집 상태", text_color=TEXT_COLOR, font=("Segoe UI Semibold", 12)).pack(
            side="left"
        )
        ctk.CTkLabel(
            header,
            textvariable=self.stage_var,
            fg_color=ACCENT_SOFT_BG,
            text_color=ACCENT_DARK_COLOR,
            font=("Segoe UI Semibold", 9),
            height=32,
            corner_radius=6,
        ).pack(side="right")

        ctk.CTkLabel(
            parent,
            textvariable=self.status_var,
            text_color=TEXT_COLOR,
            font=("Segoe UI Semibold", 11),
            anchor="w",
            justify="left",
        ).pack(anchor="w", fill="x", padx=16, pady=(9, 0))

        stage_row = ctk.CTkFrame(parent, fg_color="transparent")
        stage_row.pack(fill="x", padx=16, pady=(12, 0))
        for index, stage in enumerate(STAGE_SEQUENCE):
            stage_row.grid_columnconfigure(index, weight=1, uniform="stage")
            label = ctk.CTkLabel(
                stage_row,
                text=STAGE_LABELS[stage],
                fg_color=PANEL_SUBTLE_BG,
                text_color=MUTED_COLOR,
                font=("Segoe UI Semibold", 8),
                height=34,
                corner_radius=6,
            )
            label.grid(row=0, column=index, sticky="ew", padx=(0 if index == 0 else 5, 0))
            self.stage_label_widgets[stage] = label
        self._set_stage("ready")

        self.progress = ctk.CTkProgressBar(
            parent,
            height=12,
            corner_radius=6,
            fg_color=CONTROL_BG,
            progress_color=ACCENT_COLOR,
            mode="determinate",
        )
        self.progress.pack(fill="x", padx=16, pady=(12, 0))
        self.progress.set(0)

        self.log_toggle_button = self._button(
            parent,
            text=LOG_SHOW_LABEL,
            command=self._toggle_log_panel,
        )
        self.log_toggle_button.pack(anchor="w", padx=16, pady=(10, 0))

    def _collection_action_panel(self, parent: tk.Widget) -> None:
        ctk.CTkLabel(parent, text="수집 실행", text_color=MUTED_COLOR, font=("Segoe UI Semibold", 9)).pack(
            anchor="w", padx=16, pady=(13, 0)
        )
        actions = ctk.CTkFrame(parent, fg_color="transparent")
        actions.pack(fill="x", padx=16, pady=(12, 0))
        actions.grid_columnconfigure(0, weight=1)

        self._start_action_button(actions).grid(row=0, column=0, sticky="ew")

    def _start_action_button(self, parent: tk.Widget) -> ctk.CTkButton:
        button = self._button(
            parent,
            text=COLLECTION_ACTION_LABEL,
            variant="run",
            command=self._start_collection,
        )
        self.start_buttons.append(button)
        self.start_button = button
        return button

    def _report_panel(self, parent: tk.Widget) -> None:
        ctk.CTkLabel(parent, text="결과 보고서 확인", text_color=TEXT_COLOR, font=("Segoe UI Semibold", 13)).pack(
            anchor="w", padx=16, pady=(14, 0)
        )
        ctk.CTkLabel(
            parent,
            text="마지막 수집 결과의 핵심 수치를 확인하고 HTML 보고서 또는 Excel 결과 폴더를 바로 엽니다.",
            text_color=MUTED_COLOR,
            font=("Segoe UI", 10),
            anchor="w",
            justify="left",
        ).pack(anchor="w", fill="x", padx=16, pady=(4, 0))

        cards = ctk.CTkFrame(parent, fg_color="transparent")
        cards.pack(fill="x", padx=16, pady=(14, 0))
        for column in range(4):
            cards.grid_columnconfigure(column, weight=1, uniform="result_summary")
        self._result_summary_card(
            cards,
            title="SSID",
            value_var=self.result_ssid_count_var,
            caption="수집된 SSID",
            accent_color=ACCENT_DARK_COLOR,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self._result_summary_card(
            cards,
            title="Role",
            value_var=self.result_role_count_var,
            caption="수집된 Role",
            accent_color=TEXT_COLOR,
        ).grid(row=0, column=1, sticky="ew", padx=6)
        self._result_summary_card(
            cards,
            title="일치",
            value_var=self.result_matched_count_var,
            caption="대역표 기준",
            accent_color=SUCCESS_COLOR,
        ).grid(row=0, column=2, sticky="ew", padx=6)
        self._result_summary_card(
            cards,
            title="불일치",
            value_var=self.result_mismatched_count_var,
            caption="누락 포함",
            accent_color=WARNING_COLOR,
        ).grid(row=0, column=3, sticky="ew", padx=(6, 0))

        ctk.CTkLabel(
            parent,
            textvariable=self.result_summary_note_var,
            text_color=MUTED_COLOR,
            font=("Segoe UI", 9),
            anchor="w",
            justify="left",
            wraplength=720,
        ).pack(anchor="w", fill="x", padx=16, pady=(8, 0))

        ctk.CTkLabel(parent, text="보고서 바로 열기", text_color=MUTED_COLOR, font=("Segoe UI Semibold", 9)).pack(
            anchor="w", padx=16, pady=(16, 0)
        )

        outputs = ctk.CTkFrame(parent, fg_color="transparent")
        outputs.pack(fill="x", padx=16, pady=(9, 16))
        outputs.grid_columnconfigure(0, weight=1, uniform="result_actions")
        outputs.grid_columnconfigure(1, weight=1, uniform="result_actions")

        self.open_html_button = self._result_action_button(
            outputs,
            text=RESULT_HTML_ACTION_TEXT,
            command=self._open_html,
            state="disabled",
            variant="primary",
        )
        self.open_html_button.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.open_folder_button = self._result_action_button(
            outputs,
            text=RESULT_FOLDER_ACTION_TEXT,
            command=self._open_output_folder,
            state="disabled",
            variant="folder",
        )
        self.open_folder_button.grid(row=0, column=1, sticky="ew", padx=(6, 0))
        self.open_xlsx_button = self._button(
            outputs,
            text=RESULT_XLSX_ACTION_TEXT,
            command=self._open_xlsx,
            state="disabled",
        )
        self.open_xlsx_button.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))

    def _result_summary_card(
        self,
        parent: tk.Widget,
        *,
        title: str,
        value_var: tk.StringVar,
        caption: str,
        accent_color: str,
    ) -> ctk.CTkFrame:
        card = ctk.CTkFrame(
            parent,
            fg_color=CONTROL_BG,
            border_width=1,
            border_color=LINE_STRONG_COLOR,
            corner_radius=8,
        )
        card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            card,
            text=title,
            text_color=MUTED_COLOR,
            font=("Segoe UI Semibold", 9),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 0))
        ctk.CTkLabel(
            card,
            textvariable=value_var,
            text_color=accent_color,
            font=("Segoe UI Semibold", 24),
            anchor="w",
        ).grid(row=1, column=0, sticky="ew", padx=12, pady=(2, 0))
        ctk.CTkLabel(
            card,
            text=caption,
            text_color=MUTED_COLOR,
            font=("Segoe UI", 9),
            anchor="w",
        ).grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 10))
        return card

    def _result_action_button(
        self,
        parent: tk.Widget,
        *,
        text: str,
        command=None,
        state: str = "normal",
        variant: str = "primary",
    ) -> ctk.CTkButton:
        if variant == "primary":
            fg_color = ACCENT_COLOR
            hover_color = ACCENT_ACTIVE_COLOR
        else:
            fg_color = CONTROL_BG
            hover_color = CONTROL_HOVER_BG
        return ctk.CTkButton(
            parent,
            text=text,
            command=command,
            state=state,
            height=58,
            corner_radius=8,
            fg_color=fg_color,
            hover_color=hover_color,
            text_color="#ffffff" if variant == "primary" else TEXT_COLOR,
            text_color_disabled="#6b7280",
            font=("Segoe UI Semibold", 13),
        )

    def _scrollable_form(self, parent: tk.Widget) -> ctk.CTkScrollableFrame:
        form = ctk.CTkScrollableFrame(
            parent,
            fg_color=PANEL_BG,
            scrollbar_button_color=CONTROL_BG,
            scrollbar_button_hover_color=CONTROL_HOVER_BG,
            corner_radius=0,
            width=338,
        )
        form.grid(row=0, column=0, sticky="nsew", padx=14, pady=14)
        form.grid_columnconfigure(0, weight=1)
        return form

    def _section_label(self, parent: tk.Widget, text: str) -> None:
        container = ctk.CTkFrame(parent, fg_color="transparent")
        container.pack(fill="x", pady=(10, 8))
        ctk.CTkLabel(
            container,
            text=text.upper(),
            text_color=ACCENT_DARK_COLOR,
            font=("Segoe UI Semibold", 9),
        ).pack(side="left")
        ctk.CTkFrame(container, fg_color=LINE_COLOR, height=1, corner_radius=0).pack(
            side="left", fill="x", expand=True, padx=(8, 0), pady=(8, 0)
        )

    def _notice(self, parent: tk.Widget, text: str) -> None:
        frame = ctk.CTkFrame(
            parent,
            fg_color=WARNING_SOFT_BG,
            border_width=1,
            border_color="#92400e",
            corner_radius=6,
        )
        frame.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(
            frame,
            text=text,
            text_color=WARNING_COLOR,
            font=("Segoe UI Semibold", 9),
            justify="left",
            wraplength=280,
            anchor="w",
        ).pack(anchor="w", fill="x", padx=10, pady=8)

    def _entry(self, parent: tk.Widget, label: str, variable: tk.StringVar, *, show: str = "", hint: str = "") -> None:
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(row, text=label, text_color=TEXT_COLOR, font=("Segoe UI", 9)).pack(anchor="w")
        ctk.CTkEntry(
            row,
            textvariable=variable,
            show=show,
            height=34,
            corner_radius=6,
            fg_color=CONTROL_BG,
            border_color=LINE_STRONG_COLOR,
            text_color=TEXT_COLOR,
        ).pack(fill="x", pady=(3, 0))
        if hint:
            ctk.CTkLabel(
                row,
                text=hint,
                text_color=MUTED_COLOR,
                font=("Segoe UI", 9),
                wraplength=295,
                anchor="w",
                justify="left",
            ).pack(anchor="w", pady=(3, 0))

    def _protocol_row(self, parent: tk.Widget) -> None:
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=(0, 8))
        left = ctk.CTkFrame(row, fg_color="transparent")
        left.pack(side="left", fill="x", expand=True)
        right = ctk.CTkFrame(row, fg_color="transparent")
        right.pack(side="left", fill="x", expand=True, padx=(8, 0))
        ctk.CTkLabel(left, text="Protocol", text_color=TEXT_COLOR, font=("Segoe UI", 9)).pack(anchor="w")
        protocol = ctk.CTkComboBox(
            left,
            variable=self.protocol_var,
            values=["ssh", "telnet"],
            state="readonly",
            height=34,
            corner_radius=6,
            fg_color=CONTROL_BG,
            border_color=LINE_STRONG_COLOR,
            button_color=ACCENT_COLOR,
            button_hover_color=ACCENT_ACTIVE_COLOR,
            dropdown_fg_color=PANEL_BG,
            dropdown_hover_color=CONTROL_HOVER_BG,
            dropdown_text_color=TEXT_COLOR,
            text_color=TEXT_COLOR,
        )
        protocol.pack(fill="x", pady=(3, 0))
        ctk.CTkLabel(right, text="Port", text_color=TEXT_COLOR, font=("Segoe UI", 9)).pack(anchor="w")
        ctk.CTkEntry(
            right,
            textvariable=self.port_var,
            height=34,
            corner_radius=6,
            fg_color=CONTROL_BG,
            border_color=LINE_STRONG_COLOR,
            text_color=TEXT_COLOR,
        ).pack(fill="x", pady=(3, 0))

    def _timeout_row(self, parent: tk.Widget) -> None:
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(row, text="Timeout seconds", text_color=TEXT_COLOR, font=("Segoe UI", 9)).pack(anchor="w")
        ctk.CTkEntry(
            row,
            textvariable=self.timeout_var,
            width=120,
            height=34,
            corner_radius=6,
            fg_color=CONTROL_BG,
            border_color=LINE_STRONG_COLOR,
            text_color=TEXT_COLOR,
        ).pack(anchor="w", pady=(3, 0))

    def _role_networks_row(self, parent: tk.Widget) -> None:
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(row, text=ROLE_NETWORK_LABEL, text_color=TEXT_COLOR, font=("Segoe UI", 9)).pack(anchor="w")
        input_row = ctk.CTkFrame(row, fg_color="transparent")
        input_row.pack(fill="x", pady=(3, 0))
        ctk.CTkEntry(
            input_row,
            textvariable=self.role_networks_path_var,
            height=34,
            corner_radius=6,
            fg_color=CONTROL_BG,
            border_color=LINE_STRONG_COLOR,
            text_color=TEXT_COLOR,
        ).pack(side="left", fill="x", expand=True)
        self._button(input_row, text=ROLE_NETWORK_SELECT_LABEL, command=self._browse_role_networks).pack(side="left", padx=(8, 0))
        help_row = ctk.CTkFrame(row, fg_color="transparent")
        help_row.pack(fill="x", pady=(6, 0))
        self._button(
            help_row,
            text=ROLE_NETWORK_GUIDE_LABEL,
            command=self._show_role_network_guide,
        ).pack(side="left", fill="x", expand=True, padx=(0, 4))
        self._button(
            help_row,
            text=ROLE_NETWORK_TEMPLATE_LABEL,
            command=self._open_role_network_template,
        ).pack(side="left", fill="x", expand=True, padx=(4, 0))
        ctk.CTkLabel(
            row,
            text=ROLE_NETWORK_HELP,
            text_color=MUTED_COLOR,
            font=("Segoe UI", 9),
            wraplength=295,
            anchor="w",
            justify="left",
        ).pack(anchor="w", pady=(3, 0))
        ctk.CTkLabel(
            row,
            textvariable=self.role_networks_status_var,
            text_color=MUTED_COLOR,
            font=("Segoe UI", 9),
            wraplength=295,
            anchor="w",
            justify="left",
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
        window = ctk.CTkToplevel(self)
        window.title(ROLE_NETWORK_GUIDE_TITLE)
        window.configure(fg_color=APP_BG)
        window.transient(self)
        window.minsize(560, 480)

        container = ctk.CTkFrame(
            window,
            fg_color=PANEL_BG,
            border_width=1,
            border_color=LINE_COLOR,
            corner_radius=8,
        )
        container.pack(fill="both", expand=True, padx=14, pady=14)
        ctk.CTkLabel(
            container,
            text=ROLE_NETWORK_GUIDE_TITLE,
            text_color=TEXT_COLOR,
            font=("Segoe UI Semibold", 16),
        ).pack(anchor="w", padx=16, pady=(16, 0))
        ctk.CTkLabel(
            container,
            text="샘플 Excel의 Role_Networks Sheet에 사내 기준 대역을 입력하세요. 해당 Sheet가 없으면 첫 번째 Sheet를 읽습니다.",
            text_color=MUTED_COLOR,
            font=("Segoe UI", 9),
            wraplength=500,
            justify="left",
            anchor="w",
        ).pack(anchor="w", fill="x", padx=16, pady=(3, 12))

        text = ctk.CTkTextbox(
            container,
            wrap="word",
            fg_color=LOG_BG,
            text_color=LOG_TEXT,
            border_width=1,
            border_color=LINE_COLOR,
            corner_radius=8,
            font=("Consolas", 10),
            height=18,
        )
        text.pack(fill="both", expand=True, padx=16)
        text.insert("1.0", ROLE_NETWORK_GUIDE_TEXT)
        text.configure(state="disabled")

        actions = ctk.CTkFrame(container, fg_color="transparent")
        actions.pack(fill="x", padx=16, pady=(12, 16))
        self._button(
            actions,
            text=ROLE_NETWORK_TEMPLATE_LABEL,
            command=self._open_role_network_template,
        ).pack(side="left")
        self._button(actions, text="닫기", command=window.destroy).pack(side="right")
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
        self._set_ssh_status_for_stage(stage)
        if hasattr(self, "progress"):
            self.progress.set(STAGE_PROGRESS.get(stage, 0) / 100)
        if hasattr(self, "running_progress"):
            self.running_progress.set(STAGE_PROGRESS.get(stage, 0) / 100)
        active_index = STAGE_SEQUENCE.index(stage) if stage in STAGE_SEQUENCE else -1
        for index, step in enumerate(STAGE_SEQUENCE):
            widget = self.stage_label_widgets.get(step)
            if widget is None:
                continue
            if stage == "failed":
                widget.configure(fg_color=PANEL_SUBTLE_BG, text_color=MUTED_COLOR)
            elif index < active_index:
                widget.configure(fg_color=SUCCESS_SOFT_BG, text_color=SUCCESS_COLOR)
            elif index == active_index:
                widget.configure(fg_color=ACCENT_SOFT_BG, text_color=ACCENT_DARK_COLOR)
            else:
                widget.configure(fg_color=PANEL_SUBTLE_BG, text_color=MUTED_COLOR)

    def _set_ssh_status_for_stage(self, stage: str) -> None:
        if not hasattr(self, "ssh_status_dot"):
            return
        if stage == "connecting":
            status_text = "연결 중"
            status_color = WARNING_COLOR
        elif stage in {"collecting", "reporting"}:
            status_text = "연결됨"
            status_color = SUCCESS_COLOR
        elif stage == "completed":
            status_text = "완료"
            status_color = SUCCESS_COLOR
        elif stage == "failed":
            status_text = "실패"
            status_color = DANGER_COLOR
        else:
            status_text = "대기"
            status_color = MUTED_COLOR
        self.ssh_status_var.set(status_text)
        self.ssh_status_dot.configure(fg_color=status_color)

    def _configure_log_tags(self) -> None:
        self.log_text.tag_config("normal", foreground=LOG_TEXT)
        self.log_text.tag_config("muted", foreground=LOG_MUTED)
        self.log_text.tag_config("info", foreground=LOG_INFO)
        self.log_text.tag_config("success", foreground=LOG_SUCCESS)
        self.log_text.tag_config("warning", foreground=LOG_WARNING)
        self.log_text.tag_config("error", foreground=LOG_ERROR)

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
        self.running_progress_title_var.set("데이터 수집 진행 중")
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
        self.running_progress_title_var.set("안전 진단 진행 중")
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
            payload = {
                "run_dir": run_dir,
                "html": files["html"],
                "xlsx": files["xlsx"],
                "summary": _result_report_summary_from_parsed(parsed, role_networks),
            }
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
                    self._set_result_summary(paths.get("summary"))
                    self._set_result_buttons(folder_enabled=True, report_enabled=True)
                    self._show_report_complete_dialog(paths)
                elif event == "diagnostic_done":
                    paths = payload
                    primary_code = str(paths.get("primary_code", "WLC-UNK-001"))
                    self.last_run_dir = paths["run_dir"]
                    self.last_html = paths.get("html")
                    self.last_xlsx = None
                    self.last_diagnostic_json = paths.get("json")
                    self._set_result_summary(
                        ResultReportSummary(note="안전 진단 결과입니다. SSID/Role 요약은 일반 수집 완료 후 표시됩니다.")
                    )
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
                        self._set_result_summary(ResultReportSummary(note="실패했습니다. 수집 로그를 확인하세요."))
                        self._log(f"ERROR: {message}")
                        if payload.get("run_log"):
                            self._log(f"Run log: {payload['run_log']}")
                        self._set_result_buttons(folder_enabled=bool(self.last_run_dir), report_enabled=False)
                    else:
                        message = str(payload)
                        self._set_result_summary(ResultReportSummary(note="실패했습니다. 수집 로그를 확인하세요."))
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
        self._sync_running_progress(running)
        for button in self.start_buttons:
            button.configure(state="disabled" if running else "normal")
        self.diagnostic_button.configure(state="disabled" if running else "normal")
        if running:
            self._set_stage("connecting")
            self._set_result_summary(ResultReportSummary(note="수집 중입니다. 완료 후 요약 수치가 표시됩니다."))
            self._set_result_buttons(folder_enabled=False, report_enabled=False)
        else:
            if self.stage_var.get() not in {STAGE_LABELS["completed"], STAGE_LABELS["failed"]}:
                self._set_stage("ready")

    def _show_report_complete_dialog(self, paths: dict[str, Path]) -> None:
        window = ctk.CTkToplevel(self)
        window.title(REPORT_COMPLETE_TITLE)
        window.configure(fg_color=APP_BG)
        window.transient(self)
        window.resizable(False, False)

        container = ctk.CTkFrame(
            window,
            fg_color=PANEL_BG,
            border_width=1,
            border_color=LINE_COLOR,
            corner_radius=8,
        )
        container.pack(fill="both", expand=True, padx=16, pady=16)

        badge = ctk.CTkLabel(
            container,
            text="완료",
            fg_color=SUCCESS_SOFT_BG,
            text_color=SUCCESS_COLOR,
            font=("Segoe UI Semibold", 10),
            height=30,
            corner_radius=6,
        )
        badge.pack(anchor="w", padx=18, pady=(18, 10))

        ctk.CTkLabel(
            container,
            text=REPORT_COMPLETE_MESSAGE,
            text_color=TEXT_COLOR,
            font=("Segoe UI Semibold", 17),
            anchor="w",
        ).pack(anchor="w", fill="x", padx=18)
        ctk.CTkLabel(
            container,
            text="HTML 보고서를 먼저 확인하고, 필요하면 Excel 파일과 결과 폴더를 함께 검토하세요.",
            text_color=MUTED_COLOR,
            font=("Segoe UI", 10),
            wraplength=420,
            justify="left",
            anchor="w",
        ).pack(anchor="w", fill="x", padx=18, pady=(6, 16))

        actions = ctk.CTkFrame(container, fg_color="transparent")
        actions.pack(fill="x", padx=18, pady=(0, 18))
        actions.grid_columnconfigure(0, weight=1)
        actions.grid_columnconfigure(1, weight=1)
        html_path = paths.get("html")
        run_dir = paths.get("run_dir")
        self._button(
            actions,
            text=RESULT_HTML_ACTION_TEXT,
            variant="primary",
            command=lambda: _open_path(html_path) if html_path else None,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self._button(
            actions,
            text=RESULT_FOLDER_ACTION_TEXT,
            command=lambda: _open_path(run_dir) if run_dir else None,
        ).grid(row=0, column=1, sticky="ew", padx=(6, 0))
        self._button(actions, text="닫기", command=window.destroy).grid(
            row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0)
        )

        window.update_idletasks()
        width = 500
        height = 245
        x = self.winfo_x() + max(0, (self.winfo_width() - width) // 2)
        y = self.winfo_y() + max(0, (self.winfo_height() - height) // 2)
        window.geometry(f"{width}x{height}+{x}+{y}")
        window.focus_set()
        window.grab_set()

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

    def _set_result_summary(self, summary: object) -> None:
        if not isinstance(summary, ResultReportSummary):
            summary = ResultReportSummary()
        self.result_ssid_count_var.set(str(summary.ssid_count))
        self.result_role_count_var.set(str(summary.role_count))
        self.result_matched_count_var.set(str(summary.matched_count))
        self.result_mismatched_count_var.set(str(summary.mismatched_count))
        self.result_summary_note_var.set(summary.note)

    def _log(self, text: str) -> None:
        self.log_text.configure(state="normal")
        for segment, tag in _log_segments_for_line(text):
            if segment:
                self.log_text.insert("end", segment, (tag,))
        self.log_text.insert("end", "\n", ("normal",))
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
    stripped = text.strip()
    upper = stripped.upper()
    if upper.startswith("[ERROR]"):
        return "error"
    if upper.startswith("[WARNING]"):
        return "warning"
    if upper.startswith("[SUCCESS]"):
        return "success"
    if upper.startswith("[INFO]"):
        return "info"
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


def _log_segments_for_line(text: str) -> list[tuple[str, str]]:
    starts_with_level = bool(LOG_LEVEL_PATTERN.match(text.strip()))
    base_tag = _log_tag_for_line(text) if starts_with_level or not LOG_LEVEL_PATTERN.search(text) else "normal"
    segments: list[tuple[str, str]] = []
    cursor = 0
    for match in LOG_LEVEL_PATTERN.finditer(text):
        if match.start() > cursor:
            segments.append((text[cursor : match.start()], base_tag))
        token = match.group(1).upper()
        segments.append((text[match.start() : match.end()], LOG_LEVEL_TAGS[token]))
        cursor = match.end()
    if cursor < len(text):
        segments.append((text[cursor:], base_tag))
    if not segments:
        segments.append((text, base_tag))
    return segments


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


def _result_report_summary_from_parsed(
    parsed_controllers: list[ParsedController],
    role_networks: list[RoleNetworkDefinition] | None,
) -> ResultReportSummary:
    ssids: set[tuple[str, str]] = set()
    roles: set[tuple[str, str]] = set()
    collected_role_names: set[str] = set()

    for parsed in parsed_controllers:
        controller_name = parsed.controller.name
        for mapping in parsed.ssid_role_mappings:
            if mapping.ssid:
                ssids.add((controller_name, mapping.ssid.casefold()))
            if mapping.role:
                roles.add((controller_name, mapping.role.casefold()))
                collected_role_names.add(mapping.role.casefold())
        for role in parsed.role_policies:
            roles.add((controller_name, role.casefold()))
            collected_role_names.add(role.casefold())
        for role in parsed.user_role_observations:
            roles.add((controller_name, role.casefold()))
            collected_role_names.add(role.casefold())
        for context in parsed.role_network_contexts:
            if context.role:
                roles.add((controller_name, context.role.casefold()))
                collected_role_names.add(context.role.casefold())

    if not role_networks:
        return ResultReportSummary(
            ssid_count=len(ssids),
            role_count=len(roles),
            note="사내 Role 대역표를 선택하면 일치/불일치 항목 수가 함께 표시됩니다.",
        )

    local_lookup = _role_network_lookup_for_summary(role_networks)
    matched_count = 0
    mismatched_count = 0

    for parsed in parsed_controllers:
        for role in _collected_roles_for_summary(parsed):
            local_networks = local_lookup.get(role.casefold(), [])
            wlc_networks = _wlc_configured_subnets_for_summary(parsed, role)
            if local_networks and wlc_networks and set(local_networks) == set(wlc_networks):
                matched_count += 1
            else:
                mismatched_count += 1

    for role_key in local_lookup:
        if role_key not in collected_role_names:
            mismatched_count += 1

    return ResultReportSummary(
        ssid_count=len(ssids),
        role_count=len(roles),
        matched_count=matched_count,
        mismatched_count=mismatched_count,
        note="일치/불일치는 사내 Role 대역표와 WLC 수집 대역을 Role 단위로 비교한 값입니다.",
    )


def _role_network_lookup_for_summary(role_networks: list[RoleNetworkDefinition]) -> dict[str, list[str]]:
    lookup: dict[str, list[str]] = {}
    for definition in role_networks:
        role_key = definition.role.casefold()
        lookup.setdefault(role_key, [])
        if definition.network not in lookup[role_key]:
            lookup[role_key].append(definition.network)
    return lookup


def _collected_roles_for_summary(parsed: ParsedController) -> list[str]:
    roles = (
        set(parsed.role_policies)
        | set(parsed.user_role_observations)
        | {mapping.role for mapping in parsed.ssid_role_mappings if mapping.role}
        | {context.role for context in parsed.role_network_contexts if context.role}
    )
    return sorted(roles, key=str.casefold)


def _wlc_configured_subnets_for_summary(parsed: ParsedController, role: str) -> list[str]:
    networks = [
        context.configured_subnet
        for context in parsed.role_network_contexts
        if context.role.casefold() == role.casefold()
        and context.configured_subnet
        and context.configured_subnet.casefold() != "unknown"
    ]
    return list(dict.fromkeys(networks))


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
