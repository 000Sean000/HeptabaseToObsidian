import os

# 當前目錄即為 Vault 根目錄
vault_path = os.getcwd()

# 不合法尾部字元：空格、點、Zero-width space、No-break space
TRAILING_BAD_CHARS = ' .\u200B\u00A0'

# 記錄修改的檔案
renamed_files = []

for root, _, files in os.walk(vault_path):
    for filename in files:
        if filename.endswith('.md'):
            old_path = os.path.join(root, filename)
            cleaned_filename = filename.rstrip(TRAILING_BAD_CHARS)

            # 如果有變更，重新命名
            if cleaned_filename != filename:
                new_path = os.path.join(root, cleaned_filename)
                try:
                    os.rename(old_path, new_path)
                    renamed_files.append((filename, cleaned_filename))
                except Exception as e:
                    print(f"⚠️ 無法重新命名：{filename} → {cleaned_filename}\n{e}")

# 顯示結果
if renamed_files:
    print("\n✅ 檢查並清除了以下檔名尾部的隱藏字元：\n")
    for old, new in renamed_files:
        print(f"- {old}  →  {new}")
else:
    print("✅ 所有檔案都很乾淨，沒有尾部空白或隱形字元！")
