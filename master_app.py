from dotenv import load_dotenv
load_dotenv()
import customtkinter as ctk
from PIL import Image, ImageDraw, ImageFont
import os
import subprocess
import sys
import threading
import queue
from collections import defaultdict

# --- 디자인 시스템 정의 ---
BG_COLOR = "#18181C"
SIDEBAR_COLOR = "#25262B"
ACCENT_COLOR = "#3A76F0"
FONT_FAMILY = "Malgun Gothic"

# --- 제외 키워드(폴더/파일명에 이 문자열이 들어가면 숨김) ---
# 환경변수 APP_EXCLUDE_KEYWORDS="legacy, _archive, test" 형태로도 지정 가능

def _parse_keywords(env_key: str, default=()):
    raw = os.getenv(env_key, "")
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    return tuple(parts) if parts else tuple(default)

APP_EXCLUDE_KEYWORDS = _parse_keywords(
    "APP_EXCLUDE_KEYWORDS",
    default=()  # 기본값 비움(환경변수 설정 시에만 적용)
)


def _name_contains_any(name: str, keywords=APP_EXCLUDE_KEYWORDS) -> bool:
    s = name.lower()
    return any(k.lower() in s for k in keywords if k)


# =============================================================================
#  1. 내비게이션 아이템 그룹 (아코디언 메뉴)
# =============================================================================
class NavItemGroup(ctk.CTkFrame):
    def __init__(self, master, app_name, icon, py_files, launch_callback):
        super().__init__(master, fg_color="transparent")
        self.py_files = py_files
        self.launch_callback = launch_callback
        self.app_name = app_name
        self.is_expanded = False

        self.main_button = ctk.CTkButton(
            self,
            text=f"  {app_name}",
            image=icon,
            font=(FONT_FAMILY, 14),
            anchor="w",
            fg_color="transparent",
            hover_color=BG_COLOR,
            command=self.toggle_expand,
        )
        self.main_button.pack(fill="x")
        self.sub_frame = ctk.CTkFrame(self, fg_color="transparent")

    def toggle_expand(self):
        if not self.is_expanded:
            for group in self.master.winfo_children():
                if isinstance(group, NavItemGroup) and group != self:
                    group.collapse()
            self.expand()
        else:
            self.collapse()

    def expand(self):
        self.is_expanded = True
        self.main_button.configure(fg_color=BG_COLOR)
        for file_name in self.py_files:
            btn = ctk.CTkButton(
                self.sub_frame,
                text=f"    \u21B3 {file_name}",
                font=(FONT_FAMILY, 12),
                anchor="w",
                fg_color="transparent",
                hover_color=BG_COLOR,
                command=lambda f=file_name: self.launch_callback(self.app_name, f),
            )
            btn.pack(fill="x", padx=(10, 0), pady=2)
        self.sub_frame.pack(fill="x", pady=(0, 5))

    def collapse(self):
        self.is_expanded = False
        self.main_button.configure(fg_color="transparent")
        for widget in self.sub_frame.winfo_children():
            widget.destroy()
        self.sub_frame.pack_forget()


