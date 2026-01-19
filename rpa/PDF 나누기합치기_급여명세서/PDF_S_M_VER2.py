import customtkinter as ctk
from tkinter import filedialog, Listbox, messagebox
import os
import PyPDF2
import threading

# --- 디자인 시스템 정의 (master_app.py와 통일) ---
BG_COLOR = "#18181C"
SIDEBAR_COLOR = "#25262B"
ACCENT_COLOR = "#3A76F0"
FONT_FAMILY = "Malgun Gothic"
LISTBOX_BG = "#2B2D30"


class PDFToolApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("PDF Split & Merge Tool")
        self.geometry("1000x600")
        self.configure(fg_color=BG_COLOR)
        ctk.set_appearance_mode("Dark")

        # --- 메인 레이아웃 설정 ---
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=2)
        self.grid_rowconfigure(0, weight=1)

        # --- 상태 변수 초기화 ---
        self.split_file_path = ""
        self.output_dir_path = ""

        # --- UI 구성 요소 생성 ---
        self.setup_sidebar()
        self.setup_main_area()

        # --- 초기 모드 설정 ---
        self.switch_mode("나누기")

    def setup_sidebar(self):
        """좌측 컨트롤 패널 UI를 생성합니다."""
        sidebar_frame = ctk.CTkFrame(self, fg_color=SIDEBAR_COLOR, corner_radius=0)
        sidebar_frame.grid(row=0, column=0, sticky="nsew")
        sidebar_frame.grid_propagate(False)
        sidebar_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(sidebar_frame, text="PDF Tool", font=(FONT_FAMILY, 20, "bold")).pack(pady=20, padx=20, anchor="w")

        # 모드 전환 버튼
        mode_switcher = ctk.CTkSegmentedButton(sidebar_frame, values=["나누기", "합치기"],
                                               command=self.switch_mode, font=(FONT_FAMILY, 14),
                                               selected_color=ACCENT_COLOR, selected_hover_color=ACCENT_COLOR)
        mode_switcher.pack(fill="x", padx=20)
        mode_switcher.set("나누기")

        # 옵션 프레임
        self.split_options_frame = self.create_split_options(sidebar_frame)
        self.merge_options_frame = self.create_merge_options(sidebar_frame)

    def create_split_options(self, parent):
        """'나누기' 모드의 옵션 UI를 생성합니다."""
        frame = ctk.CTkFrame(parent, fg_color="transparent")

        ctk.CTkLabel(frame, text="1. 나눌 PDF 파일 선택", font=(FONT_FAMILY, 14, "bold")).pack(pady=(20, 5), anchor="w",
                                                                                         padx=20)
        self.split_file_label = ctk.CTkLabel(frame, text="선택된 파일 없음", wraplength=260, anchor="w", justify="left")
        self.split_file_label.pack(fill="x", padx=20)
        ctk.CTkButton(frame, text="파일 찾기", command=self.select_split_file).pack(fill="x", padx=20, pady=(5, 10))

        ctk.CTkLabel(frame, text="2. 나누기 옵션", font=(FONT_FAMILY, 14, "bold")).pack(pady=(10, 5), anchor="w", padx=20)
        self.split_pages_entry = ctk.CTkEntry(frame, placeholder_text="페이지 수 (예: 1)")
        self.split_pages_entry.pack(fill="x", padx=20)
        # self.split_pages_entry.insert(0, "1")

        ctk.CTkLabel(frame, text="3. 저장할 폴더 선택", font=(FONT_FAMILY, 14, "bold")).pack(pady=(10, 5), anchor="w", padx=20)
        self.output_dir_label = ctk.CTkLabel(frame, text="선택된 폴더 없음", wraplength=260, anchor="w", justify="left")
        self.output_dir_label.pack(fill="x", padx=20)
        ctk.CTkButton(frame, text="폴더 찾기", command=self.select_output_folder).pack(fill="x", padx=20, pady=5)

        return frame

    def create_merge_options(self, parent):
        """'합치기' 모드의 옵션 UI를 생성합니다."""
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        ctk.CTkLabel(frame, text="우측 목록에 파일을 추가하고\n순서를 조정한 뒤 실행하세요.",
                     font=(FONT_FAMILY, 14)).pack(pady=20, padx=20, anchor="w")
        return frame

    def setup_main_area(self):
        """우측 파일 목록 및 실행 영역 UI를 생성합니다."""
        main_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        main_frame.grid_rowconfigure(1, weight=1)
        main_frame.grid_columnconfigure(0, weight=1)

        # 파일 관리 버튼 프레임
        control_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        control_frame.grid(row=0, column=0, columnspan=2, sticky="ew")

        ctk.CTkLabel(control_frame, text="파일 목록", font=(FONT_FAMILY, 16, "bold")).pack(side="left")
        self.add_button = ctk.CTkButton(control_frame, text="파일 추가", width=100, command=self.add_files_to_list)
        self.add_button.pack(side="right", padx=(0, 5))
        self.remove_button = ctk.CTkButton(control_frame, text="선택 삭제", width=100, command=self.remove_selected_file)
        self.remove_button.pack(side="right", padx=(0, 5))
        self.clear_button = ctk.CTkButton(control_frame, text="전체 삭제", width=100, command=self.clear_file_list)
        self.clear_button.pack(side="right", padx=5)

        # 파일 리스트박스
        self.file_listbox = Listbox(main_frame, bg=LISTBOX_BG, fg="white", selectbackground=ACCENT_COLOR,
                                    borderwidth=0, highlightthickness=0, font=(FONT_FAMILY, 12))
        self.file_listbox.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=10)

        # 실행 버튼
        self.execute_button = ctk.CTkButton(main_frame, text="작업 실행", font=(FONT_FAMILY, 16, "bold"),
                                            height=40, fg_color=ACCENT_COLOR, hover_color="#3266D0")
        self.execute_button.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0))

        # 진행률 및 상태 표시
        self.progress_bar = ctk.CTkProgressBar(main_frame, orientation="horizontal", determinate_speed=1)
        self.progress_bar.set(0)
        self.progress_bar.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(10, 5))

        self.status_label = ctk.CTkLabel(main_frame, text="준비 완료", anchor="w")
        self.status_label.grid(row=4, column=0, columnspan=2, sticky="ew")

    # --- UI 제어 및 이벤트 핸들러 ---
    def switch_mode(self, mode):
        """'나누기'와 '합치기' 모드 간 UI를 전환합니다."""
        if mode == "나누기":
            self.split_options_frame.pack(fill="x", pady=10)
            self.merge_options_frame.pack_forget()
            self.execute_button.configure(text="PDF 나누기 실행", command=self.start_split_thread)
            self.add_button.pack_forget()
            self.remove_button.pack_forget()
            self.clear_button.pack_forget()
            self.file_listbox.delete(0, 'end')

        elif mode == "합치기":
            self.split_options_frame.pack_forget()
            self.merge_options_frame.pack(fill="x", pady=10)
            self.execute_button.configure(text="PDF 합치기 실행", command=self.start_merge_thread)
            self.add_button.pack(side="right", padx=(0, 5))
            self.remove_button.pack(side="right", padx=(0, 5))
            self.clear_button.pack(side="right", padx=5)
            self.split_file_label.configure(text="선택된 파일 없음")
            self.output_dir_label.configure(text="선택된 폴더 없음")

    def select_split_file(self):
        filepath = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf")])
        if filepath:
            self.split_file_path = filepath
            self.split_file_label.configure(text=os.path.basename(filepath))
            # 나누기 모드에서는 출력 폴더를 자동으로 제안
            if not self.output_dir_path:
                base_path = os.path.dirname(filepath)
                base_name = os.path.splitext(os.path.basename(filepath))[0]
                suggested_path = os.path.join(base_path, f"{base_name}_split")
                self.output_dir_path = suggested_path
                self.output_dir_label.configure(text=f".../{os.path.basename(suggested_path)}")

    def select_output_folder(self):
        dirpath = filedialog.askdirectory()
        if dirpath:
            self.output_dir_path = dirpath
            self.output_dir_label.configure(text=f".../{os.path.basename(dirpath)}")

    def add_files_to_list(self):
        filepaths = filedialog.askopenfilenames(filetypes=[("PDF files", "*.pdf")])
        for f in filepaths:
            self.file_listbox.insert('end', f)
        self.update_status(f"{len(filepaths)}개 파일 추가됨")

    def remove_selected_file(self):
        selected_indices = self.file_listbox.curselection()
        # 뒤에서부터 삭제해야 인덱스 엉킴 방지
        for i in reversed(selected_indices):
            self.file_listbox.delete(i)
        self.update_status("선택한 파일이 삭제되었습니다.")

    def clear_file_list(self):
        self.file_listbox.delete(0, 'end')
        self.update_status("파일 목록이 초기화되었습니다.")

    # --- 스레드 관리 ---
    def start_split_thread(self):
        threading.Thread(target=self.run_split_pdf, daemon=True).start()

    def start_merge_thread(self):
        threading.Thread(target=self.run_merge_pdf, daemon=True).start()

    # --- 핵심 로직 (PDF 처리) ---
    def run_split_pdf(self):
        if not self.split_file_path or not self.output_dir_path:
            messagebox.showerror("오류", "PDF 파일과 저장할 폴더를 모두 선택하세요.")
            return

        try:
            pages_per_split = int(self.split_pages_entry.get())
            if pages_per_split <= 0: raise ValueError
        except ValueError:
            messagebox.showerror("오류", "페이지 수는 1 이상의 숫자로 입력하세요.")
            return

        os.makedirs(self.output_dir_path, exist_ok=True)
        self.update_progress(0)
        self.update_status("PDF 나누기 시작...")

        try:
            reader = PyPDF2.PdfReader(self.split_file_path)
            total_pages = len(reader.pages)
            output_file_count = 0

            for start_page in range(0, total_pages, pages_per_split):
                end_page = min(start_page + pages_per_split, total_pages)
                writer = PyPDF2.PdfWriter()

                for i in range(start_page, end_page):
                    writer.add_page(reader.pages[i])

                output_filename = f"split_{start_page + 1}-{end_page}.pdf"
                output_path = os.path.join(self.output_dir_path, output_filename)

                with open(output_path, "wb") as f:
                    writer.write(f)

                output_file_count += 1
                progress = ((start_page + 1) / total_pages) * 100
                self.update_progress(progress / 100)  # 0.0 ~ 1.0

            self.update_progress(1)
            self.update_status(f"완료! 총 {output_file_count}개의 파일이 생성되었습니다.")
            messagebox.showinfo("완료", f"PDF 나누기가 완료되었습니다.\n저장 위치: {self.output_dir_path}")

        except Exception as e:
            self.update_status("오류 발생")
            messagebox.showerror("오류", f"PDF 처리 중 오류가 발생했습니다: {e}")
        finally:
            self.update_progress(0)

    def run_merge_pdf(self):
        file_list = self.file_listbox.get(0, 'end')
        if not file_list:
            messagebox.showerror("오류", "합칠 PDF 파일을 하나 이상 추가하세요.")
            return

        output_path = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF files", "*.pdf")])
        if not output_path:
            self.update_status("작업이 취소되었습니다.")
            return

        self.update_progress(0)
        self.update_status("PDF 합치기 시작...")

        try:
            writer = PyPDF2.PdfWriter()
            total_files = len(file_list)

            for i, filepath in enumerate(file_list):
                reader = PyPDF2.PdfReader(filepath)
                for page in reader.pages:
                    writer.add_page(page)

                progress = ((i + 1) / total_files) * 100
                self.update_progress(progress / 100)  # 0.0 ~ 1.0

            with open(output_path, "wb") as f:
                writer.write(f)

            self.update_progress(1)
            self.update_status(f"완료! 합쳐진 파일이 저장되었습니다.")
            messagebox.showinfo("완료", f"PDF 합치기가 완료되었습니다.\n저장 파일: {output_path}")

        except Exception as e:
            self.update_status("오류 발생")
            messagebox.showerror("오류", f"PDF 처리 중 오류가 발생했습니다: {e}")
        finally:
            self.update_progress(0)

    # --- UI 업데이트 헬퍼 ---
    def update_status(self, message):
        """상태 표시줄 텍스트를 안전하게 업데이트합니다."""
        self.status_label.configure(text=message)

    def update_progress(self, value):
        """프로그레스 바 값을 안전하게 업데이트합니다."""
        self.progress_bar.set(value)


if __name__ == "__main__":
    app = PDFToolApp()
    app.mainloop()