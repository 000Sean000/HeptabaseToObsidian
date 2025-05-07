from urllib.parse import quote


def clean_link_text_by_parts(label: str, url: str) -> str:
    print("Label: " + label)
    print("Url: " + url)
    print("Url string: ", [url])

    # 1. 轉移合法 escape
    url = url.replace("\\(", "<<LP>>").replace("\\)", "<<RP>>")
    print("Url with Placeholder: " + url)
    # 2. 移除非法符號
    url = url.replace("\\", "").replace("\n", "").replace("\r", "")

    # 3. 還原合法括號，並做 URL encode
    url = url.replace("<<LP>>", "%28").replace("<<RP>>", "%29")

    print("result: ", [f"[{label}]({quote(url, safe='/().,-_~')})"])
    print("Cleaned URL (repr):", repr(url))

    return f"[{label}]({quote(url, safe='/().,-_~')})"


def find_and_replace_links(text: str) -> str:
    """
    逐字掃描處理 markdown link，支援跨行、清除非法符號。
    """
    i = 0
    new_text = ""
    while i < len(text):
        if text[i] == "[":
            label_start = i
            i += 1
            label = ""
            while i < len(text) and text[i] != "]":
                label += text[i]
                i += 1

            if i >= len(text) or text[i] != "]" or i + 1 >= len(text) or text[i + 1] != "(":
                new_text += "[" + label  # 不是連結，還原
                continue

            i += 2  # skip "]("
            url = ""
            while i < len(text):
                url += text[i]
                if url.endswith(".md)"):
                    break
                i += 1

            if not url.endswith(".md)"):
                new_text += "[" + label + "](" + url
                break

            url = url[:-1]  # remove the closing ")"
            cleaned = clean_link_text_by_parts(label, url)
            new_text += cleaned
            i += 1  # skip final ")"

        else:
            new_text += text[i]
            i += 1
    return new_text

sample_text = '''
Auras: "[Coldbloodedly Scheming (心機冷血的) — Calm-Ego Common
  Form                           Ruthlessly
  Eccent.md](./Coldbloodedly%20Scheming%20\\(心機冷血的\\)%20—%20Calm-Ego%20Common%2\\
  0Form%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20\\
  %20%20%20Ruthlessly%20Eccent.md)"
'''

print([find_and_replace_links(sample_text)])
