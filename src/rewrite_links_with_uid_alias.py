# src/rewrite_links_with_uid_alias.py

import os
import re
import json
from datetime import datetime
from utils.get_safe_path import get_safe_path


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

    # 快速查表：alias_text → uid
    alias_to_uid = {
        v["full_sentence"]: v["uid"]
        for v in truncation_map.values()
    }

    # [[title]] 但不是 embed（!）或 alias（|）
    wiki_link_pattern = re.compile(r"(?<!\!)\[\[([^\[\]\|\n]+?)\]\]")

    # [[uid_xxx|@Some sentence]]
    alias_link_pattern = re.compile(r"\[\[(uid_\d+)\|\@([^\]]+)\]\]")

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

                # 處理非 alias 的 [[title]] → [[uid|@full_sentence]]
                def replace_link(match):
                    target = match.group(1)
                    if "|" in target or target not in truncation_map:
                        return match.group(0)
                    uid = truncation_map[target]["uid"]
                    full = truncation_map[target]["full_sentence"]
                    alias = f"{mark_symbol}{full}"
                    replacements.append((target, uid, alias))
                    return f"[[{uid}|{alias}]]"

                # 處理 alias 錯誤指向的 [[uid_123|@Sentence]] → [[uid_456|@Sentence]]
                def correct_alias_uid(match):
                    current_uid, alias_text = match.group(1), match.group(2)
                    correct_uid = alias_to_uid.get(alias_text)
                    if correct_uid and correct_uid != current_uid:
                        replacements.append((current_uid, correct_uid, alias_text))
                        return f"[[{correct_uid}|@{alias_text}]]"
                    return match.group(0)

                # 執行替換
                new_line = wiki_link_pattern.sub(replace_link, line)
                new_line = alias_link_pattern.sub(correct_alias_uid, new_line)

                if replacements:
                    modified = True
                    for orig, uid, alias in replacements:
                        file_log.append(
                            f"  🔁 第 {line_num + 1} 行：[[{orig}]] → [[{uid}|@{alias}]]"
                        )

                new_lines.append(new_line)

            if modified:
                with open(safe_file_path, "w", encoding="utf-8") as f:
                    f.writelines(new_lines)
                modified_file_count += 1
                total_replacements += len(file_log)
                log(f"📄 修改檔案：{rel_path}")
                log("\n".join(file_log))
                log("")

    # 日誌結尾與總結
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
