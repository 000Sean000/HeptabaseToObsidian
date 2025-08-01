# 這份code疑似沒用了

import os
import re
import json
from datetime import datetime

def fix_wiki_links_with_rename_map(vault_path, rename_map_path, log_path=None, verbose=False):
    changed_files = []
    rename_map = {}

    if not os.path.exists(rename_map_path):
        raise FileNotFoundError(f"❌ rename_map not found at {rename_map_path}")

    with open(rename_map_path, "r", encoding="utf-8") as f:
        rename_map = json.load(f)

    rename_wiki_map = {
        os.path.splitext(os.path.basename(orig).replace("%20", " "))[0]:
        os.path.splitext(os.path.basename(new).replace("%20", " "))[0]
        for orig, new in rename_map.items()
    }

    def log(msg):
        if log_path:
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(msg + "\n")
        if verbose:
            print(msg)

    wiki_pattern = re.compile(r"\[\[([^\[\]]+?)\]\]")

    def convert(content):
        count = 0
        def replace(match):
            nonlocal count
            link_text = match.group(1).strip()
            if "|" in link_text:
                target, alias = link_text.split("|", 1)
            else:
                target, alias = link_text, None

            target_clean = target.strip()
            new_target = rename_wiki_map.get(target_clean)
            if new_target and new_target != target_clean:
                count += 1
                log(f"🔁 修正 wiki link: [[{target_clean}]] → [[{new_target}]]")
                return f"[[{new_target}|{alias}]]" if alias else f"[[{new_target}]]"
            return match.group(0)

        return wiki_pattern.sub(replace, content), count

    if log_path:
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(f"🛠 Fix Wiki Link Log — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

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
                    log(f"✅ {rel_path}：修正 {changed} 筆 wiki link")
                else:
                    log(f"☑️ {rel_path}：無需修改")

    if changed_files:
        log(f"\n🎉 總共修正 wiki link 檔案數：{len(changed_files)}")
    else:
        log("✅ 沒有發現需修正的 wiki link。")

    return changed_files

# 🔹 單獨執行
if __name__ == "__main__":
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    VAULT_PATH = os.path.join(BASE_DIR, "TestData")
    RENAME_MAP_PATH = os.path.join(BASE_DIR, "log", "rename_map.json")
    LOG_PATH = os.path.join(BASE_DIR, "log", "fix_wikilinks.log")

    fix_wiki_links_with_rename_map(
        vault_path=VAULT_PATH,
        rename_map_path=RENAME_MAP_PATH,
        log_path=LOG_PATH,
        verbose=True
    )
