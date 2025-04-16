# src/convert_links_to_wikilinks.py

import os
import re
import json
from datetime import datetime

import os
import re
import json
from datetime import datetime

def convert_links_to_wikilinks(
    vault_path,
    rename_map_path=None,
    log_path=None,
    verbose=False
):
    changed_files = []
    rename_map = {}

    if rename_map_path and os.path.exists(rename_map_path):
        with open(rename_map_path, "r", encoding="utf-8") as f:
            rename_map = json.load(f)

    rename_name_map = {
        os.path.basename(orig).replace("%20", " "): os.path.basename(new)
        for orig, new in rename_map.items()
    }

    def log(msg):
        if log_path:
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(msg + "\n")
        if verbose:
            print(msg)

    pattern = re.compile(r'(?<!\!)\[(.+?)\]\((.+?\.md)\)')

    def convert(content):
        count = 0

        def replace(match):
            nonlocal count
            label = match.group(1).strip()
            link = os.path.normpath(match.group(2).strip())
            basename = os.path.basename(link).replace("%20", " ")

            matched_new = rename_name_map.get(basename)
            final_label = label
            if matched_new:
                final_label = os.path.splitext(matched_new)[0]
                if final_label != label:
                    log(f"🔁 Label 修正: [{label}] → [[{final_label}]]")

            count += 1
            return f"[[{final_label}]]"

        new_content = pattern.sub(replace, content)
        return new_content, count

    if log_path:
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(f"🔗 Link Conversion Log — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

    for root, _, files in os.walk(vault_path):
        for file in files:
            if file.endswith(".md"):
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, vault_path)

                with open(full_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                new_content, changed = convert(content)

                if changed > 0:
                    with open(full_path, 'w', encoding='utf-8') as f:
                        f.write(new_content)
                    changed_files.append(rel_path)
                    log(f"✅ {rel_path}：轉換 {changed} 個連結")
                else:
                    log(f"☑️ {rel_path}：無需修改")

    if changed_files:
        log(f"\n🎉 共更新 {len(changed_files)} 個檔案的 markdown link。")
    else:
        log("✅ 沒有發現可轉換的 markdown link。")

    return changed_files



if __name__ == "__main__":
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    VAULT_PATH = os.path.join(BASE_DIR, "TestData")
    LOG_PATH = os.path.join(BASE_DIR, "log", "link_conversion.log")
    RENAME_MAP_PATH = os.path.join(BASE_DIR, "log", "rename_map.json")

    convert_links_to_wikilinks(
        vault_path=VAULT_PATH,
        rename_map_path=RENAME_MAP_PATH,
        log_path=LOG_PATH,
        verbose=True
    )
