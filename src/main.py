# src/main.py

import os
import sys
sys.path.append(os.path.dirname(__file__))

from detect_invalid_md_filenames import detect_invalid_md_filenames
from rename_md_files_safely import rename_md_files_safely
from preprocess_heptabase_yaml import clean_yaml_artifacts
from convert_links_to_wikilinks import convert_links_to_wikilinks


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
            "name": "5️⃣ 統一縮排為 4-space",
            "func": standardize_md_indentation,
            "args": (
                VAULT_PATH,
                os.path.join(LOG_DIR, "indent_fix.log"),
                VERBOSE
            ),
        },

    ]

    print("🔧 請選擇執行模式：")
    print("1. 每步執行後需確認")
    print("2. 一次執行整個流程")
    mode = input("輸入 1 或 2：").strip()

    for step in steps:
        run_pipeline_step(step["func"], *step["args"], name=step["name"])

        if mode == "1":
            user_input = input("\n➡️ 按 Enter 執行下一步，或輸入 q 離開：").strip().lower()
            if user_input == "q":
                print("🛑 執行中止。")
                break

if __name__ == "__main__":
    main()
