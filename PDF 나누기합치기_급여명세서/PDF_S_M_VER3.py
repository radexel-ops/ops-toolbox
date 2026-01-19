import customtkinter as ctk
from tkinterdnd2 import TkinterDnD, DND_FILES
from tkinter import filedialog, messagebox, simpledialog
import os
import sys
import threading
import subprocess
import platform
import time
import pandas as pd  # 엑셀 처리를 위해 필수
import shutil        # 파일 복사/이동용

# --- 문서 처리 라이브러리 ---
try:
    import pikepdf
    HAS_PIKEPDF = True
except ImportError:
    HAS_PIKEPDF = False
    import PyPDF2  # Fallback

from PIL import Image
from docx2pdf import convert as convert_docx
from xhtml2pdf import pisa

# --- PDF 생성 및 폰트 관련 (ReportLab) ---
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.units import mm

# --- HWP 제어 (Windows Only) ---
try:
    import win32com.client
    import pythoncom
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False

# ==========================================
# 1. 디자인 시스템 (Brand Identity)
# ==========================================
APP_NAME = "Document Master Pro"
CONFIG_FILE = "doc_master_config.json"

# 브랜드 컬러 (#2C5CA3 / #20B685)
COLORS = {
    "bg": "#18191C",             # Deep Dark
    "surface": "#25262B",        # Card Background
    "surface_hover": "#2F3036",  # Hover
    "border": "#373A40",         # Lines
    
    "primary": "#2C5CA3",        # Main Blue
    "primary_hover": "#1E447A",
    "accent": "#20B685",         # Point Green
    "danger": "#FA5252",         # Red
    
    "text_main": "#FFFFFF",
    "text_sub": "#909296",
    
    # 파일 타입별 아이콘 색상
    "type_pdf": "#FF6B6B",
    "type_doc": "#4D96FF",
    "type_hwp": "#3BC9DB",
    "type_txt": "#CED4DA",
    "type_img": "#FCC419"
}

# 폰트 설정 (OS 최적화)
SYSTEM_FONT = "Segoe UI" if platform.system() == "Windows" else "Apple SD Gothic Neo"
FONTS = {
    "title": (SYSTEM_FONT, 24, "bold"),
    "header": (SYSTEM_FONT, 18, "bold"),
    "body": (SYSTEM_FONT, 13),
    "body_bold": (SYSTEM_FONT, 13, "bold"),
    "caption": (SYSTEM_FONT, 11),
    "emoji": ("Segoe UI Emoji", 14)
}

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")


# ==========================================
# 2. 폰트 매니저 (한글 깨짐 방지)
# ==========================================
class FontManager:
    """PDF 생성 시 한글이 깨지지 않도록 시스템 폰트를 찾아 등록"""
    _font_name = "MalgunGothic"
    _registered = False

    @classmethod
    def get_font(cls):
        if cls._registered: return cls._font_name
        
        candidates = []
        if platform.system() == "Windows":
            candidates = ["C:\\Windows\\Fonts\\malgun.ttf", "C:\\Windows\\Fonts\\batang.tc"]
        elif platform.system() == "Darwin":
            candidates = ["/System/Library/Fonts/AppleGothic.ttf", "/Library/Fonts/NanumGothic.ttf"]
        else:
            candidates = ["/usr/share/fonts/truetype/nanum/NanumGothic.ttf"]

        font_path = None
        for path in candidates:
            if os.path.exists(path):
                font_path = path
                break
        
        if font_path:
            try:
                pdfmetrics.registerFont(TTFont(cls._font_name, font_path))
                cls._registered = True
            except:
                cls._font_name = "Helvetica" # Fallback
        else:
            cls._font_name = "Helvetica"

        return cls._font_name


# ==========================================
# 3. 변환 엔진 (HWP, TXT, DOCX -> PDF)
# ==========================================
# ==========================================
# 3. 변환 엔진 (강력해진 CSV/엑셀 처리)
# ==========================================

