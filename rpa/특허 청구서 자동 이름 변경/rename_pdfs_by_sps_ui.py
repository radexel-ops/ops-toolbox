#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Batch-rename PDFs to the first ID matching the pattern "SPS00-0000" (e.g., SPS25-3566)
found inside each PDF's text.

UI MODE (default if no args):
- Choose folder (Browse)
- Select Dry-run or Rename (apply)
- Options: recursive, pages to scan, pattern
- Click [실행] to run; logs appear in the window

CLI MODE (backward compatible):
  python rename_pdfs_by_sps_ui.py "D:\\work\\invoices"           # dry-run
  python rename_pdfs_by_sps_ui.py "D:\\work\\invoices" --apply   # actually rename
  python rename_pdfs_by_sps_ui.py . --apply -r                   # include subfolders
  python rename_pdfs_by_sps_ui.py --ui                           # force open GUI

Requires: pip install pypdf
Default pattern: \\bSPS\\d{2}-\\d{4}\\b
"""
from __future__ import annotations
import argparse
import re
import sys
import threading
from pathlib import Path
from typing import Callable, Optional

# ---- PDF logic --------------------------------------------------------------
try:
    from pypdf import PdfReader  # type: ignore
except Exception:
    PdfReader = None  # type: ignore


def find_match_in_pdf(pdf_path: Path, rx: re.Pattern, max_pages: int) -> Optional[str]:
    try:
        reader = PdfReader(str(pdf_path))
    except Exception as e:
        return None

    texts = []
    for i, page in enumerate(reader.pages):
        if i >= max_pages:
            break
        try:
            txt = page.extract_text() or ""
        except Exception:
            txt = ""
        texts.append(txt)

    full_text = "\n".join(texts)
    m = rx.search(full_text)
    return m.group(0) if m else None


def unique_target_path(dirpath: Path, basename: str, ext: str = ".pdf") -> Path:
    target = dirpath / f"{basename}{ext}"
    idx = 1
    while target.exists():
        target = dirpath / f"{basename}-{idx}{ext}"
        idx += 1
    return target


def scan_and_rename(base: Path, recursive: bool, apply: bool, pattern: str, pages: int,
                    log: Callable[[str], None]) -> tuple[int, int]:
    rx = re.compile(pattern)
    pdfs = list(base.rglob("*.pdf") if recursive else base.glob("*.pdf"))
    if not pdfs:
        log("[INFO] No PDF files found.")
        return 0, 0

    log(f"[INFO] Scanning {len(pdfs)} PDF(s) in: {base}")
    renamed = 0
    skipped = 0

    for pdf in pdfs:
        match = find_match_in_pdf(pdf, rx, pages)
        if match:
            new_path = unique_target_path(pdf.parent, match, ".pdf")
            action = "RENAME " if apply else "DRYRUN "
            log(f"[{action}] {pdf.name}  ->  {new_path.name}")
            if apply:
                try:
                    pdf.rename(new_path)
                    renamed += 1
                except Exception as e:
                    log(f"[ERROR] Failed to rename {pdf.name}: {e}")
        else:
            log(f"[SKIP ] {pdf.name} (no match)")
            skipped += 1

    return renamed, skipped


# ---- CLI --------------------------------------------------------------------
def run_cli(args):
    if PdfReader is None:
        print("[ERROR] pypdf is not installed. Install it with: pip install pypdf", file=sys.stderr)
        sys.exit(1)

    base = Path(args.folder).expanduser().resolve()
    if not base.exists():
        print(f"[ERROR] Folder not found: {base}", file=sys.stderr)
        sys.exit(2)

    def log(s: str): print(s)

    renamed, skipped = scan_and_rename(
        base=base,
        recursive=args.recursive,
        apply=args.apply,
        pattern=args.pattern,
        pages=args.pages,
        log=log
    )

    if args.apply:
        print(f"[DONE ] Renamed: {renamed}, Skipped: {skipped}")
    else:
        print(f"[DONE ] Dry-run only. Use --apply to perform rename. Potential renames shown above.")


# ---- GUI --------------------------------------------------------------------
def run_gui(preset_folder: Optional[str] = None):
    if PdfReader is None:
        print("[ERROR] pypdf is not installed. Install it with: pip install pypdf", file=sys.stderr)
        sys.exit(1)

    try:
        import tkinter as tk  # type: ignore
        from tkinter import ttk, filedialog, messagebox  # type: ignore
    except Exception as e:
        print("[ERROR] Tkinter is not available in this Python environment.", file=sys.stderr)
        sys.exit(3)

    root = tk.Tk()
    root.title("PDF Rename by SPS ID")
    root.geometry("800x520")

    # --- Variables
    folder_var = tk.StringVar(value=preset_folder or str(Path(".").resolve()))
    pattern_var = tk.StringVar(value=r"\bSPS\d{2}-\d{4}\b")
    pages_var = tk.IntVar(value=5)
    recursive_var = tk.BooleanVar(value=False)
    mode_var = tk.StringVar(value="dry")  # 'dry' or 'apply'

    # --- Layout
    pad = {"padx": 8, "pady": 6}

    frm = ttk.Frame(root)
    frm.pack(fill="both", expand=True)

    # Folder row
    row0 = ttk.Frame(frm); row0.pack(fill="x", **pad)
    ttk.Label(row0, text="Folder:").pack(side="left")
    ent_folder = ttk.Entry(row0, textvariable=folder_var)
    ent_folder.pack(side="left", fill="x", expand=True, padx=6)
    def browse():
        d = filedialog.askdirectory(initialdir=folder_var.get() or None, title="Select the folder that contains PDFs")
        if d:
            folder_var.set(d)
    ttk.Button(row0, text="Browse…", command=browse).pack(side="left")

    # Options row
    row1 = ttk.Frame(frm); row1.pack(fill="x", **pad)
    ttk.Checkbutton(row1, text="Include subfolders (-r)", variable=recursive_var).pack(side="left")
    ttk.Label(row1, text="Pages to scan:").pack(side="left", padx=(16,4))
    spn_pages = ttk.Spinbox(row1, from_=1, to=50, textvariable=pages_var, width=5)
    spn_pages.pack(side="left")
    ttk.Label(row1, text="Pattern (regex):").pack(side="left", padx=(16,4))
    ent_pattern = ttk.Entry(row1, textvariable=pattern_var, width=28)
    ent_pattern.pack(side="left", fill="x")

    # Mode row (dry/apply)
    row2 = ttk.Frame(frm); row2.pack(fill="x", **pad)
    ttk.Label(row2, text="Mode:").pack(side="left")
    ttk.Radiobutton(row2, text="Dry-run (미리보기)", value="dry", variable=mode_var).pack(side="left", padx=6)
    ttk.Radiobutton(row2, text="Rename (실제 변경)", value="apply", variable=mode_var).pack(side="left", padx=6)

    # Run button
    row3 = ttk.Frame(frm); row3.pack(fill="x", **pad)
    run_btn = ttk.Button(row3, text="실행", width=14)
    run_btn.pack(side="right")

    # Log area
    row4 = ttk.Frame(frm); row4.pack(fill="both", expand=True, **pad)
    txt = tk.Text(row4, wrap="none", height=18)
    yscroll = ttk.Scrollbar(row4, orient="vertical", command=txt.yview)
    txt.configure(yscrollcommand=yscroll.set)
    txt.pack(side="left", fill="both", expand=True)
    yscroll.pack(side="left", fill="y")

    def log_line(s: str):
        txt.insert("end", s + "\n")
        txt.see("end")
        root.update_idletasks()

    def do_run():
        folder = folder_var.get().strip()
        base = Path(folder).expanduser().resolve()
        if not base.exists():
            messagebox.showerror("Folder not found", f"Folder not found:\n{base}")
            return
        # Validate regex
        try:
            re.compile(pattern_var.get())
        except re.error as e:
            messagebox.showerror("Regex error", f"Invalid regex:\n{e}")
            return

        # Disable Run during work
        run_btn.config(state="disabled")
        txt.delete("1.0", "end")
        log_line(f"[INFO] Start: folder={base}")
        log_line(f"[INFO] Mode={'RENAME' if mode_var.get() == 'apply' else 'DRYRUN'}  recursive={recursive_var.get()}  pages={pages_var.get()}")
        log_line(f"[INFO] Pattern={pattern_var.get()}")

        def worker():
            try:
                renamed, skipped = scan_and_rename(
                    base=base,
                    recursive=recursive_var.get(),
                    apply=(mode_var.get() == "apply"),
                    pattern=pattern_var.get(),
                    pages=int(pages_var.get() or 5),
                    log=log_line
                )
                if mode_var.get() == "apply":
                    log_line(f"[DONE ] Renamed: {renamed}, Skipped: {skipped}")
                else:
                    log_line(f"[DONE ] Dry-run only. Use Rename mode to perform rename.")
            finally:
                run_btn.config(state="normal")

        threading.Thread(target=worker, daemon=True).start()

    run_btn.config(command=do_run)

    root.mainloop()


# ---- Entry ------------------------------------------------------------------
def parse_args():
    ap = argparse.ArgumentParser(description="Rename PDFs to SPSxx-xxxx based on content text (GUI or CLI).")
    ap.add_argument("folder", nargs="?", help="Target folder (omit to open GUI).")
    ap.add_argument("-r", "--recursive", action="store_true", help="Recurse into subfolders")
    ap.add_argument("--apply", action="store_true", help="Actually rename files (default: dry-run)")
    ap.add_argument("--pattern", default=r"\bSPS\d{2}-\d{4}\b",
                    help=r"Regex to match the ID inside PDFs (default: \bSPS\d{2}-\d{4}\b)")
    ap.add_argument("--pages", type=int, default=5,
                    help="Max pages to scan per PDF (default: 5)")
    ap.add_argument("--ui", action="store_true", help="Force open GUI")
    ap.add_argument("--nogui", action="store_true", help="Force CLI even if no args")
    return ap.parse_args()


def main():
    args = parse_args()

    # Decide UI vs CLI
    if args.ui or (not args.nogui and args.folder is None):
        preset = None if args.folder is None else args.folder
        run_gui(preset_folder=preset)
    else:
        # CLI path requires folder
        if not args.folder:
            print("[ERROR] Please provide a folder path or run with --ui for the GUI.", file=sys.stderr)
            sys.exit(2)
        run_cli(args)


if __name__ == "__main__":
    main()
