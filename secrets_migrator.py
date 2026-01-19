# secrets_migrator.py
import os, re, sys, json, shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ENV = ROOT / ".env"
BACKUP = ROOT / ".env.bak"

PATTERNS = {
    # Slack
    "SLACK_TOKEN": r"(xox[baprs]-[0-9A-Za-z\-]{10,})",
    "SLACK_CHANNEL_DEFAULT": r"\b(C[A-Z0-9]{8,})\b",
    # Google OAuth
    "GOOGLE_OAUTH_CLIENT_ID": r"[0-9\-]+-[0-9a-z]+\.apps\.googleusercontent\.com",
    "GOOGLE_OAUTH_CLIENT_SECRET": r"(?:GOCSPX-[0-9A-Za-z\-_]{20,}|[0-9A-Za-z\-_]{24,})",
    # Calendar
    "GCAL_ABSENCE_CALENDAR_ID": r"[\w\.\-]+@group\.calendar\.google\.com|\bprimary\b",
    # Sheets
    "GOOGLE_SHEETS_NICKNAME_SPREADSHEET_ID": r"[A-Za-z0-9\-_]{30,}",
    # OpenAI/Gemini
    "OPENAI_API_KEY": r"(sk-[A-Za-z0-9]{20,})",
    "GENAI_API_KEY": r"(AIza[0-9A-Za-z\-_]{30,})",
    # Tesseract (경로 추정)
    "TESSERACT_CMD": r"(?:[A-Za-z]:\\[^\"']*?tesseract\.exe)|(?:/usr/bin/tesseract|/opt/homebrew/bin/tesseract)",
    # WEHAGO (이메일/ID 형태 추정)
    "WEHAGO_ID": r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}",
}

IGNORE_DIRS = {"X_","venv",".venv1",".idea", ".venv", "__pycache__", ".git", "node_modules"}

def read_text(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""

def scan():
    found = {}
    for p in ROOT.rglob("*.py"):


            if any(part in IGNORE_DIRS for part in p.parts):
                continue
            text = read_text(p)
            for key, pat in PATTERNS.items():
                for m in re.findall(pat, text):
                    if key not in found:
                        found[key] = str(m)
                        print(p,"_______",found)
    return found

def parse_env(path: Path):
    vals = {}
    if not path.exists(): return vals
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip() or line.strip().startswith("#"): continue
        if "=" in line:
            k, v = line.split("=", 1)
            vals[k.strip()] = v.strip()
    return vals

def mask(v: str, left=6, right=4):
    if not v: return ""
    if len(v) <= left+right: return "*"*len(v)
    return v[:left] + "*"*(len(v)-left-right) + v[-right:]

def main():
    print("[*] 코드에서 비밀값 후보 스캔 중...")
    found = scan()
    if not found:
        print("  - 후보가 보이지 않습니다. (하드코딩이 없거나 패턴 밖)")
    else:
        for k, v in found.items():
            print(f"  - {k}: {mask(v)}")

    existing = parse_env(ENV)
    if ENV.exists():
        shutil.copy2(ENV, BACKUP)
        print(f"[*] 기존 .env 백업 완료 → {BACKUP.name}")

    merged = existing.copy()
    merged.setdefault("TIMEZONE", "Asia/Seoul")
    merged.setdefault("LOG_LEVEL", "INFO")

    # 병합: 기존 값 우선, 없으면 자동 추출값
    for k, v in found.items():
        merged.setdefault(k, v)

    # 필수 키(없으면 빈 값으로 추가)
    for k in [
        "SLACK_TOKEN","SLACK_CHANNEL_DEFAULT","SLACK_CHANNEL_NEWS","SLACK_CHANNEL_PUBMED",
        "SLACK_CHANNEL_ABSENCE","SLACK_CHANNEL_HEARTBEAT",
        "GOOGLE_OAUTH_CLIENT_ID","GOOGLE_OAUTH_CLIENT_SECRET","GCAL_ABSENCE_CALENDAR_ID",
        "GOOGLE_SHEETS_NICKNAME_SPREADSHEET_ID","GOOGLE_SHEETS_NICKNAME_RANGE",
        "GOOGLE_CREDENTIALS","GOOGLE_TOKEN_PATH",
        "WEHAGO_ID","WEHAGO_PW","WEHAGO_MONTHS","WEHAGO_DOWNLOAD_DIR",
        "OPENAI_API_KEY","OPENAI_DEFAULT_MODEL","GENAI_API_KEY",
        "TESSERACT_CMD","TESSDATA_PREFIX",
    ]:
        merged.setdefault(k, "")

    # 기본값
    if not merged.get("GOOGLE_TOKEN_PATH"):
        merged["GOOGLE_TOKEN_PATH"] = "token.json"
    if not merged.get("GOOGLE_SHEETS_NICKNAME_RANGE"):
        merged["GOOGLE_SHEETS_NICKNAME_RANGE"] = "'직원 정보'!A:Z"
    if not merged.get("OPENAI_DEFAULT_MODEL"):
        merged["OPENAI_DEFAULT_MODEL"] = "o4-mini"
    if not merged.get("WEHAGO_MONTHS"):
        merged["WEHAGO_MONTHS"] = "6"

    # 쓰기
    lines = []
    def add(section, keys):
        lines.append(f"# ===== {section} =====")
        for k in keys:
            lines.append(f"{k}={merged.get(k,'')}")
        lines.append("")
    add("공통", ["TIMEZONE","LOG_LEVEL"])
    add("Slack", ["SLACK_TOKEN","SLACK_CHANNEL_DEFAULT","SLACK_CHANNEL_NEWS","SLACK_CHANNEL_PUBMED","SLACK_CHANNEL_ABSENCE","SLACK_CHANNEL_HEARTBEAT"])
    add("Google OAuth / Calendar / Sheets", ["GOOGLE_OAUTH_CLIENT_ID","GOOGLE_OAUTH_CLIENT_SECRET","GOOGLE_TOKEN_PATH","GCAL_ABSENCE_CALENDAR_ID","GOOGLE_SHEETS_NICKNAME_SPREADSHEET_ID","GOOGLE_SHEETS_NICKNAME_RANGE","GOOGLE_CREDENTIALS"])
    add("WEHAGO", ["WEHAGO_ID","WEHAGO_PW","WEHAGO_MONTHS","WEHAGO_DOWNLOAD_DIR"])
    add("OpenAI / Gemini", ["OPENAI_API_KEY","OPENAI_DEFAULT_MODEL","GENAI_API_KEY"])
    add("OCR / Tesseract", ["TESSERACT_CMD","TESSDATA_PREFIX"])

    ENV.write_text("\n".join(lines), encoding="utf-8")
    print(f"[*] .env 작성 완료: {ENV}")

if __name__ == "__main__":
    main()