class ConverterEngine:
    """
    다양한 파일 포맷(HWP, Excel, CSV, Word, Image)을 PDF로 변환합니다.
    (스레드 안전성 확보 및 HWP 지원 추가됨)
    """
    
    @staticmethod
    def to_pdf(input_path, output_folder):
        ext = os.path.splitext(input_path)[1].lower()
        filename = os.path.splitext(os.path.basename(input_path))[0]
        temp_pdf = os.path.join(output_folder, f"temp_{filename}.pdf")

        # Win32 COM 객체를 스레드에서 사용하기 위한 초기화 (필수)
        if HAS_WIN32:
            pythoncom.CoInitialize()

        try:
            # 1. PDF (그대로 반환)
            if ext == ".pdf":
                return input_path

            # 2. HWP (한글 파일)
            elif ext in [".hwp", ".hwpx"]:
                if platform.system() == "Windows" and HAS_WIN32:
                    return ConverterEngine._hwp_to_pdf(input_path, temp_pdf)
                else:
                    raise Exception("HWP 변환은 Windows 환경에서 한글(Hwp)이 설치되어 있어야 가능합니다.")

            # 3. Excel & CSV
            elif ext in [".xlsx", ".xls", ".csv"]:
                return ConverterEngine._excel_to_pdf(input_path, temp_pdf)

            # 4. Word (Windows 전용)
            elif ext in [".docx", ".doc"]:
                if platform.system() == "Windows":
                    try:
                        convert_docx(input_path, temp_pdf)
                        return temp_pdf
                    except Exception as e:
                        raise Exception(f"Word 변환 실패: {e}")
                else:
                    raise Exception("Word 변환은 Windows 환경에서만 지원됩니다.")

            # 5. Images
            elif ext in [".jpg", ".jpeg", ".png", ".bmp", ".gif"]:
                img = Image.open(input_path).convert('RGB')
                img.save(temp_pdf)
                return temp_pdf

            # 6. HTML
            elif ext in [".html", ".htm"]:
                with open(input_path, "r", encoding="utf-8") as f:
                    html_str = f.read()
                return ConverterEngine._html_to_pdf(html_str, temp_pdf)
            
            else:
                return None # 지원하지 않는 포맷

        except Exception as e:
            raise Exception(f"{filename} 변환 중 오류: {str(e)}")
        finally:
            # 스레드 정리
            if HAS_WIN32:
                pythoncom.CoUninitialize()

    @staticmethod
    def _hwp_to_pdf(input_path, output_path):
        """HWP 파일을 PDF로 변환 (한글 오토메이션 사용)"""
        hwp = None
        try:
            # HWP 오브젝트 생성
            hwp = win32com.client.Dispatch("HWPFrame.HwpObject")
            hwp.RegisterModule("FilePathCheckDLL", "FilePathCheckerModule") # 보안 팝업 우회 시도
            hwp.XHwpWindows.Item(0).Visible = False # 백그라운드 실행
            
            # 파일 열기
            hwp.Open(input_path)
            
            # PDF 저장 설정
            hwp.HAction.GetDefault("FileSaveAs_S", hwp.HParameterSet.HFileSaveAs.HSet)
            hwp.HParameterSet.HFileSaveAs.FileName = output_path
            hwp.HParameterSet.HFileSaveAs.Format = "PDF"
            
            # 저장 실행
            if not hwp.HAction.Execute("FileSaveAs_S", hwp.HParameterSet.HFileSaveAs.HSet):
                raise Exception("HWP 저장 액션 실패 (권한 또는 파일 상태 확인)")
                
            return output_path
            
        except Exception as e:
            raise Exception(f"한글(HWP) 제어 오류: {e}")
        finally:
            if hwp:
                hwp.Quit()

    @staticmethod
    def _excel_to_pdf(path, output_path):
        """
        Excel/CSV -> HTML -> PDF 변환 프로세스
        """
        dfs = {}
        
        # 1. CSV / 엑셀 데이터 로드
        if path.lower().endswith('.csv'):
            encodings = ['utf-8-sig', 'cp949', 'euc-kr', 'latin1']
            loaded = False
            
            for enc in encodings:
                try:
                    # pd가 import 되어 있어야 함
                    try:
                        dfs['Sheet1'] = pd.read_csv(path, encoding=enc, dtype=str, on_bad_lines='skip')
                    except TypeError:
                        dfs['Sheet1'] = pd.read_csv(path, encoding=enc, dtype=str, error_bad_lines=False)
                    loaded = True
                    break
                except Exception:
                    continue
            
            if not loaded:
                raise Exception("CSV 파일의 인코딩을 인식할 수 없습니다.")
        else:
            try:
                dfs = pd.read_excel(path, sheet_name=None, dtype=str)
            except Exception as e:
                raise Exception(f"Excel 읽기 오류: {e}")

        # 2. 한글 폰트 준비
        font_name = FontManager.get_font()

        # 3. HTML 스타일링
        css = f"""
        <style>
            @page {{
                size: a4 landscape;
                margin: 1cm;
                @frame footer_frame {{
                    -pdf-frame-content: footerContent;
                    bottom: 0cm; height: 1cm;
                }}
            }}
            body {{ font-family: '{font_name}', sans-serif; }}
            h2 {{
                font-size: 14pt; color: #333;
                border-bottom: 2px solid {COLORS['primary']};
                margin-top: 20px; margin-bottom: 10px;
            }}
            table {{
                width: 100%; border-collapse: collapse; font-size: 9pt;
            }}
            th {{
                background-color: #f1f3f5; border: 1px solid #ddd;
                padding: 6px; font-weight: bold; text-align: center;
            }}
            td {{
                border: 1px solid #ddd; padding: 6px;
                vertical-align: top; word-wrap: break-word;
            }}
            tr:nth-child(even) {{ background-color: #f9f9f9; }}
        </style>
        """
        
        html_content = f"<html><head>{css}</head><body>"
        has_data = False
        
        for sheet_name, df in dfs.items():
            if not df.empty and len(df.columns) > 0:
                has_data = True
                df = df.fillna("")
                html_content += f"<h2>📄 {sheet_name}</h2>"
                html_content += df.to_html(index=False, header=True, border=0)
                html_content += "<pdf:nextpage />"

        html_content += "</body></html>"
        
        if not has_data:
            raise Exception("데이터가 없는 빈 파일입니다.")

        return ConverterEngine._html_to_pdf(html_content, output_path)

    @staticmethod
    def _html_to_pdf(source_html, output_path):
        try:
            with open(output_path, "w+b") as f:
                pisa_status = pisa.CreatePDF(source_html, dest=f, encoding='utf-8')
            
            if pisa_status.err:
                raise Exception(f"PDF 생성 엔진 오류 (Code: {pisa_status.err})")
            return output_path
        except Exception as e:
            raise Exception(f"PDF 저장 실패: {e}")
