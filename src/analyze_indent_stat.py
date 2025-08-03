# src/analyze_indent_stat.py

import os
import json
from collections import Counter
from datetime import datetime
from utils import get_safe_path  # ← 加入此行，確保 utils.py 裡有定義


def get_leading_spaces(line: str) -> int:
    return len(line) - len(line.lstrip(' '))


def analyze_indent_diffs(folder_path, log_path=None, map_path=None, fallback_indent=4, threshold=0.5):
    global_indent_diffs = Counter()
    file_indent_map = {}

    if log_path:
        safe_log_path = get_safe_path(log_path)
        os.makedirs(os.path.dirname(safe_log_path), exist_ok=True)
        with open(safe_log_path, "w", encoding="utf-8") as f:
            f.write(f"📊 Indent Unit Analysis Log — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

    for root, _, files in os.walk(folder_path):
        for file in files:
            if not file.endswith(".md"):
                continue

            full_path = os.path.join(root, file)
            safe_full_path = get_safe_path(full_path)
            rel_path = os.path.relpath(full_path, folder_path)

            with open(safe_full_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            space_indents = [get_leading_spaces(line) for line in lines if line.strip()]
            diffs = []

            for i in range(1, len(space_indents)):
                diff = space_indents[i] - space_indents[i - 1]
                if diff != 0:
                    diffs.append(diff)
                    global_indent_diffs[diff] += 1

            pos_diffs = [d for d in diffs if d > 0]
            pos_diff_counter = Counter(pos_diffs)
            total_pos = sum(pos_diff_counter.values())

            if not pos_diff_counter:
                summary = f"☑️ {rel_path}: 無正向縮排變化"
                file_indent_map[rel_path] = fallback_indent
            else:
                unit_list = sorted(pos_diff_counter.items(), key=lambda x: -x[1])
                unit_str = ", ".join(
                    f"{k} ({v} 次, {v/total_pos:.0%})"
                    for k, v in unit_list
                )

                top_unit, top_count = unit_list[0]
                top_ratio = top_count / total_pos

                if len(pos_diff_counter) == 1:
                    summary = f"✅ {rel_path}: 統一縮排單位 = {top_unit} → {unit_str}"
                    file_indent_map[rel_path] = top_unit
                elif top_ratio >= threshold:
                    summary = f"⚠️ {rel_path}: 主縮排單位 = {top_unit} (占比 {top_ratio:.0%}) → {unit_str}"
                    file_indent_map[rel_path] = top_unit
                else:
                    summary = f"🚫 {rel_path}: 無明顯縮排單位 → {unit_str}，使用 fallback = {fallback_indent}"
                    file_indent_map[rel_path] = fallback_indent

            if log_path:
                with open(get_safe_path(log_path), "a", encoding="utf-8") as f:
                    f.write(summary + "\n")

            print(summary)

    if map_path:
        with open(get_safe_path(map_path), "w", encoding="utf-8") as f:
            json.dump(file_indent_map, f, indent=2, ensure_ascii=False)

    return global_indent_diffs, file_indent_map


# === 🧪 測試用入口 ===
if __name__ == "__main__":
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    VAULT_PATH = os.path.join(BASE_DIR, "TestData")
    LOG_PATH = os.path.join(BASE_DIR, "log", "indent_analysis.log")
    MAP_PATH = os.path.join(BASE_DIR, "log", "indent_unit_map.json")

    result, unit_map = analyze_indent_diffs(
        folder_path=VAULT_PATH,
        log_path=LOG_PATH,
        map_path=MAP_PATH
    )

    print("\n📊 全域縮排差異統計：")
    for diff, count in sorted(result.items()):
        print(f"{diff:+3d} → {count} 次")

    print(f"\n🗺️ 縮排單位對應表已輸出至：{MAP_PATH}")
