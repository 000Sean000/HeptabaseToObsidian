# preprocess_heptabase_yaml.py

import os
import re
import urllib.parse
from datetime import datetime

def encode_url(url):
    return urllib.parse.quote(url, safe="/().-_%")

def clean_link_spacing(line):
    return re.sub(r'"\s+\[', '"[', line)

def split_multi_links(line):
    pattern = re.compile(r'("?\[.+?\]\(.+?\)"?)')
    parts = pattern.findall(line)
    if len(parts) > 1 and ":" not in line:
        return [part.strip() for part in parts]
    return None

def fix_literal_block(lines):
    return [line.rstrip("\\").rstrip() for line in lines]

def fix_link_url_encoding(match):
    label, url = match.group(1), match.group(2)
    encoded_url = encode_url(url)
    return f"[{label}]({encoded_url})"

def fix_link_encodings(line):
    return re.sub(r'\[(.+?)\]\((.+?)\)', fix_link_url_encoding, line)

def fix_double_quotes(line):
    # 移除外層重複雙引號或不對稱情況
    line = re.sub(r'""([^"]+?)""', r'"\1"', line)
    line = re.sub(r'^([^"])?\[', r'"\g<0>', line) if line.strip().startswith("[") else line
    return line

def process_yaml_lines(yaml_lines):
    output_lines = []
    in_literal_block = False
    literal_indent = None
    literal_content = []

    for line in yaml_lines:
        if in_literal_block:
            if line.startswith(" " * literal_indent) or line.strip() == "":
                literal_content.append(line)
                continue
            else:
                # 結束 literal block，先清洗並寫回
                output_lines.extend(fix_literal_block(literal_content))
                in_literal_block = False
                literal_content = []

        if re.search(r"\|\-|\>\-", line.strip()):
            in_literal_block = True
            literal_indent = len(line) - len(line.lstrip())
            output_lines.append(line)
            continue

        # 清理 link 前空白與重複引號
        line = clean_link_spacing(line)
        line = fix_link_encodings(line)
        line = fix_double_quotes(line)

        # 拆分多個連結成陣列
        if re.search(r':\s*".*\[.+?\]\(.+?\).*"', line):
            key, value = line.split(":", 1)
            links = split_multi_links(value)
            if links:
                output_lines.append(f"{key.strip()}:")
                for l in links:
                    output_lines.append(f"  - {l}")
                continue

        output_lines.append(line)

    if in_literal_block and literal_content:
        output_lines.extend(fix_literal_block(literal_content))

    return output_lines

def clean_yaml_artifacts(vault_path, log_path=None, verbose=False):
    changed_files = []

    def log(msg):
        if log_path:
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(msg + "\n")
        if verbose:
            print(msg)

    if log_path:
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(f"🧹 YAML Preprocessing Log — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

    for root, _, files in os.walk(vault_path):
        for file in files:
            if file.endswith(".md"):
                full_path = os.path.join(root, file)
                with open(full_path, "r", encoding="utf-8") as f:
                    content = f.read()

                if content.startswith("---"):
                    parts = content.split("---")
                    if len(parts) >= 3:
                        pre, yaml_raw, post = parts[0], parts[1], "---".join(parts[2:])
                        yaml_lines = yaml_raw.strip().splitlines()
                        cleaned_yaml = process_yaml_lines(yaml_lines)
                        new_content = "---\n" + "\n".join(cleaned_yaml) + "\n---\n" + post.lstrip()

                        if new_content != content:
                            with open(full_path, "w", encoding="utf-8") as f:
                                f.write(new_content)
                            changed_files.append(full_path)
                            log(f"✅ 修正: {full_path}")
                        else:
                            log(f"☑️ 無需修改: {full_path}")

    if changed_files:
        log(f"\n🎉 共清理 {len(changed_files)} 個檔案中的 YAML 區域。")
    else:
        log("✅ 沒有需要修正的 YAML 區塊。")

    return changed_files

# === 🧪 單獨測試區 ===
if __name__ == "__main__":
    BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    VAULT_PATH = os.path.join(BASE, "TestData")
    LOG_PATH = os.path.join(BASE, "log", "yaml_preprocess.log")

    clean_yaml_artifacts(VAULT_PATH, log_path=LOG_PATH, verbose=True)