# =============================================================================
#  2. 메인 애플리케이션 (단순/안정 실행기 + 워크스페이스 로그뷰어)
#    - 클릭 시 해당 스크립트를 서브프로세스로 실행
#    - 부모(이 대시보드)가 사용 중인 파이썬 인터프리터를 그대로 사용(sys.executable)
#    - 현재 프로세스 환경변수 그대로 상속(os.environ)
#    - stdout/stderr를 안전하게 스트리밍해 워크스페이스에 표시(스레드+큐)
#    - 의존성 자동설치/복잡 로직 없음 → 안정 우선
# =============================================================================
class AppOrchestrator(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("Dark")
        self.title("RDXL_OPS RPA Dashboard")
        self.geometry("1400x850")
        self.configure(fg_color=BG_COLOR)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # 프로세스 및 로그 스트리밍 상태
        self.processes = {}                 # key: tab_name -> Popen
        self.output_queues = defaultdict(queue.Queue)  # 탭별 출력 큐
        self.log_widgets = {}               # key: tab_name -> CTkTextbox

        self.setup_sidebar()
        self.setup_main_area()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.after(100, self._pump_logs)    # UI 로그 업데이트 루프 시작

    # --- UI 레이아웃 ---
    def setup_sidebar(self):
        sidebar = ctk.CTkScrollableFrame(self, width=300, fg_color=SIDEBAR_COLOR, corner_radius=0)
        sidebar.grid(row=0, column=0, sticky="nsw")
        sidebar.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(sidebar, text="RDXL AUTOMATION APPS", font=(FONT_FAMILY, 16, "bold")).pack(
            padx=20, pady=20, anchor="w"
        )

        for app_name in self.get_app_directories():
            icon = self.create_default_icon(app_name[0].upper())
            app_path = os.path.join(os.path.dirname(__file__), app_name)
            py_files = [f for f in os.listdir(app_path) if f.endswith(".py")]
            NavItemGroup(sidebar, app_name, icon, py_files, self.launch_script).pack(
                fill="x", padx=10, pady=2
            )

    def setup_main_area(self):
        main_area = ctk.CTkFrame(self, fg_color="transparent")
        main_area.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        main_area.grid_rowconfigure(2, weight=1)  # 로그 텍스트박스가 늘어나도록
        main_area.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(main_area, text="Workspace", font=(FONT_FAMILY, 28, "bold")).grid(
            row=0, column=0, sticky="w"
        )

        self.tab_view = ctk.CTkTabview(
            main_area,
            fg_color=SIDEBAR_COLOR,
            segmented_button_selected_color=ACCENT_COLOR,
        )
        self.tab_view.grid(row=1, column=0, sticky="nsew", pady=(10, 0))
        if not self.tab_view.get():
            self.add_welcome_tab()

    def add_welcome_tab(self):
        if "Welcome" not in self.tab_view._name_list:
            self.tab_view.add("Welcome")
            self.tab_view.set("Welcome")
            ctk.CTkLabel(
                self.tab_view.tab("Welcome"),
                text="좌측 메뉴에서 실행할 앱을 선택하세요.",
                font=(FONT_FAMILY, 16),
            ).pack(expand=True)

    # --- 핵심: 실행 + 로그 스트리밍 ---
    def launch_script(self, app_name, file_name):
        script_path = os.path.join(os.path.dirname(__file__), app_name, file_name)
        tab_name = f"{app_name}: {file_name}"

        if not os.path.exists(script_path):
            self._alert(f"스크립트를 찾을 수 없습니다: {script_path}")
            return

        # Welcome 탭 제거
        if "Welcome" in self.tab_view._name_list:
            self.tab_view.delete("Welcome")

        # 이미 열려있으면 포커스만 이동
        if tab_name in self.tab_view._name_list:
            self.tab_view.set(tab_name)
            return

        # 탭 생성(상태 + 종료 버튼 + 로그창)
        tab = self.tab_view.add(tab_name)
        self.tab_view.set(tab_name)
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(2, weight=1)

        control = ctk.CTkFrame(tab, fg_color="transparent")
        control.grid(row=0, column=0, sticky="ew", padx=10, pady=8)
        status_label = ctk.CTkLabel(control, text="대기 중", font=(FONT_FAMILY, 13))
        status_label.pack(side="left")
        stop_btn = ctk.CTkButton(control, text="프로세스 종료", command=lambda: self.terminate_process(tab_name))
        stop_btn.pack(side="right")

        info = ctk.CTkLabel(tab, text="실행 준비...", font=(FONT_FAMILY, 14))
        info.grid(row=1, column=0, sticky="w", padx=12, pady=(0, 6))

        # 워크스페이스 로그 텍스트박스
        logbox = ctk.CTkTextbox(tab, wrap="word", font=(FONT_FAMILY, 13))
        logbox.grid(row=2, column=0, sticky="nsew", padx=10, pady=10)
        self.log_widgets[tab_name] = logbox

        # 실제 실행: 부모 인터프리터 그대로 사용 + 환경 상속 + 스크립트 폴더에서 실행
        python_exe = sys.executable.replace("\\", "/")
        cwd = os.path.dirname(script_path)
        env = os.environ.copy()

        creationflags = 0
        if os.name == "nt":
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

        try:
            proc = subprocess.Popen(
                [python_exe, script_path],
                cwd=cwd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                bufsize=1,
                creationflags=creationflags,
            )
            self.processes[tab_name] = proc
            status_label.configure(text=f"실행 중 (PID {proc.pid})")
            info.configure(text="로그 수집 중... GUI 앱이라면 별도 창이 뜹니다.")

            # 스트리밍 스레드
            threading.Thread(target=self._stream_to_queue, args=(proc.stdout, tab_name, False), daemon=True).start()
            threading.Thread(target=self._stream_to_queue, args=(proc.stderr, tab_name, True), daemon=True).start()
            threading.Thread(target=self._wait_and_report, args=(proc, tab_name), daemon=True).start()
        except Exception as e:
            status_label.configure(text="실행 실패")
            self.output_queues[tab_name].put(f"[LAUNCH-ERROR] {e}\n")

    # --- 스트리밍 & UI 펌프 ---
    def _stream_to_queue(self, stream, tab_name, is_err=False):
        prefix = "[ERR] " if is_err else ""
        try:
            for line in iter(stream.readline, ''):
                self.output_queues[tab_name].put(prefix + line)
        except Exception as e:
            self.output_queues[tab_name].put(prefix + f"<stream error: {e}>\n")
        finally:
            try:
                stream.close()
            except Exception:
                pass

    def _pump_logs(self):
        # 주기적으로 큐를 비워 각 탭 로그박스에 출력
        MAX_CHARS = 500_000  # 메모리 안전장치 (약 0.5MB)
        for tab_name, q in list(self.output_queues.items()):
            logbox = self.log_widgets.get(tab_name)
            if not logbox:
                continue
            lines = []
            while not q.empty():
                try:
                    lines.append(q.get_nowait())
                except queue.Empty:
                    break
            if lines:
                try:
                    logbox.insert("end", "".join(lines))
                    logbox.see("end")
                    # 용량 제한: 오래된 내용 잘라내기
                    content = logbox.get("1.0", "end-1c")
                    if len(content) > MAX_CHARS:
                        cut = len(content) - MAX_CHARS
                        logbox.delete("1.0", f"1.0+{cut}c")
                except Exception:
                    pass
        self.after(100, self._pump_logs)

    def _wait_and_report(self, proc: subprocess.Popen, tab_name: str):
        code = proc.wait()
        self.output_queues[tab_name].put(f"\n[PROCESS-EXIT] return code: {code}\n")

    # --- 종료/정리 ---
    def terminate_process(self, tab_name):
        proc = self.processes.pop(tab_name, None)
        if proc and proc.poll() is None:
            try:
                proc.terminate()
            except Exception:
                pass
        # UI/상태 정리
        self.log_widgets.pop(tab_name, None)
        self.output_queues.pop(tab_name, None)
        if tab_name in self.tab_view._name_list:
            self.tab_view.delete(tab_name)
        if not self.tab_view.get():
            self.add_welcome_tab()

    def on_closing(self):
        for name, proc in list(self.processes.items()):
            try:
                if proc.poll() is None:
                    proc.terminate()
            except Exception:
                pass
        self.processes.clear()
        self.destroy()

    # --- 유틸 ---
    def _alert(self, msg: str):
        dialog = ctk.CTkToplevel(self)
        dialog.title("알림"); dialog.geometry("420x160"); dialog.transient(self); dialog.grab_set()
        ctk.CTkLabel(dialog, text=msg, font=(FONT_FAMILY, 14)).pack(pady=20, padx=20)
        ctk.CTkButton(dialog, text="확인", command=dialog.destroy).pack(pady=10)

    def get_app_directories(self):
        excluded = {".git", ".idea", "__pycache__", "venv", ".venv"}
        current_dir = os.path.dirname(os.path.abspath(__file__))
        dirs = []
        for d in os.listdir(current_dir):
            full = os.path.join(current_dir, d)
            if not os.path.isdir(full):
                continue
            if d in excluded or d.startswith("."):
                continue
            if _name_contains_any(d):  # 키워드 기반 제외
                continue
            dirs.append(d)
        return sorted(dirs)

    def create_default_icon(self, initial, size=(24, 24)):
        image = Image.new("RGBA", size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        try:
            font = ImageFont.truetype("malgun.ttf", 12)
        except IOError:
            font = ImageFont.load_default()
        text_bbox = draw.textbbox((0, 0), initial, font=font)
        draw.text(
            ((size[0] - text_bbox[2]) / 2, (size[1] - text_bbox[3]) / 2 - 2),
            initial,
            font=font,
            fill="#A0A0A0",
        )
        return ctk.CTkImage(dark_image=image, size=size)


if __name__ == "__main__":
    app = AppOrchestrator()
    app.mainloop()
