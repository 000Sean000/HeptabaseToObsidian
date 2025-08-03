# src/rewrite_links_with_uid_alias.py

import os
import re
import json
from datetime import datetime
from utils import get_safe_path  # ✅ 加入安全路徑處理


def rewrite_links_with_uid_alias(
    vault_path,
    truncation_map_path,
    log_path,
    mark_symbol="@",
    verbose=False
):
    truncation_map_path = get_safe_path(truncation_map_path)
    log_path = get_safe_path(log_path)

    with open(truncation_map_path, "r", encoding="utf-8") as f:
        truncation_map = json.load(f)

    wiki_link_pattern = re.compile(r"(?<!\!)\[\[([^\[\]\|\n]+?)\]\]")  # 排除 embed 與 alias
    modified_file_count = 0
    total_replacements = 0
    log_lines = []

    def log(msg):
        log_lines.append(msg)
        if verbose:
            print(msg)

    for root, _, files in os.walk(vault_path):
        for file in files:
            if not file.endswith(".md"):
                continue

            file_path = os.path.join(root, file)
            safe_file_path = get_safe_path(file_path)
            rel_path = os.path.relpath(file_path, vault_path)

            with open(safe_file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            modified = False
            new_lines = []
            file_log = []

            for line_num, line in enumerate(lines):
                replacements = []

                def replace_link(match):
                    target = match.group(1)
                    if "|" in target or target not in truncation_map:
                        return match.group(0)
                    uid = truncation_map[target]["uid"]
                    full = truncation_map[target]["full_sentence"]
                    alias = f"{mark_symbol}{full}"
                    replacements.append((target, uid, alias))
                    return f"[[{uid}|{alias}]]"

                new_line = wiki_link_pattern.sub(replace_link, line)

                if replacements:
                    modified = True
                    for orig, uid, alias in replacements:
                        file_log.append(f"  🔁 第 {line_num + 1} 行：[[{orig}]] → [[{uid}|{alias}]]")

                new_lines.append(new_line)

            if modified:
                with open(safe_file_path, "w", encoding="utf-8") as f:
                    f.writelines(new_lines)
                modified_file_count += 1
                total_replacements += len(file_log)
                log(f"📄 修改檔案：{rel_path}")
                log("\n".join(file_log))
                log("")

    log("\n")
    log("📊 統計摘要\n")
    log(f"📝 被修改檔案數：{modified_file_count} 筆\n")
    log(f"🔁 替換 wiki link 數：{total_replacements} 筆\n")

    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    with open(log_path, "w", encoding="utf-8") as f:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        f.write(f"🔗 UID Link Rewrite Log — {timestamp}\n\n")
        f.write("\n".join(log_lines))

    return modified_file_count, total_replacements


# === 測試入口 ===
if __name__ == "__main__":
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    VAULT_PATH = os.path.join(BASE_DIR, "TestData")
    MAP_PATH = os.path.join(BASE_DIR, "log", "truncation_map.json")
    LOG_PATH = os.path.join(BASE_DIR, "log", "uid_link_rewrite.log")

    rewrite_links_with_uid_alias(
        VAULT_PATH,
        MAP_PATH,
        LOG_PATH,
        mark_symbol="@",
        verbose=True
    )

