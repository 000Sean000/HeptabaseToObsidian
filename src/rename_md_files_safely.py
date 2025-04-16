import os
import json
import unicodedata
from datetime import datetime

def rename_md_files_safely(
    vault_path,
    output_map="rename_map.json",
    log_file="rename_phase.log",
    invalid_char_check=None,
    verbose=False
):
    """
    將尾端含非法字元的 .md 檔案重新命名為合法結尾，並輸出對照表與 log。

    Args:
        vault_path (str): Vault 根目錄
        output_map (str): 輸出對照表 JSON 檔名
        log_file (str): 輸出 log 檔名
        invalid_char_check (callable): 自定尾端非法字元檢查函式（預設支援空白、句點、控制字元）
        verbose (bool): 是否印出至終端機

    Returns:
        Tuple[dict, str]: (rename_map, log_path)
    """
    rename_map = {}
    log_path = os.path.join(vault_path, log_file)
    map_path = os.path.join(vault_path, output_map)

    def log(msg):
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(msg + "\n")
        if verbose:
            print(msg)

    def is_invalid_tail_char(char):
        return char in {" ", ".", "\u200B", "\u00A0", "\u3000"} or unicodedata.category(char).startswith("C")

    checker = invalid_char_check if invalid_char_check else is_invalid_tail_char

    def clean_tail(name):
        i = len(name) - 1
        while i >= 0 and checker(name[i]):
            i -= 1
        return name[:i+1]

    def resolve_conflict(dir_path, base_name, ext):
        candidate = base_name + ext
        count = 1
        while os.path.exists(os.path.join(dir_path, candidate)):
            candidate = f"{base_name} ({count}){ext}"
            count += 1
        return candidate

    # Reset log at start
    with open(log_path, "w", encoding="utf-8") as f:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        f.write(f"📁 Rename Phase Log — {timestamp}\n\n")

    log("🔍 開始掃描並重新命名含非法尾端字元的 .md 檔案...\n")

    for root, _, files in os.walk(vault_path):
        for file in files:
            if file.endswith(".md"):
                full_path = os.path.join(root, file)
                relative_path = os.path.relpath(full_path, vault_path)

                base_name = file[:-3]
                clean_base = clean_tail(base_name)

                if clean_base != base_name:
                    ext = ".md"
                    safe_name = resolve_conflict(root, clean_base, ext)
                    new_path = os.path.join(root, safe_name)
                    os.rename(full_path, new_path)
                    new_rel = os.path.relpath(new_path, vault_path)
                    rename_map[relative_path] = new_rel
                    log(f"🔁 重新命名: {relative_path} → {new_rel}")

    if rename_map:
        with open(map_path, "w", encoding="utf-8") as f:
            json.dump(rename_map, f, indent=2, ensure_ascii=False)
        log(f"\n✅ 已重新命名 {len(rename_map)} 個檔案，對照表儲存為 {output_map}")
    else:
        log("✅ 沒有需要重新命名的檔案。所有檔名尾端皆為合法字元。")

    log(f"\n📄 Log 儲存於 {log_file}")
    return rename_map, log_path

if __name__ == "__main__":
    vault = os.getcwd()
    rename_map, log_path = rename_md_files_safely(vault, verbose=True)
