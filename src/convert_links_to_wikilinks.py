# src/convert_links_to_wikilinks.py

import os
import re
import json
from datetime import datetime
from urllib.parse import unquote

def normalize_filename(link: str) -> str:
    return unquote(os.path.basename(link)).replace("\\(", "(").replace("\\)", ")").strip()

# 更新 shared_replace_function，讓 label 也進行 normalization
def shared_replace_function(rename_name_map, log, wrap_in_quotes=False):
    def replace(match):
        full_match = match.group(0)
        label = match.group(1).strip()
        link = match.group(2).strip()

        # Normalize both label and link for comparison
        label_clean = normalize_filename(label)
        basename = normalize_filename(link)

        matched_new = rename_name_map.get(label_clean) or rename_name_map.get(basename)
        final_label = label
        if matched_new:
            final_label = os.path.splitext(matched_new)[0]
            if final_label != label:
                log(f"🔁 Label 修正: [{label}] → [[{final_label}]]")

        wiki_link = f"[[{final_label}]]"
        if full_match.startswith('"') and full_match.endswith('"'):
            return f'"{wiki_link}"'
        return wiki_link
    return replace


def convert_links_to_wikilinks(vault_path, rename_map_path=None, log_path=None, verbose=False):
    changed_files = []
    rename_map = {}

    if rename_map_path and os.path.exists(rename_map_path):
        with open(rename_map_path, "r", encoding="utf-8") as f:
            rename_map = json.load(f)

    rename_name_map = {
        normalize_filename(orig): os.path.basename(new)
        for orig, new in rename_map.items()
    }

    def log(msg):
        if log_path:
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(msg + "\n")
        if verbose:
            print(msg)

    md_pattern = re.compile(r'(?<!\!)\[(.+?)\]\((.+?\.md)\)')
    yaml_pattern = re.compile(r'"?\[(.+?)\]\((.+?\.md)\)"?', re.DOTALL)

    def convert(content):
        md_count = 0
        yaml_count = 0

        # 處理 markdown 區域
        new_content, md_count = md_pattern.subn(shared_replace_function(rename_name_map, log, wrap_in_quotes=False), content)
        # 處理 yaml 區域（允許換行，並自動補回原始引號）
        new_content, yaml_count = yaml_pattern.subn(shared_replace_function(rename_name_map, log, wrap_in_quotes=True), new_content)

        return new_content, md_count + yaml_count

    if log_path:
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(f"🔗 Link Conversion Log — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

    for root, _, files in os.walk(vault_path):
        for file in files:
            if file.endswith(".md"):
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, vault_path)

                with open(full_path, "r", encoding="utf-8") as f:
                    content = f.read()

                new_content, count = convert(content)

                if new_content != content:
                    with open(full_path, "w", encoding="utf-8") as f:
                        f.write(new_content)
                    changed_files.append(rel_path)
                    log(f"✅ {rel_path}：修正 {count} 處")
                else:
                    log(f"☑️ {rel_path}：無需修改")

    if changed_files:
        log(f"\n🎉 共更新 {len(changed_files)} 個檔案的 markdown link。")
    else:
        log("✅ 沒有發現可轉換的 markdown link。")

    return changed_files

# === 🧪 單獨執行測試區 ===
if __name__ == "__main__":
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    VAULT_PATH = os.path.join(BASE_DIR, "TestData")
    RENAME_MAP_PATH = os.path.join(BASE_DIR, "log", "rename_map.json")
    LOG_PATH = os.path.join(BASE_DIR, "log", "link_conversion.log")

    convert_links_to_wikilinks(
        vault_path=VAULT_PATH,
        rename_map_path=RENAME_MAP_PATH,
        log_path=LOG_PATH,
        verbose=True
    )

