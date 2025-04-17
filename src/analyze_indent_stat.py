
import os
from collections import Counter

def get_visual_indent(line, tab_size=3):
    """模擬方向鍵移動的視覺縮排量"""
    visual_pos = 0
    for char in line:
        if char == ' ':
            visual_pos += 1
        elif char == '\t':
            visual_pos += tab_size - (visual_pos % tab_size)
        else:
            break
    return visual_pos

def analyze_indent_diffs(folder_path, tab_size=3):
    indent_diffs = []

    for root, _, files in os.walk(folder_path):
        for file in files:
            if not file.endswith(".md"):
                continue

            full_path = os.path.join(root, file)
            with open(full_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            visual_indents = [get_visual_indent(line, tab_size) for line in lines if line.strip()]

            for i in range(1, len(visual_indents)):
                diff = visual_indents[i] - visual_indents[i - 1]
                if diff != 0:
                    indent_diffs.append(diff)

    return Counter(indent_diffs)

# === 🧪 測試用入口 ===
if __name__ == "__main__":
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    VAULT_PATH = os.path.join(BASE_DIR, "TestData")  # 你自己的資料夾

    result = analyze_indent_diffs(VAULT_PATH, tab_size=3)
    print("\n📊 縮排差異統計：")
    for diff, count in sorted(result.items()):
        print(f"{diff:+3d} → {count} 次")
