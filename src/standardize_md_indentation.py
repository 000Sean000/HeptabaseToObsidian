# src/standardize_md_indentation.py

import os
import json
from datetime import datetime
from utils.get_safe_path import get_safe_path
from utils.logger import Logger


def get_leading_indent(line: str, tab_size=4) -> int:
    count = 0
    for c in line:
        if c == ' ':
            count += 1
        elif c == '\t':
            count += tab_size
        else:
            break
    return count


def find_yaml_block(lines):
    yaml_boundaries = [i for i, l in enumerate(lines[:20]) if l.strip() == "---"]
    if len(yaml_boundaries) >= 2 and yaml_boundaries[0] == 0:
        return yaml_boundaries[0], yaml_boundaries[1]
    return None, None


def standardize_md_indentation(
    vault_path,
    log_path=None,
    verbose=False,
    spaces_per_indent=4,
    indent_unit_map_path=None,
    fallback_unit=4,
):
    changed_files = []

    indent_unit_map = {}
    if indent_unit_map_path and os.path.exists(indent_unit_map_path):
        with open(get_safe_path(indent_unit_map_path), "r", encoding="utf-8") as f:
            indent_unit_map = json.load(f)

    logger = Logger(log_path=log_path, verbose=verbose, title="Indent Fix Log")
    log = logger.log
    
    if log_path:
        with open(get_safe_path(log_path), "w", encoding="utf-8") as f:
            f.write(f"\U0001f9f9 Indentation Fix Log — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

    for root, _, files in os.walk(vault_path):
        for file in files:
            if not file.endswith(".md"):
                continue

            file_path = os.path.join(root, file)
            safe_file_path = get_safe_path(file_path)
            rel_path = os.path.relpath(file_path, vault_path)

            indent_unit = indent_unit_map.get(rel_path, fallback_unit)

            with open(safe_file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            yaml_start, yaml_end = find_yaml_block(lines)
            new_lines = []
            changed = False

            for i, line in enumerate(lines):
                if yaml_start is not None and yaml_start <= i <= yaml_end:
                    new_lines.append(line)
                    continue

                raw_line = line
                space_indent = get_leading_indent(line, tab_size=indent_unit)
                indent_level = space_indent // indent_unit
                stripped = line.lstrip().rstrip('\n')
                if stripped.endswith('\\'):
                    stripped = stripped[:-1].rstrip()
                rebuilt_line = ' ' * (spaces_per_indent * indent_level) + stripped + '\n'

                if rebuilt_line != raw_line:
                    changed = True
                new_lines.append(rebuilt_line)

            if changed:
                with open(safe_file_path, "w", encoding="utf-8") as f:
                    f.writelines(new_lines)
                changed_files.append(rel_path)
                log(f"✅ {rel_path}：已統一縮排（依空格單位={indent_unit} 推算層級 → 每層轉為 {spaces_per_indent} space）")
            else:
                log(f"☑️ {rel_path}：縮排正常（依空格單位={indent_unit} 推算層級 → 每層為 {spaces_per_indent} space）")

    if changed_files:
        log(f"\n🎉 共修正 {len(changed_files)} 個檔案的縮排")
    else:
        log("✅ 所有檔案縮排皆已一致")

    logger.save()
    
    return changed_files
