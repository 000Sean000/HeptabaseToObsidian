import os
import re
import json
from datetime import datetime
from utils import get_safe_path



def build_uid_map_for_truncated_titles(vault_path, map_path, log_path, verbose=False):
    truncation_map = {}
    full_to_uid = {}
    uid_to_expected_full = {}
    uid_index = 1
    log_lines = []

    def log(msg):
        log_lines.append(msg)
        if verbose:
            print(msg)

    # Load existing map if available
    try:
        if os.path.exists(map_path):
            with open(map_path, "r", encoding="utf-8") as f:
                truncation_map = json.load(f)
                for k, v in truncation_map.items():
                    full = v["full_sentence"]
                    uid = v["uid"]
                    full_to_uid[full] = uid
                    uid_to_expected_full[uid] = full
                used_uids = [int(v["uid"].split("_")[1]) for v in truncation_map.values()]
                uid_index = max(used_uids) + 1 if used_uids else 1
    except Exception as e:
        log(f"⚠️ 無法讀取舊 map，將重新從 uid_001 開始。錯誤：{e}")
        truncation_map = {}
        uid_index = 1

    def is_valid_char(c):
        return c.isalnum() or c in " -_()[]"

    def skip_yaml(lines):
        if lines and lines[0].strip() == "---":
            for i in range(1, len(lines)):
                if lines[i].strip() == "---":
                    return lines[i + 1:]
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

            full_path = os.path.join(root, file)
            base_filename = file[:-3]

            with open(full_path, "r", encoding="utf-8") as f:
                lines = skip_yaml(f.readlines())

            content_line = next((line.strip() for line in lines if line.strip()), "")
            cleaned = clean_markdown_line(content_line)

            # Case 1: already UID named
            if base_filename.startswith("uid_"):
                expected = uid_to_expected_full.get(base_filename)
                if expected:
                    if expected != cleaned:
                        log(f"⚠️ 錯誤：{file} 的內容與 map 不符，應為：{expected}")
                else:
                    log(f"⚠️ 警告：{file} 是 UID 檔案，但未在 map 中登錄")
                continue

            # Case 2: filename not uid_*, but is semantic truncation
            match, reason = compare_filename_and_line(base_filename, cleaned)

            log(f"{'✔️' if match else '❌'} {file}\n  ↪ 檔名: {base_filename}\n  ↪ 首句: {cleaned}\n  ↪ 理由: {reason}\n")

            if match:
                if cleaned in full_to_uid:
                    uid = full_to_uid[cleaned]
                else:
                    uid = f"uid_{uid_index:03d}"
                    uid_index += 1
                    truncation_map[base_filename] = {
                        "uid": uid,
                        "full_sentence": cleaned
                    }
                    full_to_uid[cleaned] = uid
                    uid_to_expected_full[uid] = cleaned

                desired_path = os.path.join(root, uid + ".md")

                if os.path.exists(desired_path):
                    with open(desired_path, "r", encoding="utf-8") as f:
                        existing = skip_yaml(f.readlines())
                        existing_line = next((line.strip() for line in existing if line.strip()), "")
                        existing_cleaned = clean_markdown_line(existing_line)
                    if existing_cleaned != cleaned:
                        i = 1
                        while os.path.exists(os.path.join(root, f"{uid}({i}).md")):
                            i += 1
                        alt_path = os.path.join(root, f"{uid}({i}).md")
                        os.rename(full_path, alt_path)
                        log(f"⚠️ 衝突：{file} → 改為 {uid}({i}).md，避免覆寫 {uid}.md")
                    else:
                        os.remove(full_path)  # Duplicate, keep the UID version
                        log(f"✅ {file} 已有正確 UID 檔案，原始檔刪除")
                else:
                    os.rename(full_path, desired_path)
                    log(f"🔁 已重新命名: {file} → {uid}.md\n")

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
