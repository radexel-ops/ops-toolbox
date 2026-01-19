from cx_Freeze import setup, Executable

# Dependency packages
build_exe_options = {
    "packages": ["tkinter", "PyPDF2", "csv", "os"],
    "excludes": [],
    "include_files": []  # 필요한 추가 파일이 있다면 이곳에 추가하십시오.
}

# Set to GUI application instead of console application
base = "Win32GUI"  # GUI 기반 응용 프로그램으로 변경

setup(
    name="PDFlex",
    version="1.0",
    description="A versatile PDF management tool",
    options={"build_exe": build_exe_options},
    executables=[Executable("PDF_S_M.py", base=base)]  # 스크립트 이름과 아이콘을 적절하게 변경
)