# ==========================================
# 4. PDF 프로세서 (병합/분할/회전)
# ==========================================
# ==========================================
# 4. PDF 프로세서 (병합/분할/회전) - pikepdf 사용
# ==========================================
class PDFProcessor:
    @staticmethod
    def merge(file_list, save_path, progress_callback):
        if HAS_PIKEPDF:
            return PDFProcessor._merge_pikepdf(file_list, save_path, progress_callback)
        else:
            return PDFProcessor._merge_pypdf2(file_list, save_path, progress_callback)

    @staticmethod
    def _merge_pikepdf(file_list, save_path, progress_callback):
        """pikepdf를 사용한 병합 (양식/색상 완벽 보존)"""
        pdf_out = pikepdf.new()
        total = len(file_list)
        skipped = []

        for i, path in enumerate(file_list):
            try:
                # pikepdf로 PDF 열기 (암호화 자동 처리)
                with pikepdf.open(path, password="", allow_overwriting_input=False) as pdf_in:
                    # 모든 페이지 복사 (완벽한 보존)
                    pdf_out.pages.extend(pdf_in.pages)

            except pikepdf.PasswordError:
                skipped.append(f"{os.path.basename(path)}: 비밀번호 필요")
            except Exception as e:
                error_msg = str(e)
                skipped.append(f"{os.path.basename(path)}: {error_msg[:50]}")

            if progress_callback:
                progress_callback(0.5 + ((i+1)/total * 0.5))

        # 저장
        pdf_out.save(save_path)
        pdf_out.close()

        # 스킵된 파일이 있으면 경고 표시
        if skipped:
            warning = "\n".join(skipped[:5])
            if len(skipped) > 5:
                warning += f"\n... 외 {len(skipped)-5}개"
            raise Exception(f"일부 파일을 건너뛰었습니다:\n\n{warning}")

        return True

    @staticmethod
    def _merge_pypdf2(file_list, save_path, progress_callback):
        """PyPDF2를 사용한 병합 (Fallback)"""
        writer = PyPDF2.PdfWriter()
        total = len(file_list)
        skipped = []

        for i, path in enumerate(file_list):
            try:
                reader = PyPDF2.PdfReader(path)
                if reader.is_encrypted:
                    try:
                        reader.decrypt("")
                    except Exception:
                        skipped.append(f"{os.path.basename(path)}: 암호화 오류")
                        continue

                for page in reader.pages:
                    writer.add_page(page)

            except Exception as e:
                skipped.append(f"{os.path.basename(path)}: {str(e)[:50]}")

            if progress_callback:
                progress_callback(0.5 + ((i+1)/total * 0.5))

        with open(save_path, "wb") as f:
            writer.write(f)

        if skipped:
            warning = "\n".join(skipped[:5])
            if len(skipped) > 5:
                warning += f"\n... 외 {len(skipped)-5}개"
            raise Exception(f"일부 파일을 건너뛰었습니다:\n\n{warning}")

        return True

    @staticmethod
    def split(path, mode, val, progress_callback):
        if HAS_PIKEPDF:
            return PDFProcessor._split_pikepdf(path, mode, val, progress_callback)
        else:
            return PDFProcessor._split_pypdf2(path, mode, val, progress_callback)

    @staticmethod
    def _split_pikepdf(path, mode, val, progress_callback):
        """pikepdf를 사용한 분할 (양식/색상 완벽 보존)"""
        try:
            # PDF 열기 (암호화 자동 처리)
            pdf_in = pikepdf.open(path, password="", allow_overwriting_input=False)
            total = len(pdf_in.pages)
        except pikepdf.PasswordError:
            raise Exception("암호화된 PDF 파일입니다.\n비밀번호를 해제한 후 다시 시도하세요.")
        except Exception as e:
            raise Exception(f"PDF 파일을 읽을 수 없습니다: {e}")

        base = os.path.dirname(path)
        name = os.path.splitext(os.path.basename(path))[0]
        out_dir = os.path.join(base, f"{name}_split")
        os.makedirs(out_dir, exist_ok=True)

        # 1. 균등 분할 (예: 2페이지씩)
        if mode == "equal":
            try:
                step = int(val)
                if step < 1: raise ValueError
            except:
                pdf_in.close()
                raise Exception("균등 분할은 '1 이상의 정수'를 입력해야 합니다.")

            for s in range(0, total, step):
                e = min(s+step, total)
                pdf_out = pikepdf.new()

                # 페이지 복사 (완벽한 보존)
                for i in range(s, e):
                    pdf_out.pages.append(pdf_in.pages[i])

                # 파일 저장
                out_name = f"{name}_{s+1}-{e}.pdf"
                pdf_out.save(os.path.join(out_dir, out_name))
                pdf_out.close()

                if progress_callback:
                    progress_callback(min((s+step)/total, 1.0))

            pdf_in.close()
            return True, out_dir # 폴더 경로 반환

        # 2. 범위 추출 (예: 1-3, 5)
        elif mode == "range":
            pages = set()
            try:
                for p in val.split(','):
                    p = p.strip()
                    if not p:  # 빈 문자열 무시
                        continue
                    if '-' in p:
                        parts = p.split('-')
                        if len(parts) != 2:
                            raise ValueError(f"잘못된 범위 형식: {p}")
                        s, e = map(int, parts)
                        if s < 1 or e < 1:
                            raise ValueError("페이지 번호는 1 이상이어야 합니다.")
                        if s > e:
                            raise ValueError(f"시작 페이지({s})가 끝 페이지({e})보다 큽니다.")
                        # 1-based를 0-based로 변환, 끝 페이지 포함
                        pages.update(range(s-1, e))
                    else:
                        page_num = int(p)
                        if page_num < 1:
                            raise ValueError("페이지 번호는 1 이상이어야 합니다.")
                        pages.add(page_num - 1)
            except ValueError as ve:
                pdf_in.close()
                raise Exception(f"입력 오류: {ve}\n올바른 형식 예: 1-3, 5, 7-10")
            except Exception as e:
                pdf_in.close()
                raise Exception(f"입력 처리 중 오류: {e}")

            page_list = sorted([p for p in pages if 0 <= p < total])

            # 범위를 벗어난 페이지가 있는지 확인
            invalid_pages = [p+1 for p in pages if p >= total or p < 0]
            if invalid_pages:
                pdf_in.close()
                raise Exception(f"범위를 벗어난 페이지: {invalid_pages}\n(전체 {total}페이지)")

            if not page_list:
                pdf_in.close()
                raise Exception("추출할 페이지가 없습니다.")

            pdf_out = pikepdf.new()
            for i in page_list:
                pdf_out.pages.append(pdf_in.pages[i])

            out_path = os.path.join(out_dir, f"{name}_extract.pdf")
            pdf_out.save(out_path)
            pdf_out.close()
            pdf_in.close()

            if progress_callback: progress_callback(1.0)
            return True, out_path # 파일 경로 반환

        pdf_in.close()
        return False, "잘못된 모드입니다."

    @staticmethod
    def _split_pypdf2(path, mode, val, progress_callback):
        """PyPDF2를 사용한 분할 (Fallback)"""
        try:
            reader = PyPDF2.PdfReader(path)
            if reader.is_encrypted:
                try:
                    reader.decrypt("")
                except Exception:
                    raise Exception("암호화된 PDF 파일입니다.")
            total = len(reader.pages)
        except Exception as e:
            raise Exception(f"PDF 파일을 읽을 수 없습니다: {e}")

        base = os.path.dirname(path)
        name = os.path.splitext(os.path.basename(path))[0]
        out_dir = os.path.join(base, f"{name}_split")
        os.makedirs(out_dir, exist_ok=True)

        if mode == "equal":
            try:
                step = int(val)
                if step < 1: raise ValueError
            except:
                raise Exception("균등 분할은 '1 이상의 정수'를 입력해야 합니다.")

            for s in range(0, total, step):
                e = min(s+step, total)
                writer = PyPDF2.PdfWriter()
                for i in range(s, e):
                    writer.add_page(reader.pages[i])

                out_name = f"{name}_{s+1}-{e}.pdf"
                with open(os.path.join(out_dir, out_name), "wb") as f:
                    writer.write(f)

                if progress_callback:
                    progress_callback(min((s+step)/total, 1.0))

            return True, out_dir

        elif mode == "range":
            pages = set()
            try:
                for p in val.split(','):
                    p = p.strip()
                    if not p: continue
                    if '-' in p:
                        parts = p.split('-')
                        if len(parts) != 2:
                            raise ValueError(f"잘못된 범위 형식: {p}")
                        s, e = map(int, parts)
                        if s < 1 or e < 1:
                            raise ValueError("페이지 번호는 1 이상이어야 합니다.")
                        if s > e:
                            raise ValueError(f"시작 페이지({s})가 끝 페이지({e})보다 큽니다.")
                        pages.update(range(s-1, e))
                    else:
                        page_num = int(p)
                        if page_num < 1:
                            raise ValueError("페이지 번호는 1 이상이어야 합니다.")
                        pages.add(page_num - 1)
            except ValueError as ve:
                raise Exception(f"입력 오류: {ve}\n올바른 형식 예: 1-3, 5, 7-10")
            except Exception as e:
                raise Exception(f"입력 처리 중 오류: {e}")

            page_list = sorted([p for p in pages if 0 <= p < total])
            invalid_pages = [p+1 for p in pages if p >= total or p < 0]
            if invalid_pages:
                raise Exception(f"범위를 벗어난 페이지: {invalid_pages}\n(전체 {total}페이지)")
            if not page_list:
                raise Exception("추출할 페이지가 없습니다.")

            writer = PyPDF2.PdfWriter()
            for i in page_list:
                writer.add_page(reader.pages[i])

            out_path = os.path.join(out_dir, f"{name}_extract.pdf")
            with open(out_path, "wb") as f:
                writer.write(f)

            if progress_callback: progress_callback(1.0)
            return True, out_path

        return False, "잘못된 모드입니다."

    @staticmethod
    def rotate(path, deg, progress_callback):
        if HAS_PIKEPDF:
            return PDFProcessor._rotate_pikepdf(path, deg, progress_callback)
        else:
            return PDFProcessor._rotate_pypdf2(path, deg, progress_callback)

    @staticmethod
    def _rotate_pikepdf(path, deg, progress_callback):
        """pikepdf를 사용한 회전 (양식/색상 완벽 보존)"""
        try:
            pdf_in = pikepdf.open(path, password="", allow_overwriting_input=False)
            total = len(pdf_in.pages)
        except pikepdf.PasswordError:
            raise Exception("암호화된 PDF 파일입니다.\n비밀번호를 해제한 후 다시 시도하세요.")
        except Exception as e:
            raise Exception(f"PDF 파일을 읽을 수 없습니다: {e}")

        # 페이지 회전 (in-place)
        for i, page in enumerate(pdf_in.pages):
            page.Rotate = (page.Rotate if hasattr(page, 'Rotate') else 0) + deg
            if progress_callback:
                progress_callback((i+1)/total)

        out_path = os.path.join(os.path.dirname(path), f"rotated_{os.path.basename(path)}")
        pdf_in.save(out_path)
        pdf_in.close()
        return True, out_path

    @staticmethod
    def _rotate_pypdf2(path, deg, progress_callback):
        """PyPDF2를 사용한 회전 (Fallback)"""
        try:
            reader = PyPDF2.PdfReader(path)
            if reader.is_encrypted:
                try:
                    reader.decrypt("")
                except Exception:
                    raise Exception("암호화된 PDF 파일입니다.")
            total = len(reader.pages)
        except Exception as e:
            raise Exception(f"PDF 파일을 읽을 수 없습니다: {e}")

        writer = PyPDF2.PdfWriter()
        for i, p in enumerate(reader.pages):
            p.rotate(deg)
            writer.add_page(p)
            if progress_callback:
                progress_callback((i+1)/total)

        out_path = os.path.join(os.path.dirname(path), f"rotated_{os.path.basename(path)}")
        with open(out_path, "wb") as f:
            writer.write(f)
        return True, out_path


