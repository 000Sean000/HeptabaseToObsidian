import os
import json
import urllib.parse
import re

vault_path = os.getcwd()
rename_map = {}

# --- PHASE 1: Rename all .md files with invalid trailing characters ---
def safe_rename_all_md_files():
    def safe_new_path(directory, clean_name):
        base, ext = os.path.splitext(clean_name)
        count = 1
        candidate = clean_name
        while os.path.exists(os.path.join(directory, candidate)):
            candidate = f"{base} ({count}){ext}"
            count += 1
        return os.path.join(directory, candidate)

    for root, _, files in os.walk(vault_path):
        for file in files:
            if file.endswith(".md"):
                original_path = os.path.join(root, file)
                clean_name = file.rstrip(" .\u200B\u00A0")
                if clean_name != file:
                    clean_path = safe_new_path(root, clean_name)
                    os.rename(original_path, clean_path)
                    relative_original = os.path.relpath(original_path, vault_path)
                    relative_new = os.path.relpath(clean_path, vault_path)
                    rename_map[relative_original] = relative_new

# --- PHASE 2: Save rename map for reference ---
def save_rename_map():
    with open(os.path.join(vault_path, "rename_map.json"), "w", encoding="utf-8") as f:
        json.dump(rename_map, f, indent=2, ensure_ascii=False)

# --- PHASE 3: Convert markdown links using rename map ---
def convert_links_using_map():
    pattern = re.compile(r'(?<!\!)\[(.+?)\.md\]\((.+?\.md)\)')

    def replace(match):
        label = match.group(1).strip()
        raw_path = match.group(2).strip()
        decoded_path = urllib.parse.unquote(raw_path)
        rel_path = os.path.normpath(decoded_path)
        for orig, new in rename_map.items():
            if os.path.normpath(orig) == rel_path:
                rel_path = new  # Use updated path from rename_map
                break
        name_without_ext = os.path.splitext(os.path.basename(rel_path))[0]
        return f"[[{name_without_ext}]]"

    changed_files = []

    for root, _, files in os.walk(vault_path):
        for file in files:
            if file.endswith(".md"):
                path = os.path.join(root, file)
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
                new_content = pattern.sub(replace, content)
                if new_content != content:
                    with open(path, 'w', encoding='utf-8') as f:
                        f.write(new_content)
                    changed_files.append(os.path.relpath(path, vault_path))

    return changed_files

# --- EXECUTION ---
print("🔍 Phase 1: Renaming .md files...")
safe_rename_all_md_files()
save_rename_map()
print(f"✅ Renamed {len(rename_map)} file(s). Saved map as rename_map.json.")

print("\n🔁 Phase 2: Converting markdown links to wiki links...")
converted = convert_links_using_map()

if converted:
    print("\n✅ Converted markdown links in the following file(s):")
    for f in converted:
        print("  -", f)
else:
    print("✅ No markdown links found or updated.")
