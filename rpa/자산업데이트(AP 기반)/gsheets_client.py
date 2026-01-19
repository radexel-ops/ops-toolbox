
# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from typing import Any, Dict, List, Tuple, Optional

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# ---- Project config ----
from config import (
    SCOPES,
    GOOGLE_CLIENT_ID,
    GOOGLE_CLIENT_SECRET,
    GOOGLE_CLIENT_SECRETS_FILE,
)

TOKEN_PATH = "token.json"


def col_letter(idx_zero_based: int) -> str:
    """0-based column index -> Excel/Sheets column letter (A, B, ..., AA, AB, ...)"""
    n = idx_zero_based + 1
    s = ""
    while n > 0:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def A1(sheet_name: str, range_a1: str) -> str:
    """Return "'Sheet Name'!A1:B2" string."""
    sheet_name = str(sheet_name or "").replace("'", "''")
    return f"'{sheet_name}'!{range_a1}"


def _load_credentials_from_token() -> Optional[Credentials]:
    if os.path.exists(TOKEN_PATH):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
            if creds and creds.valid:
                return creds
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
                return creds
        except Exception:
            pass
    return None


def _run_oauth_flow() -> Credentials:
    # Prefer client_secret.json file if provided
    if GOOGLE_CLIENT_SECRETS_FILE:
        flow = InstalledAppFlow.from_client_secrets_file(GOOGLE_CLIENT_SECRETS_FILE, SCOPES)
    else:
        if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
            raise RuntimeError(
                "GOOGLE_CLIENT_ID/GOOGLE_CLIENT_SECRET가 비어 있습니다. "
                "환경변수 또는 config.json에 값을 채우세요."
            )
        client_config = {
            "installed": {
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": ["http://localhost"]
            }
        }
        flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    creds = flow.run_local_server(port=0, prompt='consent')
    with open(TOKEN_PATH, "w", encoding="utf-8") as f:
        f.write(creds.to_json())
    return creds


def get_credentials(reset: bool=False) -> Credentials:
    if reset and os.path.exists(TOKEN_PATH):
        try:
            os.remove(TOKEN_PATH)
        except Exception:
            pass
    creds = _load_credentials_from_token()
    if creds:
        return creds
    return _run_oauth_flow()


class SheetsClient:
    def __init__(self):
        self.service = None

    # ────────────────────────── Connect ──────────────────────────
    def connect(self):
        creds = get_credentials(False)
        self.service = build("sheets", "v4", credentials=creds)

    # ────────────────────────── Values ──────────────────────────
    def values_get(self, spreadsheet_id: str, range_a1: str, value_render_option: str="UNFORMATTED_VALUE") -> List[List[Any]]:
        """Get values from a range. Returns [] if not found."""
        try:
            rsp = self.service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=range_a1,
                valueRenderOption=value_render_option
            ).execute()
            return rsp.get("values", []) or []
        except HttpError as e:
            if e.resp.status == 404:
                return []
            raise

    def values_batch_update_columns(self, spreadsheet_id: str, data: List[Dict[str, Any]]):
        """Batch update multiple columns (list of {range, values})."""
        body = {
            "valueInputOption": "RAW",
            "data": data,
        }
        self.service.spreadsheets().values().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body=body
        ).execute()

    # ────────────────────────── Sheet meta ──────────────────────────
    def _get_sheet_meta(self, spreadsheet_id: str, sheet_name: str) -> Tuple[int, Dict[str, Any]]:
        """Return (sheet_id, gridProperties)."""
        meta = self.service.spreadsheets().get(
            spreadsheetId=spreadsheet_id,
            fields="sheets(properties(sheetId,title,gridProperties(rowCount,columnCount)))"
        ).execute()
        for s in meta.get("sheets", []):
            props = s.get("properties", {})
            if (props.get("title") or "") == sheet_name:
                return int(props["sheetId"]), props.get("gridProperties", {})
        raise ValueError(f"시트 '{sheet_name}'을(를) 찾을 수 없습니다.")

    # ────────────────────────── Insert Rows + Copy Template ──────────────────────────
    def insert_rows_copy_template(
        self,
        spreadsheet_id: str,
        sheet_name: str,
        insert_count: int,
        total_cols: int,
        template_row_1based: int
    ) -> Tuple[int, int]:
        """
        Append rows to the bottom of the sheet and copy format & formulas from template row.
        Returns (start_row_1based, end_row_1based) of the inserted block.
        """
        if insert_count <= 0:
            raise ValueError("insert_count must be > 0")

        sheet_id, grid = self._get_sheet_meta(spreadsheet_id, sheet_name)
        row_count = int(grid.get("rowCount", 0))

        # New rows will start at the current row_count (0-based index); 1-based is row_count+1.
        start_index = row_count
        end_index = row_count + insert_count

        # Build requests
        requests: List[Dict[str, Any]] = []

        # 1) Insert rows at the end — inheritFromBefore MUST be True when inserting at grid end.
        requests.append({
            "insertDimension": {
                "range": {
                    "sheetId": sheet_id,
                    "dimension": "ROWS",
                    "startIndex": start_index,
                    "endIndex": end_index
                },
                "inheritFromBefore": True
            }
        })

        # 2) Copy FORMAT then FORMULAS from the template row to the inserted block
        # Source row (1-based -> 0-based)
        src_row0 = int(template_row_1based) - 1
        requests.append({
            "copyPaste": {
                "source": {
                    "sheetId": sheet_id,
                    "startRowIndex": src_row0,
                    "endRowIndex": src_row0 + 1,
                    "startColumnIndex": 0,
                    "endColumnIndex": total_cols
                },
                "destination": {
                    "sheetId": sheet_id,
                    "startRowIndex": start_index,
                    "endRowIndex": end_index,
                    "startColumnIndex": 0,
                    "endColumnIndex": total_cols
                },
                "pasteType": "PASTE_FORMAT",
                "pasteOrientation": "NORMAL"
            }
        })
        requests.append({
            "copyPaste": {
                "source": {
                    "sheetId": sheet_id,
                    "startRowIndex": src_row0,
                    "endRowIndex": src_row0 + 1,
                    "startColumnIndex": 0,
                    "endColumnIndex": total_cols
                },
                "destination": {
                    "sheetId": sheet_id,
                    "startRowIndex": start_index,
                    "endRowIndex": end_index,
                    "startColumnIndex": 0,
                    "endColumnIndex": total_cols
                },
                "pasteType": "PASTE_FORMULA",
                "pasteOrientation": "NORMAL"
            }
        })

        body = {"requests": requests}
        self.service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body=body
        ).execute()

        start_1based = start_index + 1
        end_1based = end_index
        return start_1based, end_1based