# ==========================================
# 5. UI 컴포넌트 (Modern UI)
# ==========================================
class ModernButton(ctk.CTkButton):
    def __init__(self, master, **kwargs):
        kwargs.setdefault("height", 42)
        kwargs.setdefault("corner_radius", 8)
        kwargs.setdefault("font", FONTS["body_bold"])
        if "fg_color" not in kwargs:
            kwargs["fg_color"] = COLORS["primary"]
            kwargs["hover_color"] = COLORS["primary_hover"]
        super().__init__(master, **kwargs)

class FileListItem(ctk.CTkFrame):
    def __init__(self, master, path, on_del, on_up, on_down, **kwargs):
        super().__init__(master, fg_color=COLORS["surface"], corner_radius=10, **kwargs)
        self.path = path
        
        ext = os.path.splitext(path)[1].lower()
        icon, color = "📄", COLORS["text_sub"]
        
        if ext == ".pdf": icon, color = "📕 PDF", COLORS["type_pdf"]
        elif ext in [".docx", ".doc"]: icon, color = "📘 DOC", COLORS["type_doc"]
        elif ext in [".hwp", ".hwpx"]: icon, color = "📒 HWP", COLORS["type_hwp"]
        elif ext == ".txt": icon, color = "📝 TXT", COLORS["type_txt"]
        elif ext in [".jpg", ".png"]: icon, color = "🖼️ IMG", COLORS["type_img"]

        badge = ctk.CTkLabel(self, text=icon, font=("Arial", 11, "bold"), text_color=color, width=60)
        badge.pack(side="left", padx=(15, 5), pady=12)

        name_lbl = ctk.CTkLabel(self, text=os.path.basename(path), font=FONTS["body"], text_color=COLORS["text_main"], anchor="w")
        name_lbl.pack(side="left", fill="x", expand=True)

        btn_kw = {"width": 32, "height": 32, "fg_color": "transparent", "font": ("Arial", 14), "corner_radius": 6}
        
        ctk.CTkButton(self, text="✕", text_color=COLORS["danger"], hover_color="#331010", 
                      command=lambda: on_del(self), **btn_kw).pack(side="right", padx=(0, 10))
        ctk.CTkButton(self, text="▼", text_color=COLORS["text_sub"], hover_color=COLORS["surface_hover"], 
                      command=lambda: on_down(self), **btn_kw).pack(side="right")
        ctk.CTkButton(self, text="▲", text_color=COLORS["text_sub"], hover_color=COLORS["surface_hover"], 
                      command=lambda: on_up(self), **btn_kw).pack(side="right")


