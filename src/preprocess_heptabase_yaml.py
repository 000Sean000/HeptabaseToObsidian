# src/preprocess_heptabase_yaml.py

import os
import re
import urllib.parse
from pathlib import Path
from datetime import datetime
from utils.get_safe_path import get_safe_path



def encode_url(url: str) -> str:
    return urllib.parse.quote(url, safe="/().,-_~")


def clean_link_whitespace(text: str) -> str:
    text = re.sub(r'" +(?=\[\[)', '"', text)
    text = re.sub(r'" +(?=\[.+?\]\(.+?\.md\))', '"', text)
    text = re.sub(r'(\[.+?\]\(.+?\.md\)) +(?=")', r'\1', text)
    text = re.sub(r'" +(\[.+?\]\(.+?\.md\)) +?"', r'"\1"', text)
    return text


def clean_link_text_by_parts(label: str, url: str) -> str:
    label = re.sub(r'\n\s{0,4}', ' ', label)
    label = label.replace("\n", " ").replace("\r", "").replace("\\", "").strip()
    url = url.replace("\\(", "<<LP>>").replace("\\)", "<<RP>>")
    url = re.sub(r'%([0-9A-Fa-f]{1})\\\n\s{0,4}([0-9A-Fa-f]{1})', r'%\1\2', url)
    url = re.sub(r'\n\s{0,4}', ' ', url)
    url = url.replace("\\", "")
    url = url.replace("<<LP>>", "%28").replace("<<RP>>", "%29")
    url = urllib.parse.unquote(url)
    url = urllib.parse.quote(url, safe="/().,-_~%")
    return f"[{label}]({url})"


def find_and_replace_links(text: str) -> str:
    i = 0
    new_text = ""
    while i < len(text):
        if text[i] == "[":
            i += 1
            label = ""
            while i < len(text) and text[i] != "]":
                label += text[i]
                i += 1
            if i >= len(text) or i + 1 >= len(text) or text[i] != "]" or text[i + 1] != "(":
                new_text += "[" + label
                continue
            i += 2
            url = ""
            while i < len(text):
                url += text[i]
                if url.endswith(".md)"):
                    break
                i += 1
            if not url.endswith(".md)"):
                new_text += f"[{label}]({url}"
                break
            url = url[:-1]
            cleaned = clean_link_text_by_parts(label, url)
            new_text += cleaned
            i += 1
        else:
            new_text += text[i]
            i += 1
    return new_text


def strip_unbalanced_quotes(text: str) -> str:
    if text.count('"') % 2 != 0:
        if text.startswith('"') and not text.endswith('"'):
            return text[1:]
        elif not text.startswith('"') and text.endswith('"'):
            return text[:-1]
    return text


def split_links(text: str) -> list:
    link_pattern = r'(\[\[.*?\]\]|\[.*?\]\(.*?\.md\))'
    parts = re.split(link_pattern, text)
    parts = [p for p in parts if p.strip()]
    result = []
    for part in parts:
        if re.match(link_pattern, part):
            if not (part.startswith('"') and part.endswith('"')):
                part = f'"{part.strip()}"'
        else:
            part = strip_unbalanced_quotes(part.strip())
        result.append(part)
    return result


def encode_links(text: str) -> str:
    def repl(match):
        label, url = match.groups()
        encoded = encode_url(url)
        return f'[{label}]({encoded})'
    return re.sub(r'\[(.*?)\]\((.*?)\)', repl, text)


def process_block_lines(block_lines: list, key: str, original_op: str) -> list:
    result = [f"{key}:{' ' + original_op if original_op else ''}"]
    for line in block_lines:
        cleaned = encode_links(line.rstrip("\\").rstrip())
        links = split_links(cleaned)
        for part in links:
            part = clean_link_whitespace(part)
            result.append(f"  {part}")
    return result


def preprocess_yaml_content(content: str, log_fn=print) -> str:
    lines = content.splitlines()
    result = []
    inside_block = False
    block_lines = []
    block_key = ""
    original_op = ""
    if len(lines) > 0 and lines[0].strip() == "---":
        try:
            header_end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
            header_start = 0
        except StopIteration:
            log_fn("⚠️ YAML 區塊未正確關閉（找不到結尾 `---`），跳過此檔案")
            return content
    else:
        log_fn("⚠️ 無合法 YAML 區塊（第 0 行不是 `---`），跳過此檔案")
        return content


    pre_yaml = lines[:header_start + 1]
    yaml_lines = lines[header_start + 1:header_end]
    post_yaml = lines[header_end:]
    yaml_lines = find_and_replace_links("\n".join(yaml_lines)).splitlines()
    result.extend(pre_yaml)

    for i in range(len(yaml_lines)):
        line = yaml_lines[i]
        match = re.match(r'^([^:\s][^:]*)[:]\s*(\|\-|\>\-)?\s*$', line)
        if match:
            if inside_block:
                result.extend(process_block_lines(block_lines, block_key, original_op))
                block_lines = []
            block_key = match.group(1).strip()
            original_op = match.group(2) or ""
            inside_block = True
        elif inside_block:
            if re.match(r'^\s{2,}', line):
                block_lines.append(line.strip())
            else:
                result.extend(process_block_lines(block_lines, block_key, original_op))
                result.append(clean_link_whitespace(strip_unbalanced_quotes(line)))
                block_lines = []
                inside_block = False
        else:
            cleaned = clean_link_whitespace(strip_unbalanced_quotes(line))
            result.append(cleaned)

    if inside_block and block_lines:
        result.extend(process_block_lines(block_lines, block_key, original_op))

    result.extend(post_yaml)
    return "\n".join(result)


def clean_yaml_artifacts(vault_path, log_path=None, verbose=False):
    modified_files = []
    logs = []

    def log(msg):
        logs.append(msg)
        if verbose:
            print(msg)

    for root, _, files in os.walk(vault_path):
        for file in files:
            if not file.endswith(".md"):
                continue

            full_path = os.path.join(root, file)
            rel_path = Path(full_path).relative_to(vault_path)

            full_path = get_safe_path(full_path)

            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()

            cleaned = preprocess_yaml_content(content, log_fn=log)

            if cleaned.strip() != content.strip():
                log(f"📛 差異內容: {rel_path}")
                log(f"cleaned:\n{cleaned}")
                log("\nVS.\n")
                log(f"content:\n{content}")
                for i, (c1, c2) in enumerate(zip(cleaned, content)):
                    if c1 != c2:
                        log(f"  第 {i} 字元不同: '{c1}' vs '{c2}'")
                        break
                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(cleaned)
                modified_files.append(str(rel_path))
                log(f"🧼 cleaned: {rel_path}")
            else:
                log(f"☑️ no changes: {rel_path}")
    if verbose:
        log(f"\n📄 總共修改 {len(modified_files)} 個檔案。")

    if log_path:
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, "w", encoding="utf-8") as f:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"🧼 YAML Clean Log — {timestamp}\n\n")
            for msg in logs:
                f.write(f"{msg}\n")




if __name__ == "__main__":
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    VAULT_PATH = os.path.join(BASE_DIR, "TestData")
    LOG_PATH = os.path.join(BASE_DIR, "log", "yaml_preprocess.log")
    clean_yaml_artifacts(VAULT_PATH, log_path=LOG_PATH, verbose=True)
