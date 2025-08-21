# src/utils/get_safe_path.py

import os

def get_safe_path(path: str) -> str:
    r"""針對 Windows 自動加上長路徑前綴，避免超過 MAX_PATH 錯誤。
    - 自動修復：若傳入已含一個或多個 `\\?\` 前綴，會全部剝除後再加回「恰好一個」。
    - 支援 UNC：\\server\share\path → \\?\UNC\server\share\path
    - 邊界保護：空字串、根號 "\\"、或只含前綴等異常輸入，都回退到絕對路徑再加前綴。
    """
    if os.name != "nt":
        return path

    if path is None:
        return ""

    s = str(path).replace("/", "\\").strip()

    # 剝除所有重複的 extended 前綴：處理如 "\\?\ \\?\C:\..."、"\\?\UNC\server\share\..."
    while s.upper().startswith("\\\\?\\"):
        if s.upper().startswith("\\\\?\\UNC\\"):
            # \\?\UNC\server\share\... → 還原一般 UNC：\\server\share\...
            s = "\\" + "\\" + s[8:]  # len("\\\\?\\UNC\\") == 8
        else:
            # \\?\C:\... → 去前綴成 C:\...
            s = s[4:]  # len("\\\\?\\") == 4

    # 邊界：若剝到只剩空、或只有 "\\"，回退到目前工作目錄
    if not s or s == "\\":
        s = os.getcwd()

    # 轉成絕對路徑（不帶 extended 前綴）
    s_abs = os.path.abspath(s)

    # 統一重新加上「恰好一個」 extended 前綴
    if s_abs.startswith("\\\\"):  # UNC：\\server\share\path
        return "\\\\?\\UNC\\" + s_abs.lstrip("\\")
    else:
        return "\\\\?\\" + s_abs