# ==========================================
# 6. 메인 애플리케이션 (수정됨)
# ==========================================
class App(ctk.CTk, TkinterDnD.DnDWrapper):
    def __init__(self):
        super().__init__()
        self.TkdndVersion = TkinterDnD._require(self)
        
        self.title(APP_NAME)
        self.geometry("1000x750")
        self.configure(fg_color=COLORS["bg"])
        
        self.temp_dir = os.path.join(os.getcwd(), "temp_workspace")
        if not os.path.exists(self.temp_dir): os.makedirs(self.temp_dir)
        
        self.merge_items = [] 
        self.split_target = None
        self.rot_target = None

        self._setup_ui()
        
        self.drop_target_register(DND_FILES)
        self.dnd_bind('<<Drop>>', self.on_drop)

    def _setup_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.tabs = ctk.CTkTabview(self, fg_color="transparent",
                                   segmented_button_fg_color=COLORS["surface"],
                                   segmented_button_selected_color=COLORS["primary"],
                                   segmented_button_selected_hover_color=COLORS["primary_hover"],
                                   segmented_button_unselected_hover_color=COLORS["surface_hover"],
                                   text_color=COLORS["text_sub"])
        self.tabs._segmented_button.configure(font=FONTS["header"], height=45)
        self.tabs.grid(row=0, column=0, padx=30, pady=(20, 0), sticky="nsew")
        
        self.tab_merge = self.tabs.add("  문서 합치기  ")
        self.tab_split = self.tabs.add("  나누기 / 추출  ")
        self.tab_rot = self.tabs.add("  PDF 회전  ")

        self._init_merge()
        self._init_split()
        self._init_rotate()

        self.footer = ctk.CTkFrame(self, height=50, fg_color=COLORS["surface"], corner_radius=0)
        self.footer.grid(row=1, column=0, sticky="ew")
        
        self.status_icon = ctk.CTkLabel(self.footer, text="⚡", font=FONTS["emoji"])
        self.status_icon.pack(side="left", padx=(30, 5))
        
        self.status_lbl = ctk.CTkLabel(self.footer, text="준비 완료", text_color=COLORS["text_sub"], font=FONTS["caption"])
        self.status_lbl.pack(side="left")
        
        self.prog_bar = ctk.CTkProgressBar(self.footer, width=250, height=8, progress_color=COLORS["accent"])
        self.prog_bar.set(0)
        self.prog_bar.pack(side="right", padx=30)

    # --- [TAB 1] Merge ---
    def _init_merge(self):
        t = self.tab_merge
        t.grid_columnconfigure(0, weight=1)
        t.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(t, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(10, 10))
        ctk.CTkLabel(header, text="모든 문서를 하나의 PDF로 병합", font=FONTS["header"], text_color=COLORS["text_main"]).pack(anchor="w")
        ctk.CTkLabel(header, text="지원: PDF, Word, HWP(한글), Excel, Image, HTML", font=FONTS["body"], text_color=COLORS["primary"]).pack(anchor="w")

        self.scroll_area = ctk.CTkScrollableFrame(t, fg_color="transparent")
        self.scroll_area.grid(row=1, column=0, sticky="nsew", pady=5)
        
        self.empty_view = ctk.CTkFrame(self.scroll_area, fg_color=COLORS["surface"], corner_radius=15, border_width=2, border_color=COLORS["border"])
        self.empty_view.pack(fill="x", ipady=60)
        ctk.CTkLabel(self.empty_view, text="📂", font=("Segoe UI Emoji", 56)).pack(pady=(30,10))
        ctk.CTkLabel(self.empty_view, text="여기에 파일을 드래그하세요", font=FONTS["header"], text_color=COLORS["text_main"]).pack()
        
        actions = ctk.CTkFrame(t, fg_color="transparent")
        actions.grid(row=2, column=0, sticky="ew", pady=20)
        
        ModernButton(actions, text="+ 파일 선택", command=self.add_file_dialog, 
                     fg_color=COLORS["surface"], hover_color=COLORS["surface_hover"], width=140).pack(side="left")
        
        ctk.CTkButton(actions, text="초기화", command=self.clear_list, width=100, height=40, corner_radius=8,
                      fg_color="transparent", border_width=1, border_color=COLORS["danger"], 
                      text_color=COLORS["danger"], hover_color="#331010", font=FONTS["body_bold"]).pack(side="left", padx=10)

        self.btn_run_merge = ModernButton(actions, text="PDF로 변환 및 합치기 시작", state="disabled", command=self.run_merge)
        self.btn_run_merge.pack(side="right", fill="x", expand=True, padx=(20, 0))

    def on_drop(self, event):
        data = event.data
        if not data: return
        paths = [p.strip("{}") for p in data.split("} {")] if "{" in data else data.split()
        self.add_files(paths)

    def add_file_dialog(self):
        files = filedialog.askopenfilenames()
        if files: self.add_files(files)

    def add_files(self, paths):
        self.empty_view.pack_forget()
        for p in paths:
            if os.path.isfile(p):
                FileListItem(self.scroll_area, p, self.del_item, self.up_item, self.down_item).pack(fill="x", pady=4)
        self._sync_ui()

    def _sync_ui(self):
        items = self.scroll_area.winfo_children()
        has_files = any(isinstance(c, FileListItem) for c in items)
        
        if not has_files:
            self.empty_view.pack(fill="x", ipady=60)
            self.btn_run_merge.configure(state="disabled")
            self.status_lbl.configure(text="목록이 비었습니다.")
        else:
            self.btn_run_merge.configure(state="normal")
            count = sum(1 for c in items if isinstance(c, FileListItem))
            self.status_lbl.configure(text=f"총 {count}개 파일 대기 중")

    def del_item(self, widget):
        widget.destroy()
        self.after(50, self._sync_ui)

    def clear_list(self):
        for child in self.scroll_area.winfo_children():
            if isinstance(child, FileListItem): child.destroy()
        self._sync_ui()

    def up_item(self, widget):
        children = self.scroll_area.winfo_children()
        idx = children.index(widget)
        if idx > 0: widget.pack(before=children[idx-1])

    def down_item(self, widget):
        children = self.scroll_area.winfo_children()
        idx = children.index(widget)
        if idx < len(children) - 1: widget.pack(after=children[idx+1])

    def run_merge(self):
        files = []
        for child in self.scroll_area.winfo_children():
            if isinstance(child, FileListItem):
                files.append(child.path)
        
        if not files: return
        
        save_path = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF", "*.pdf")])
        if not save_path: return
        
        self._lock_ui(True)
        threading.Thread(target=self._worker_merge, args=(files, save_path), daemon=True).start()

    def _worker_merge(self, files, save_path):
        temp_files = []
        errors = []
        total = len(files)
        
        try:
            for i, f in enumerate(files):
                self.status_lbl.configure(text=f"변환 중 ({i+1}/{total}): {os.path.basename(f)}")
                try:
                    pdf = ConverterEngine.to_pdf(f, self.temp_dir)
                    if pdf: temp_files.append(pdf)
                except Exception as e:
                    errors.append(f"{os.path.basename(f)}: {e}")
                
                self.prog_bar.set((i+1)/total * 0.5)

            if temp_files:
                self.status_lbl.configure(text="PDF 병합 중...")
                PDFProcessor.merge(temp_files, save_path, self.prog_bar.set)
                self.after(0, lambda: self._finish(True, save_path, "합치기", errors))
            else:
                self.after(0, lambda: self._finish(False, "변환된 파일이 없습니다.", "합치기", errors))
            
            for t in temp_files:
                if self.temp_dir in t:
                    try: os.remove(t)
                    except: pass

        except Exception as e:
            self.after(0, lambda: self._finish(False, str(e), "합치기", errors))

    # --- [TAB 2] Split ---
    def _init_split(self):
        t = self.tab_split
        f = ctk.CTkFrame(t, fg_color="transparent")
        f.pack(fill="both", padx=40, pady=40)
        
        ctk.CTkLabel(f, text="PDF 나누기 / 추출", font=FONTS["header"]).pack(anchor="w")
        self.lbl_split = ctk.CTkLabel(f, text="선택 없음", text_color=COLORS["text_sub"])
        self.lbl_split.pack(pady=10)
        ModernButton(f, text="📂 파일 선택", fg_color=COLORS["surface"], command=self.sel_split).pack()
        
        self.split_mode = ctk.StringVar(value="equal")
        ctk.CTkRadioButton(f, text="균등 분할 (예: 2 입력 시 2쪽씩 자름)", variable=self.split_mode, value="equal").pack(pady=10)
        ctk.CTkRadioButton(f, text="범위 추출 (예: 1-3, 5)", variable=self.split_mode, value="range").pack()
        
        self.ent_split = ctk.CTkEntry(f, placeholder_text="값 입력")
        self.ent_split.pack(pady=10, fill="x")
        
        self.btn_run_split = ModernButton(f, text="실행", state="disabled", command=self.run_split)
        self.btn_run_split.pack(pady=20, fill="x")

    def sel_split(self):
        f = filedialog.askopenfilename(filetypes=[("PDF", "*.pdf")])
        if f:
            self.split_target = f
            self.lbl_split.configure(text=os.path.basename(f))
            self.btn_run_split.configure(state="normal")

    def run_split(self):
        val = self.ent_split.get()
        if not val:
            messagebox.showwarning("입력 필요", "나누거나 추출할 값을 입력해주세요.")
            return

        self._lock_ui(True)

        # [수정] 인자를 리스트로 묶어서 전달 (작업 이름 "나누기"가 함수 인자로 들어가는 것 방지)
        args = [self.split_target, self.split_mode.get(), val]

        threading.Thread(
            target=lambda: self._worker_sub(PDFProcessor.split, args, "나누기"),
            daemon=True
        ).start()

    # --- [TAB 3] Rotate ---
    def _init_rotate(self):
        t = self.tab_rot
        f = ctk.CTkFrame(t, fg_color="transparent")
        f.pack(fill="both", padx=40, pady=40)
        
        ctk.CTkLabel(f, text="PDF 회전", font=FONTS["header"]).pack()
        self.lbl_rot = ctk.CTkLabel(f, text="선택 없음", text_color=COLORS["text_sub"])
        self.lbl_rot.pack(pady=10)
        ModernButton(f, text="📂 파일 선택", fg_color=COLORS["surface"], command=self.sel_rot).pack()
        
        self.rot_val = ctk.IntVar(value=90)
        ctk.CTkRadioButton(f, text="시계방향 90도 회전", variable=self.rot_val, value=90).pack(pady=5)
        ctk.CTkRadioButton(f, text="180도 회전", variable=self.rot_val, value=180).pack(pady=5)
        
        self.btn_run_rot = ModernButton(f, text="회전 저장", state="disabled", command=self.run_rot)
        self.btn_run_rot.pack(pady=20, fill="x")

    def sel_rot(self):
        f = filedialog.askopenfilename(filetypes=[("PDF", "*.pdf")])
        if f:
            self.rot_target = f
            self.lbl_rot.configure(text=os.path.basename(f))
            self.btn_run_rot.configure(state="normal")

    def run_rot(self):
        self._lock_ui(True)

        # [수정] 인자를 리스트로 묶어서 전달
        args = [self.rot_target, self.rot_val.get()]

        threading.Thread(
            target=lambda: self._worker_sub(PDFProcessor.rotate, args, "회전"),
            daemon=True
        ).start()

    # --- [Common Worker] 중요 수정됨 ---
    def _worker_sub(self, func, args_list, label_text):
        """
        func: 실행할 함수 (split, rotate 등)
        args_list: 함수에 들어갈 인자 리스트 (callback 제외)
        label_text: 완료 시 메시지에 띄울 작업 이름
        """
        try:
            # func 실행 시 인자 리스트를 풀어서(*args_list) 넣고, 마지막에 콜백 추가
            ok, res = func(*args_list, self.prog_bar.set)
            self.after(0, lambda: self._finish(ok, res, label_text, []))
        except Exception as e:
            self.after(0, lambda: self._finish(False, str(e), "오류", []))

    def _lock_ui(self, busy):
        state = "disabled" if busy else "normal"
        self.btn_run_merge.configure(state=state)
        self.btn_run_split.configure(state=state)
        self.btn_run_rot.configure(state=state)
        if busy:
            self.status_lbl.configure(text="작업 처리 중... 잠시만 기다려주세요.")
            self.status_icon.configure(text="⏳")
            self.prog_bar.set(0)
        else:
            self.status_icon.configure(text="✅")

    def _finish(self, success, result, mode, errors):
        self._lock_ui(False)
        self.prog_bar.set(1)
        if success:
            self.status_lbl.configure(text="작업 완료")
            msg = f"{mode} 작업이 성공했습니다."
            if errors: msg += f"\n\n[실패 파일]\n{chr(10).join(errors[:3])}"
            
            if messagebox.askyesno("완료", msg + "\n\n결과물을 확인하시겠습니까?"):
                try:
                    if platform.system() == "Windows": os.startfile(result)
                    elif platform.system() == "Darwin": subprocess.Popen(["open", result])
                    else: subprocess.Popen(["xdg-open", result])
                except:
                    messagebox.showinfo("알림", f"저장 위치:\n{result}")
        else:
            self.status_lbl.configure(text="오류 발생")
            messagebox.showerror("실패", result)

    def _worker_sub(self, func, args_list, label_text):
        """
        func: 실행할 함수 (split, rotate 등)
        args_list: 함수에 들어갈 인자 리스트 (callback 제외)
        label_text: 완료 시 메시지에 띄울 작업 이름
        """
        try:
            # func 실행 시 인자 리스트를 풀어서(*args_list) 넣고, 마지막에 콜백 추가
            ok, res = func(*args_list, self.prog_bar.set)
            self.after(0, lambda: self._finish(ok, res, label_text, []))
        except Exception as e:
            error_msg = str(e)
            self.after(0, lambda: self._finish(False, error_msg, "오류", []))

if __name__ == "__main__":
    app = App()
    app.mainloop()