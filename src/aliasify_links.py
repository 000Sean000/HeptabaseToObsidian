import os
import re
import yaml
from datetime import datetime

def extract_clean_first_line(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    for line in lines:
        clean = re.sub(r'[#>\-\*\+`\[\]_*~]', '', line).strip()
        if clean:
            return clean
    return None

def get_existing_alias(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    if lines and lines[0].strip() == "---":
        end_idx = next((i for i, l in enumerate(lines[1:], 1) if l.strip() == "---"), -1)
        if end_idx != -1:
            yaml_block = yaml.safe_load("".join(lines[1:end_idx])) or {}
            aliases = yaml_block.get("aliases", [])
            if isinstance(aliases, str):
                return [aliases]
            return aliases
    return []

def inject_alias(file_path, new_alias):
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    if lines and lines[0].strip() == "---":
        end_idx = next((i for i, l in enumerate(lines[1:], 1) if l.strip() == "---"), -1)
        if end_idx != -1:
            yaml_block = yaml.safe_load("".join(lines[1:end_idx])) or {}
            aliases = yaml_block.get("aliases", [])
            if isinstance(aliases, str):
                aliases = [aliases]
            if new_alias not in aliases:
                aliases.append(new_alias)
                yaml_block["aliases"] = aliases
                updated_yaml = yaml.dump(yaml_block, allow_unicode=True, sort_keys=False)
                new_lines = ["---\n"] + updated_yaml.splitlines(keepends=True) + ["---\n"] + lines[end_idx+1:]
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.writelines(new_lines)
    else:
        yaml_block = {"aliases": [new_alias]}
        updated_yaml = yaml.dump(yaml_block, allow_unicode=True, sort_keys=False)
        new_lines = ["---\n"] + updated_yaml.splitlines(keepends=True) + ["---\n"] + lines
        with open(file_path, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)

def aliasify_all_links(vault_path, log_file="aliasify_links.log"):
    wiki_link_pattern = re.compile(r'\[\[([^\[\]]+?)\]\]')
    alias_map = {}
    log_path = os.path.join(vault_path, log_file)
    with open(log_path, "w", encoding="utf-8") as log:
        log.write(f"📌 Aliasify Log — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        for root, _, files in os.walk(vault_path):
            for file in files:
                if file.endswith(".md"):
                    file_path = os.path.join(root, file)
                    rel_path = os.path.relpath(file_path, vault_path)
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    links = wiki_link_pattern.findall(content)
                    if not links:
                        continue
                    changed = False
                    for link in set(links):
                        target_file = os.path.join(vault_path, link + ".md")
                        if not os.path.exists(target_file):
                            continue
                        if link in alias_map:
                            alias = alias_map[link]
                        else:
                            aliases = get_existing_alias(target_file)
                            if aliases:
                                alias = aliases[0]
                            else:
                                alias = extract_clean_first_line(target_file)
                                if alias:
                                    inject_alias(target_file, alias)
                            alias_map[link] = alias
                        if alias and link != alias:
                            content = re.sub(rf'\[\[{re.escape(link)}\]\]', f'[[{alias}]]', content)
                            changed = True
                            log.write(f"🔁 {rel_path}: [[{link}]] → [[{alias}]]\n")
                    if changed:
                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.write(content)
        log.write("\n✅ 完成所有連結轉換與 alias 注入。\n")
    return log_path

if __name__ == "__main__":
    vault_dir = os.getcwd()
    aliasify_all_links(vault_dir)
