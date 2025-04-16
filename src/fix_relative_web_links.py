import os
import re
from datetime import datetime

def fix_relative_web_links(vault_path, log_path=None, verbose=False):
    pattern = re.compile(r'\[([^\]]+?)\]\(((?!https?://)[a-zA-Z0-9.-]+\.[a-z]{2,}[^)\s]*)\)')
    changed_files = []
    scanned_files = 0

    def log(msg):
        if log_path:
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(msg + "\n")
        if verbose:
            print(msg)

    if log_path:
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(f"🌐 Web Link Fix Log — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

    for root, _, files in os.walk(vault_path):
        for file in files:
            if file.endswith(".md"):
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, vault_path)
                scanned_files += 1

                with open(full_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                match_log = []

                def repl(match):
                    label = match.group(1)
                    target = match.group(2)
                    fixed = f"[{label}](https://{target})"
                    match_log.append(f"🔗 修正: [{label}]({target}) → {fixed}")
                    return fixed

                new_content, count = pattern.subn(repl, content)

                if count > 0:
                    with open(full_path, 'w', encoding='utf-8') as f:
                        f.write(new_content)
                    changed_files.append(rel_path)
                    log(f"✅ {rel_path}：修正 {count} 個連結")
                    for msg in match_log:
                        log("   " + msg)
                else:
                    log(f"☑️ {rel_path}：無需修改")

    log(f"\n📊 掃描完成：共掃描 {scanned_files} 個檔案，其中 {len(changed_files)} 個檔案有修改。")
    return changed_files


# ✅ 建議給 main.py 用的測試入口（不要用 __file__，交由主程式處理）
if __name__ == "__main__":
    vault = os.path.abspath("../TestData")
    log_file = os.path.abspath("../log/web_link_fix.log")
    fix_relative_web_links(vault, log_path=log_file, verbose=True)
