import os

vault_path = os.getcwd()
empty_files = []

for root, _, files in os.walk(vault_path):
    for f in files:
        if f.endswith('.md'):
            full_path = os.path.join(root, f)
            if os.path.getsize(full_path) == 0:
                empty_files.append(full_path)

print("\n🕵️ 以下是內容為空的 .md 檔案：\n")
for f in empty_files:
    print("  -", f)
