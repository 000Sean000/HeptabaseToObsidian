# src/build_uid_map_for_truncated_titles.py

import os
import re
import json
import unicodedata
from datetime import datetime


def build_uid_map_for_truncated_titles(vault_path, map_path, log_path, verbose=False):
    truncation_map = {}
    uid_index = 1
    log_lines = []

    # 嘗試讀取舊的 map 並設定 uid_index 起點
    try:
        if os.path.exists(map_path):
            with open(map_path, "r", encoding="utf-8") as f:
                truncation_map = json.load(f)
            used_uids = [int(v["uid"].split("_")[1]) for v in truncation_map.values()]
            uid_index = max(used_uids) + 1 if used_uids else 1
    except Exception as e:
        log_lines.append(f"⚠️ 無法讀取舊 map，將重新從 uid_001 開始。錯誤：{e}")
        truncation_map = {}
        uid_index = 1

    total_files = 0
    truncated_count = 0
    already_processed_count = 0
    non_truncated_count = 0

    def log(msg):
        log_lines.append(msg)
        if verbose:
            print(msg)

    def is_valid_char(c):
        return c.isalnum() or c in " -_()[]"

    def skip_yaml(lines):
        if lines and lines[0].strip() == "---":
            for i in range(1, len(lines)):
                if lines[i].strip() == "---":
                    return lines[i + 1 :]
        return lines

    def clean_markdown_line(line):
        line = line.lstrip()
        line = re.sub(r"^[-+*]\s+", "", line)
        line = re.sub(r"^\d+[\\.]?\s*", "", line)
        line = re.sub(r"^#+\s*", "", line)
        line = re.sub(r"^>+\s*", "", line)
        line = re.sub(r"\*\*(.*?)\*\*", r"\1", line)
        line = re.sub(r"(?<!\*)\*(?!\*)(.*?)\*(?!\*)", r"\1", line)
        line = re.sub(r"`(.*?)`", r"\1", line)
        line = re.sub(r"\[\[([^\|\]]+)(\|.*?)?\]\]", lambda m: re.sub(r"\s+\d+$", "", m.group(1)), line)
        return line.strip()

    def remove_trailing_number(text):
        return re.sub(r"\s*\d+$", "", text.strip())

    def compare_filename_and_line(filename, line):
        fn = remove_trailing_number(filename)
        i, j = 0, 0
        while i < len(fn) and j < len(line):
            c1, c2 = fn[i], line[j]
            if c1 == c2:
                i += 1
                j += 1
            elif not is_valid_char(c1) or not is_valid_char(c2):
                i += 1
                j += 1
            else:
                return False, f"❌ 字元不符：'{c1}' ≠ '{c2}' 位置 {i}"
        if i < len(fn):
            return False, f"❌ 檔名未完全匹配：僅比對至 {i}/{len(fn)}"
        remaining = line[j:].strip()
        if remaining == "" or re.fullmatch(r"\d+", remaining):
            return False, "❌ 剩餘內容僅為數字或空白"
        return True, "✔️ 首句包含額外語意，構成語意斷句"

    for root, _, files in os.walk(vault_path):
        for file in files:
            if not file.endswith(".md"):
                continue
            total_files += 1
            base_filename = file[:-3]
            if base_filename in truncation_map:
                already_processed_count += 1
                continue

            full_path = os.path.join(root, file)
            with open(full_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            lines = skip_yaml(lines)
            content_line = ""
            for line in lines:
                if line.strip():
                    content_line = line.strip()
                    break
            cleaned = clean_markdown_line(content_line)
            match, reason = compare_filename_and_line(base_filename, cleaned)

            log(f"{'✔️' if match else '❌'} {file}")
            log(f"  ↪ 檔名: {base_filename}")
            log(f"  ↪ 首句: {cleaned}")
            log(f"  ↪ 理由: {reason}")
            log("")

            if match:
                uid = f"uid_{uid_index:03d}"
                uid_index += 1
                new_path = os.path.join(root, uid + ".md")
                os.rename(full_path, new_path)
                truncation_map[base_filename] = {
                    "uid": uid,
                    "full_sentence": cleaned
                }
                truncated_count += 1
                log(f"🔁 已重新命名: {file} → {uid}.md\n")
            else:
                non_truncated_count += 1

    log("\n")
    log("📊 統計摘要\n")
    log(f"✔️ 新增 UID：{truncated_count} 筆\n")
    log(f"🔁 已處理過：{already_processed_count} 筆\n")
    log(f"🚫 不構成斷句：{non_truncated_count} 筆\n")
    log(f"📁 掃描筆記總數：{total_files} 筆\n")

    os.makedirs(os.path.dirname(map_path), exist_ok=True)
    with open(map_path, "w", encoding="utf-8") as f:
        json.dump(truncation_map, f, indent=2, ensure_ascii=False)

    with open(log_path, "w", encoding="utf-8") as f:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        f.write(f"📄 Truncation Detection Log — {timestamp}\n\n")
        f.write("\n".join(log_lines))

    return truncation_map, log_lines


if __name__ == "__main__":
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    VAULT_DIR = os.path.join(BASE_DIR, "TestData")
    MAP_PATH = os.path.join(BASE_DIR, "log", "truncation_map.json")
    LOG_PATH = os.path.join(BASE_DIR, "log", "truncation_detect.log")

    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    build_uid_map_for_truncated_titles(VAULT_DIR, MAP_PATH, LOG_PATH, verbose=True)
