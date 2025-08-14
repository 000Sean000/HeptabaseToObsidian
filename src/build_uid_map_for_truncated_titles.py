# src/build_uid_map_for_truncated_titles.py

import os
import re
import json
from datetime import datetime
from typing import Tuple
from utils.get_safe_path import get_safe_path  # ✅ 新增導入
from utils.logger import Logger


LONG_FILENAME_UTF8_BYTES_THRESHOLD = 70  # 目前檔名約能使用97Byte，不排除有容量更小、提前截斷的情況，所以可能要設得比97小一些


def build_uid_map_for_truncated_titles(vault_path, map_path, log_path, verbose=False):
    truncation_map = {}
    full_to_uid = {}
    uid_to_expected_full = {}

    uid_index = 1

    logger = Logger(log_path=log_path, verbose=verbose, title=None)
    log = logger.log
    
    modification_stats = {
        "new_uid_assigned": 0,
        "uid_corrected": 0,
        "map_updated_from_filename": 0,
        "temp_fixed_to_uid": 0,
        "temp_fixed_to_uid_with_conflict": 0,
        "temp_fixed_new_uid": 0,
        "duplicate_warning": 0
    }


    # ✅ 使用 get_safe_path 包裝 map 路徑
    map_path = get_safe_path(map_path)

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
        uid_count_before = len(truncation_map)  # ✅ 新增：記錄原始數量
    except Exception as e:
        log(f"⚠️ 無法讀取舊 map，將重新從 uid_001 開始。錯誤：{e}")
        truncation_map = {}
        uid_index = 1
        uid_count_before = 0  # 若 map 讀取失敗，初始化為 0


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
    
    def is_truncated(filename: str, full_sentence: str) -> tuple[bool, str]:
        filename_clean = remove_trailing_number(filename)

        tail = full_sentence[len(filename_clean):].strip()
        filename_byte_length = len(filename_clean.encode("utf-8"))
        if tail in {".", "?", "!"}:
            return True, f"✔️ 補述為符號：'{tail}' → 認定為截斷"
        elif filename_byte_length >= LONG_FILENAME_UTF8_BYTES_THRESHOLD and tail:
            return True, f"✔️ 檔名長且有補述（{filename_byte_length} bytes）→ 認定為截斷"
        return False, f"❌ 檔名長度 {filename_byte_length} bytes，補述非關鍵 → 非截斷"
    
    def fix_wrong_uid_filename(uid_index, file_path, base_filename, cleaned, expected_uid, root, log):
        """
        修正錯誤命名的 UID 檔案名稱
        """
        if not expected_uid:
            #log(f"⚠️ 找不到與內容對應的正確 UID → 無法修正 {base_filename}.md")
            log(f"⚠️ 找不到與內容對應的正確 UID → 新增UID")
            uid, uid_index = get_unused_uid(root, uid_index)
            if cleaned in full_to_uid:
                existent_uid = full_to_uid[cleaned]
                log(f"⚠️ 警告：{uid}.md 和{existent_uid}.md 的語意相同，請人工檢查是否為重複的檔案！")
            truncation_map[f"{base_filename} (duplicated?)"] = {
                "uid": uid,
                "full_sentence": cleaned
            }
            full_to_uid[cleaned] = uid
            uid_to_expected_full[uid] = cleaned                      
            desired_path = os.path.join(root, uid + ".md")
            safe_desired_path = get_safe_path(desired_path)     
            os.rename(safe_full_path, safe_desired_path)
            log(f"🔁 已重新命名: {file} → {uid}.md\n")             
            modification_stats["new_uid_assigned"] += 1
            return

        correct_name = f"{expected_uid}.md"
        correct_path = os.path.join(root, correct_name)
        safe_correct_path = get_safe_path(correct_path)

        if os.path.exists(safe_correct_path):
            try:
                with open(safe_correct_path, "r", encoding="utf-8") as f:
                    lines = skip_yaml(f.readlines())
                    existing_line = next((line.strip() for line in lines if line.strip()), "")
                    existing_cleaned = clean_markdown_line(existing_line)
            except Exception as e:
                log(f"⚠️ 無法讀取 {correct_name} 內容：{e}")
                return

            if existing_cleaned == cleaned:
                # 內容相同 → 不更動正確檔案，將目前錯誤的檔案改名為 uid_xxx(n)
                i = 1
                while True:
                    alt_path = os.path.join(root, f"{expected_uid}({i}).md")
                    safe_alt_path = get_safe_path(alt_path)
                    if not os.path.exists(safe_alt_path):
                        break
                    i += 1
                os.rename(file_path, safe_alt_path)
                log(f"⚠️ UID 重複：{base_filename}.md 內容與 {expected_uid}.md 相同，改名為 {expected_uid}({i}).md 避免衝突")
                modification_stats["duplicate_warning"] += 1

            else:
                # 內容不同 → 將正確檔案改為暫名 uid_fix_temp(n)
                i = 1
                while True:
                    temp_path = os.path.join(root, f"uid_fix_temp({i}).md")
                    safe_temp_path = get_safe_path(temp_path)
                    if not os.path.exists(safe_temp_path):
                        break
                    i += 1
                os.rename(safe_correct_path, safe_temp_path)
                os.rename(file_path, safe_correct_path)
                log(f"⚠️ UID 衝突：{expected_uid}.md 被錯誤佔用，已移至 uid_fix_temp({i}).md，並將 {base_filename}.md 正名為 {expected_uid}.md")
        else:
            # 沒有正確檔案 → 直接正名
            os.rename(file_path, safe_correct_path)
            log(f"🔁 已修正檔名：{base_filename}.md → {expected_uid}.md")
            modification_stats["uid_corrected"] += 1


    def update_uid_map_from_filename(
        file_path,
        base_filename,
        cleaned,
        root,
        truncation_map,
        full_to_uid,
        uid_to_expected_full,
        uid_index,
        log
    ):
        """
        處理未登錄 map 的 UID 檔案：指派新的 UID 並更新 map
        """

        # 指派一個新的 UID（舊的 uid 編號不保留）
        uid, uid_index = get_unused_uid(root, uid_index)

        # 更新 map
        truncation_map[base_filename] = {
            "uid": uid,
            "full_sentence": cleaned
        }
        full_to_uid[cleaned] = uid
        uid_to_expected_full[uid] = cleaned

        # 重新命名檔案
        desired_path = os.path.join(root, uid + ".md")
        safe_desired_path = get_safe_path(desired_path)
        os.rename(file_path, safe_desired_path)

        log(f"🔁 未登錄 UID 檔案 {base_filename}.md 已重新命名為 {uid}.md 並更新 map")
        modification_stats["map_updated_from_filename"] += 1

        return uid_index  # 回傳最新 uid_index 給主程式更新


    def fix_temp_uid_files(
        vault_path,
        truncation_map,
        full_to_uid,
        uid_to_expected_full,
        uid_index,
        log,
        modification_stats
    ):
        for root, _, files in os.walk(vault_path):
            for file in files:
                if not file.startswith("uid_fix_temp(") or not file.endswith(".md"):
                    continue

                full_path = os.path.join(root, file)
                safe_full_path = get_safe_path(full_path)

                try:
                    with open(safe_full_path, "r", encoding="utf-8") as f:
                        lines = skip_yaml(f.readlines())
                except Exception as e:
                    log(f"⚠️ 無法讀取暫存檔 {file}：{e}")
                    continue

                content_line = next((line.strip() for line in lines if line.strip()), "")
                if not content_line:
                    log(f"⚠️ 暫存檔 {file} 為空，略過")
                    continue

                cleaned = clean_markdown_line(content_line)

                if cleaned in full_to_uid:
                    correct_uid = full_to_uid[cleaned]
                    desired_path = os.path.join(root, correct_uid + ".md")
                    safe_desired_path = get_safe_path(desired_path)

                    if os.path.exists(safe_desired_path):
                        with open(safe_desired_path, "r", encoding="utf-8") as f:
                            existing_lines = skip_yaml(f.readlines())
                            existing_line = next((line.strip() for line in existing_lines if line.strip()), "")
                            existing_cleaned = clean_markdown_line(existing_line)

                        if existing_cleaned == cleaned:
                            os.remove(safe_full_path)
                            log(f"🗑️ 移除重複暫存檔 {file}，與 {correct_uid}.md 內容一致")
                        else:
                            i = 1
                            while True:
                                alt_path = os.path.join(root, f"{correct_uid}({i}).md")
                                safe_alt_path = get_safe_path(alt_path)
                                if not os.path.exists(safe_alt_path):
                                    break
                                i += 1
                            os.rename(safe_full_path, safe_alt_path)
                            log(f"⚠️ 衝突：{file} → 改為 {correct_uid}({i}).md，因為 {correct_uid}.md 內容不同")
                            modification_stats["temp_fixed_to_uid_with_conflict"] += 1

                    else:
                        os.rename(safe_full_path, safe_desired_path)
                        log(f"🔁 修正暫存檔：{file} → {correct_uid}.md")
                        modification_stats["temp_fixed_to_uid"] += 1

                else:
                    new_uid, uid_index = get_unused_uid(root, uid_index)
                    truncation_map[file[:-3]] = {
                        "uid": new_uid,
                        "full_sentence": cleaned
                    }
                    full_to_uid[cleaned] = new_uid
                    uid_to_expected_full[new_uid] = cleaned

                    desired_path = os.path.join(root, new_uid + ".md")
                    safe_desired_path = get_safe_path(desired_path)
                    os.rename(safe_full_path, safe_desired_path)
                    log(f"🆕 暫存檔未配對 map → 指派新 UID：{file} → {new_uid}.md")
                    modification_stats["temp_fixed_new_uid"] += 1


        return uid_index

    
    def get_unused_uid(root, uid_index):
        """索取一個沒被使用的 UID"""
        while True:
            uid = f"uid_{uid_index:03d}"
            desired_path = os.path.join(root, uid + ".md")
            safe_desired_path = get_safe_path(desired_path)
            if not os.path.exists(safe_desired_path):
                return uid, uid_index + 1
            uid_index += 1




    for root, _, files in os.walk(vault_path):
        for file in files:
            if not file.endswith(".md"):
                continue

            full_path = os.path.join(root, file)
            safe_full_path = get_safe_path(full_path)
            base_filename = file[:-3]

            try:
                with open(safe_full_path, "r", encoding="utf-8") as f:
                    lines = skip_yaml(f.readlines())
            except Exception as e:
                log(f"⚠️ 無法讀取 {file}：{e}")
                continue

            content_line = next((line.strip() for line in lines if line.strip()), "")
            if not content_line:
                log(f"⚠️ {file} 為空檔案，略過")
                continue

            cleaned = clean_markdown_line(content_line)

            if base_filename.startswith("uid_"): # 檢查現有的 uid 筆記
                expected = uid_to_expected_full.get(base_filename)
                if expected:
                    if expected != cleaned:
                        log(f"⚠️ 錯誤：{file} 的內容與 map 不符，應為：{expected}")
                        fix_wrong_uid_filename(
                            uid_index=uid_index,
                            file_path=safe_full_path,
                            base_filename=base_filename,
                            cleaned=cleaned,
                            expected_uid=full_to_uid.get(cleaned),
                            root=root,
                            log=log
                        )
                
                else:
                    log(f"⚠️ 警告：{file} 是 UID 檔案，但未在 map 中登錄")
                    uid_index = update_uid_map_from_filename(
                        file_path=safe_full_path,
                        base_filename=base_filename,
                        cleaned=cleaned,
                        root=root,
                        truncation_map=truncation_map,
                        full_to_uid=full_to_uid,
                        uid_to_expected_full=uid_to_expected_full,
                        uid_index=uid_index,
                        log=log
                    )

                continue
            else: # 新增 uid 筆記
                match, reason_match = compare_filename_and_line(base_filename, cleaned)
                log(f"{'✔️' if match else '❌'} {file}\n  ↪ 檔名: {base_filename}\n  ↪ 首句: {cleaned}\n  ↪ 理由: {reason_match}")

                if not match:
                    continue

                truncated, reason_trunc = is_truncated(base_filename, cleaned)
                log(f"📎 判斷截斷: {'是' if truncated else '否'} — {reason_trunc}\n")

                if not truncated:
                    continue

                
                
   
    uid_index = fix_temp_uid_files(
        vault_path=vault_path,
        truncation_map=truncation_map,
        full_to_uid=full_to_uid,
        uid_to_expected_full=uid_to_expected_full,
        uid_index=uid_index,
        log=log,
        modification_stats=modification_stats
    )



    # ✅ 統計新增的 UID 數
    new_uid_count = len(truncation_map) - uid_count_before
    log(f"\n📌 本次新增 UID 數：{new_uid_count} 筆")
    log("\n📊 修改統計：")
    for k, v in modification_stats.items():
        log(f"  - {k}: {v} 次")



    # ✅ 安全儲存 map 與 log
    os.makedirs(os.path.dirname(map_path), exist_ok=True)
    with open(map_path, "w", encoding="utf-8") as f:
        json.dump(truncation_map, f, indent=2, ensure_ascii=False)

    logger.save()

    return truncation_map


# === 🧪 單獨執行 ===
if __name__ == "__main__":
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    VAULT_DIR = os.path.join(BASE_DIR, "TestData")
    MAP_PATH = os.path.join(BASE_DIR, "log", "truncation_map.json")
    LOG_PATH = os.path.join(BASE_DIR, "log", "truncation_detect.log")

    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    build_uid_map_for_truncated_titles(VAULT_DIR, MAP_PATH, LOG_PATH, verbose=True)
