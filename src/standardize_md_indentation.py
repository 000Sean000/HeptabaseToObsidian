# src/standardize_md_indentation.py

import os
from datetime import datetime

def get_visual_indent(line, tab_size=3):
    """模擬方向鍵移動的視覺縮排量"""
    visual_pos = 0
    for char in line:
        if char == ' ':
            visual_pos += 1
        elif char == '\t':
            visual_pos += tab_size - (visual_pos % tab_size)
        else:
            break
    return visual_pos

def standardize_md_indentation(vault_path, log_path=None, verbose=False, spaces_per_indent=4, tab_size=3, indent_unit=3):
    changed_files = []

    def log(msg):
        if log_path:
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(msg + "\n")
        if verbose:
            print(msg)

    if log_path:
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(f"🧹 Indentation Fix Log — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

    for root, _, files in os.walk(vault_path):
        for file in files:
            if not file.endswith(".md"):
                continue

            file_path = os.path.join(root, file)
            rel_path = os.path.relpath(file_path, vault_path)

            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            new_lines = []
            changed = False

            for line in lines:
                raw_line = line
                visual_indent = get_visual_indent(line, tab_size=tab_size)
                indent_level = visual_indent // indent_unit
                stripped = line.lstrip()
                rebuilt_line = ' ' * (spaces_per_indent * indent_level) + stripped

                if rebuilt_line != raw_line:
                    changed = True
                new_lines.append(rebuilt_line)

            if changed:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.writelines(new_lines)
                changed_files.append(rel_path)
                log(f"✅ {rel_path}：已統一縮排")
            else:
                log(f"☑️ {rel_path}：縮排正常")

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

    standardize_md_indentation(
        vault_path=VAULT_PATH,
        log_path=LOG_PATH,
        verbose=True
    )
