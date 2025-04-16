# detect_invalid_md_filenames.py
import os
import unicodedata
from datetime import datetime

def detect_invalid_md_filenames(vault_path, output_log="invalid_filenames.log", verbose=False):
    """
    掃描指定 Vault 目錄下的所有 .md 檔案，找出尾端包含非法字元的檔案。
    非法字元包括空白、句號、控制碼（如 \u200B, \u00A0, \u3000）。

    Args:
        vault_path (str): Vault 根目錄
        output_log (str): 輸出 log 檔名
        verbose (bool): 是否印出至 terminal（預設為 False）

    Returns:
        List[dict]: 每筆結果為 {
            "filename": 檔名,
            "trailing": 非法尾端字串,
            "trailing_unicode": unicode 顯示字串,
            "path": 完整路徑
        }
    """
    results = []

    def is_invalid_tail_char(char):
        return char in {" ", ".", "\u200B", "\u00A0", "\u3000"} or unicodedata.category(char).startswith("C")

    for root, _, files in os.walk(vault_path):
        for file in files:
            if file.endswith(".md"):
                base_name = file[:-3]  # 去掉 .md
                trailing = ""
                i = len(base_name) - 1
                while i >= 0 and is_invalid_tail_char(base_name[i]):
                    trailing = base_name[i] + trailing
                    i -= 1

                if trailing:
                    results.append({
                        "filename": file,
                        "trailing": trailing,
                        "trailing_unicode": "".join(f"\\u{ord(c):04x}" for c in trailing),
                        "path": os.path.join(root, file)
                    })

    # 寫入 log 檔案
    with open(os.path.join(vault_path, output_log), "w", encoding="utf-8") as f:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        f.write(f"🕵️ Invalid filename trailing report @ {timestamp}\n\n")
        if not results:
            f.write("✅ 所有 .md 檔案尾端都乾淨。\n")
        else:
            for item in results:
                f.write(f"- {item['filename']} → '{item['trailing']}' [{item['trailing_unicode']}]\n")
                f.write(f"  ↳ {item['path']}\n\n")

    if verbose:
        print(f"🔍 結果已寫入：{output_log}")
        if not results:
            print("✅ 所有 .md 檔案尾端都乾淨。")
        else:
            print(f"🧨 共發現 {len(results)} 筆非法尾端檔名，詳見 {output_log}")

    return results
if __name__ == "__main__":
    vault = os.getcwd()
    detect_invalid_md_filenames(vault, verbose=True)
