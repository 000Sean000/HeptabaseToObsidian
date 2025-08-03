# src/standardize_md_indentation.py

import os
import json
from datetime import datetime
from utils.get_safe_path import get_safe_path  # ✅ 加入此行


def get_leading_spaces(line: str) -> int:
    return len(line) - len(line.lstrip(' '))


def standardize_md_indentation(
    vault_path,
    log_path=None,
    verbose=False,
    spaces_per_indent=4,
    indent_unit_map_path=None,
    fallback_unit=4,
):
    changed_files = []

    # 讀入縮排單位 map
    indent_unit_map = {}
    if indent_unit_map_path and os.path.exists(indent_unit_map_path):
        with open(get_safe_path(indent_unit_map_path), "r", encoding="utf-8") as f:
            indent_unit_map = json.load(f)

    def log(msg):
        if log_path:
            safe_log_path = get_safe_path(log_path)
            os.makedirs(os.path.dirname(safe_log_path), exist_ok=True)
            with open(safe_log_path, "a", encoding="utf-8") as f:
                f.write(msg + "\n")
        if verbose:
            print(msg)

    if log_path:
        with open(get_safe_path(log_path), "w", encoding="utf-8") as f:
            f.write(f"🧹 Indentation Fix Log — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

    for root, _, files in os.walk(vault_path):
        for file in files:
            if not file.endswith(".md"):
                continue

            file_path = os.path.join(root, file)
            safe_file_path = get_safe_path(file_path)
            rel_path = os.path.relpath(file_path, vault_path)

            indent_unit = indent_unit_map.get(rel_path, fallback_unit)

            with open(safe_file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            new_lines = []
            changed = False

            for line in lines:
                raw_line = line
                space_indent = get_leading_spaces(line)
                indent_level = space_indent // indent_unit
                stripped = line.lstrip().rstrip('\n')
                if stripped.endswith('\\'):
                    stripped = stripped[:-1].rstrip()
                rebuilt_line = ' ' * (spaces_per_indent * indent_level) + stripped + '\n'

                if rebuilt_line != raw_line:
                    changed = True
                new_lines.append(rebuilt_line)

            if changed:
                with open(safe_file_path, "w", encoding="utf-8") as f:
                    f.writelines(new_lines)
                changed_files.append(rel_path)
                log(f"✅ {rel_path}：已統一縮排（依空格單位={indent_unit} 推算層級 → 每層轉為 {spaces_per_indent} space）")
            else:
                log(f"☑️ {rel_path}：縮排正常（依空格單位={indent_unit} 推算層級 → 每層為 {spaces_per_indent} space）")

    if changed_files:
        log(f"\n🎉 共修正 {len(changed_files)} 個檔案的縮排")
    else:
        log("✅ 所有檔案縮排皆已一致")

    return changed_files


# === 🧪 單獨執行測試區 ===
if __name__ == "__main__":
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    VAULT_PATH = os.path.join(BASE_DIR, "TestData")
    LOG_PATH = os.path.join(BASE_DIR, "log", "indent_fix.log")
    MAP_PATH = os.path.join(BASE_DIR, "log", "indent_unit_map.json")

    standardize_md_indentation(
        vault_path=VAULT_PATH,
        log_path=LOG_PATH,
        verbose=True,
        indent_unit_map_path=MAP_PATH,
        fallback_unit=4
    )
