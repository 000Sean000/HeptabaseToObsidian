# src/main.py

import os
import sys
sys.path.append(os.path.dirname(__file__))

from detect_invalid_md_filenames import detect_invalid_md_filenames
from rename_md_files_safely import rename_md_files_safely
from preprocess_heptabase_yaml import clean_yaml_artifacts
from convert_links_to_wikilinks import convert_links_to_wikilinks
from analyze_indent_stat import analyze_indent_diffs
from standardize_md_indentation import standardize_md_indentation
from unwrap_hard_wraps import unwrap_hard_wraps
from build_uid_map_for_truncated_titles import build_uid_map_for_truncated_titles
from rewrite_links_with_uid_alias import rewrite_links_with_uid_alias


def run_pipeline_step(step_func, *args, name=None):
    print(f"\n🚀 執行模組：{name}")
    result = step_func(*args)
    print(f"✅ {name} 完成")
    return result


def main():
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    VAULT_PATH = os.path.join(BASE_DIR, "TestData")
    LOG_DIR = os.path.join(BASE_DIR, "log")
    os.makedirs(LOG_DIR, exist_ok=True)
    VERBOSE = True

    INDENT_ANALYSIS_LOG = os.path.join(LOG_DIR, "indent_analysis.log")
    INDENT_UNIT_MAP_PATH = os.path.join(LOG_DIR, "indent_unit_map.json")
    INDENT_FIX_LOG = os.path.join(LOG_DIR, "indent_fix.log")
    UNWRAP_LOG = os.path.join(LOG_DIR, "unwrap_hard_wraps.log")

    steps = [
        {
            "name": "1️⃣ 檢查非法檔名",
            "func": detect_invalid_md_filenames,
            "args": (
                VAULT_PATH,
                os.path.join(LOG_DIR, "invalid_filenames.log"),
                VERBOSE
            ),
        },
        {
            "name": "2️⃣ 重命名非法檔名",
            "func": rename_md_files_safely,
            "args": (
                VAULT_PATH,
                os.path.join(LOG_DIR, "rename_map.json"),
                os.path.join(LOG_DIR, "rename_phase.log"),
                None,  # invalid_char_check
                VERBOSE
            ),
        },
        {
            "name": "3️⃣ 清理 YAML 結構與雙引號",
            "func": clean_yaml_artifacts,
            "args": (
                VAULT_PATH,
                os.path.join(LOG_DIR, "yaml_preprocess.log"),
                VERBOSE
            ),
        },
        {
            "name": "4️⃣ 轉換 markdown link 成 wiki link",
            "func": convert_links_to_wikilinks,
            "args": (
                VAULT_PATH,
                os.path.join(LOG_DIR, "rename_map.json"),
                os.path.join(LOG_DIR, "link_conversion.log"),
                VERBOSE
            ),
        },
        {
            "name": "5️⃣ 分析縮排單位",
            "func": analyze_indent_diffs,
            "args": (
                VAULT_PATH,
                INDENT_ANALYSIS_LOG,
                INDENT_UNIT_MAP_PATH,
                4,
                0.5,
                VERBOSE
            ),
        },
        {
            "name": "6️⃣ 統一縮排格式",
            "func": standardize_md_indentation,
            "args": (
                VAULT_PATH,
                INDENT_FIX_LOG,
                VERBOSE,
                4,      # spaces_per_indent
                INDENT_UNIT_MAP_PATH,
                4       # fallback_unit
            ),
        },
        {
            "name": "7️⃣ 掃描語意斷句並重新命名為 UID",
            "func": build_uid_map_for_truncated_titles,
            "args": (
                VAULT_PATH,
                os.path.join(LOG_DIR, "truncation_map.json"),
                os.path.join(LOG_DIR, "truncation_detect.log"),
                VERBOSE
            ),
        },
        {
            "name": "8️⃣ 替換 link 為 UID 與語意 alias",
            "func": rewrite_links_with_uid_alias,
            "args": (
                VAULT_PATH,
                os.path.join(LOG_DIR, "truncation_map.json"),
                os.path.join(LOG_DIR, "uid_link_rewrite.log"),
                "@",
                VERBOSE
            ),
        },

    ]

    print("\n📋 將執行以下步驟：")
    for step in steps:
        print(f"   - {step['name']}")

    print("\n🔧 請選擇執行模式：")
    print("1. 每步執行後需確認")
    print("2. 一次執行整個流程")
    mode = input("輸入 1 或 2：").strip()

    for step in steps:
        if mode == "1":
            print(f"\n⏳ 即將執行：{step['name']}")
            user_input = input("➡️ 按 Enter 執行，或輸入 q 離開：").strip().lower()
            if user_input == "q":
                print("🛑 執行中止。")
                break

        run_pipeline_step(step["func"], *step["args"], name=step["name"])


if __name__ == "__main__":
    main()


    
