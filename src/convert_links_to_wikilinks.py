# src/convert_links_to_wikilinks.py

import os
import re
import json
from datetime import datetime
from urllib.parse import unquote
from utils import get_safe_path  # ← 確保 utils.py 有這個 function


def normalize_filename(link: str) -> str:
    name = unquote(os.path.basename(link))
    name = name.replace("\\(", "(").replace("\\)", ")").strip()
    return os.path.splitext(name)[0].rstrip(". ")  # 清除尾部句點/空白

def shared_replace_function(rename_name_map, log, wrap_in_quotes=False):
    def replace(match):
        label = match.group(1).strip()
        link = match.group(2).strip()

        label_clean = normalize_filename(label)
        link_clean = normalize_filename(link)

        if label_clean in rename_name_map:
            matched_new = rename_name_map[label_clean]
            source = f"label → {label_clean}"
        elif link_clean in rename_name_map:
            matched_new = rename_name_map[link_clean]
            source = f"link → {link_clean}"
        else:
            matched_new = None
            source = "fallback to original"

        final_label = matched_new if matched_new else label_clean
        log(f"🔁 轉換: [{label}]({link}) → [[{final_label}]] (based on {source})")

        wiki_link = f"[[{final_label}]]"
        return f'"{wiki_link}"' if wrap_in_quotes else wiki_link

    return replace


def convert_links_to_wikilinks(vault_path, rename_map_path=None, log_path=None, verbose=False):
    changed_files = []
    rename_map = {}

    if rename_map_path and os.path.exists(rename_map_path):
        rename_map_path = get_safe_path(rename_map_path)
        with open(rename_map_path, "r", encoding="utf-8") as f:
            rename_map = json.load(f)

    rename_name_map = {
        normalize_filename(orig): normalize_filename(new)
        for orig, new in rename_map.items()
    }

    def log(msg):
        if log_path:
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
            safe_log_path = get_safe_path(log_path)
            with open(safe_log_path, "a", encoding="utf-8") as f:
                f.write(msg + "\n")
        if verbose:
            print(msg)

    md_pattern = re.compile(r'(?<!\!)\[(.+?)\]\((.+?\.md)\)', re.DOTALL)
    yaml_pattern = re.compile(r'"?\[(.+?)\]\((.+?\.md)\)"?', re.DOTALL)

    def convert(content):
        content, n1 = md_pattern.subn(shared_replace_function(rename_name_map, log, wrap_in_quotes=False), content)
        content, n2 = yaml_pattern.subn(shared_replace_function(rename_name_map, log, wrap_in_quotes=True), content)
        return content, n1 + n2

    if log_path:
        safe_log_path = get_safe_path(log_path)
        with open(safe_log_path, "w", encoding="utf-8") as f:
            f.write(f"🔗 Link Conversion Log — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

    for root, _, files in os.walk(vault_path):
        for file in files:
            if file.endswith(".md"):
                full_path = os.path.join(root, file)
                safe_full_path = get_safe_path(full_path)
                rel_path = os.path.relpath(full_path, vault_path)

                with open(safe_full_path, "r", encoding="utf-8") as f:
                    content = f.read()

                new_content, count = convert(content)

                if new_content != content:
                    with open(safe_full_path, "w", encoding="utf-8") as f:
                        f.write(new_content)
                    changed_files.append(rel_path)
                    log(f"✅ {rel_path}：修正 {count} 處")
                else:
                    log(f"☑️ {rel_path}：無需修改")

    log(f"\n🎉 共更新 {len(changed_files)} 個檔案的 markdown link。" if changed_files else "✅ 沒有發現可轉換的 markdown link。")
    return changed_files


# === 🧪 測試區 ===
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
