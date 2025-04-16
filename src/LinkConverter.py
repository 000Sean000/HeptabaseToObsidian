import os
import re

vault_path = os.getcwd()
changed_files = []

# 最穩 regex：匹配 [label.md](link.md)，只轉換這種
pattern = re.compile(r'(?<!\!)\[(.+?)\.md\]\((.+?\.md)\)')

def convert_links(content):
    def replace(match):
        label = match.group(1).strip()
        return f"[[{label}]]"
    return pattern.sub(replace, content)

# 遍歷所有 markdown 檔案
for root, _, files in os.walk(vault_path):
    for file in files:
        if file.endswith(".md"):
            path = os.path.join(root, file)
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            new_content = convert_links(content)
            if new_content != content:
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                changed_files.append(path)

# 回報
if changed_files:
    print("\n✅ 成功！以下檔案中 [xxx.md](yyy.md) 已轉為 [[xxx]]：\n")
    for f in changed_files:
        print("  -", f)
else:
    print("✅ 沒有符合的連結，一切已經是 wiki link！")
