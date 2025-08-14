# src/unwrap_hard_wraps.py

import os
import re
from datetime import datetime
from utils.get_safe_path import get_safe_path
from utils.logger import Logger

# === 可調參數（單位：UTF-8 bytes） ===
MIN_WRAP_LEN = 80     # 視為「很長一行」的長度門檻（全英文約120字，全中文約40字）
TITLEISH_MAX = 64     # 視為「短標題」的長度上限（全英文約80字，全中文約26字）
SENTENCE_ENDERS = ("。", "！", "？", ".", "!", "?")

# === Markdown 模式 ===
MD_TABLE_LINE = re.compile(r'^\s*\|')   # 表格
HR_LINE = re.compile(r'^\s*(-{3,}|\*{3,}|_{3,})\s*$')
ATX_HEADING = re.compile(r'^\s{0,3}#{1,6}\s')
LIST_BULLET = re.compile(r'^\s{0,}[*\-+]\s+')
LIST_ORDERED = re.compile(r'^\s{0,}\d{1,3}[.)]\s+')
BLOCKQUOTE = re.compile(r'^\s{0,3}>\s?')
CODE_FENCE = re.compile(r'^\s{0,3}```')
HARD_BREAK = re.compile(r'(  |\s\\)$')  # 兩空白或反斜線結尾的強制換行
BQ_PREFIX = re.compile(r'^(\s{0,3}>\s?)')  # 抓 blockquote 前綴（支援最多3空白）

# 取得下一行第一個 token（整個 [[Wikilink]] 或英數詞）
NEXT_TOKEN_RE = re.compile(r'^\s*(\[\[[^\]]+\]\]|[A-Za-z0-9][A-Za-z0-9_\-]*)')

# 單行純 wikilink（可帶 alias）
_PURE_WIKILINK = re.compile(r'^\s*\[\[[^|\]]+(?:\|[^\]]+)?\]\]\s*$')

def is_pure_wikilink(s: str) -> bool:
    return bool(_PURE_WIKILINK.match(s.strip()))

def split_bq_prefix(line: str):
    """回傳 (prefix, payload)。若非 blockquote 則 prefix=""、payload=line"""
    m = BQ_PREFIX.match(line)
    if not m:
        return "", line
    return m.group(0), line[m.end():]

def find_yaml_block(lines):
    """回傳 (start, end) 或 (None, None)"""
    boundaries = [i for i, l in enumerate(lines[:20]) if l.strip() == "---"]
    if len(boundaries) >= 2 and boundaries[0] == 0:
        return boundaries[0], boundaries[1]
    return None, None

# === 工具函式 ===
def is_header_line(s: str) -> bool:
    return ATX_HEADING.match(s.lstrip()) is not None

def block_start_reason(s: str) -> str:
    t = s.lstrip()
    if t == "":
        return "blank"
    if ATX_HEADING.match(t):
        return "heading"
    if LIST_BULLET.match(t):
        return "list_bullet"
    if LIST_ORDERED.match(t):
        return "list_ordered"
    if BLOCKQUOTE.match(t):
        return "blockquote"
    if CODE_FENCE.match(t):
        return "code_fence"
    if MD_TABLE_LINE.match(t):
        return "table"
    if HR_LINE.match(t):
        return "hr"
    if t.startswith("<"):
        return "html"
    return ""

def is_block_starter(s: str) -> bool:
    return block_start_reason(s) != ""

def looks_titleish(s: str) -> bool:
    """短、像標題/名詞/連結的行：不當作續行來源"""
    txt = s.strip()
    if len(txt.encode("utf-8")) <= TITLEISH_MAX:
        # 純連結/粗體/名詞傾向
        if txt.endswith(("]]", ")")):
            return True
        if (txt.startswith("**") and txt.endswith("**")) or (txt.startswith("[[") and txt.endswith("]]")):
            return True
        # 只有一兩個詞的標題感
        if ":" not in txt and all(len(w) <= 20 for w in txt.replace("**", "").split()):
            return True
    return False

def ends_with_forced_break(prev_raw: str) -> bool:
    return HARD_BREAK.search(prev_raw.rstrip("\n")) is not None

def get_leading_indent(line: str, tab_size=4) -> int:
    n = 0
    for ch in line:
        if ch == " ":
            n += 1
        elif ch == "\t":
            n += tab_size
        else:
            break
    return n

def first_token_bytes(s: str) -> int:
    """
    取得下一行開頭第一個「詞」的 UTF-8 byte 長度：
    - [[...]] 視為一個詞
    - 否則取第一個英數詞（允許 -/_）
    取不到則回 0
    """
    m = NEXT_TOKEN_RE.match(s)
    if not m:
        return 0
    return len(m.group(1).encode("utf-8"))

# === 超保守的合併判斷 ===
def should_unwrap(
    prev_line: str,
    curr_line: str,
    *,
    prev_is_list: bool,
    next_indented_text: bool,
    same_bq_level: bool,
    log,
    rel: str,
    i: int
) -> bool:
    ps_raw = prev_line.rstrip("\n")
    cs_raw = curr_line.rstrip("\n")
    ps = ps_raw.strip()
    cs = cs_raw.strip()

    prev_indent = get_leading_indent(prev_line)
    curr_indent = get_leading_indent(curr_line)

    # 先看「下一行」是否為區塊起點（同層 blockquote 例外）
    nxt_r = block_start_reason(curr_line)
    if nxt_r and not same_bq_level:
        log(f"⛔ [{rel}] L{i}->{i+1} stop: nxt is block starter ({nxt_r})")
        return False

    prev_len_bytes = len(ps.encode("utf-8"))

    # 詳細決策 baseline
    base = f"🔎 [{rel}] L{i}->{i+1}: prev_bytes={prev_len_bytes}, prev_indent={prev_indent}, curr_indent={curr_indent}, same_bq={same_bq_level}"

    # 空行不合併
    if not cs:
        log(f"{base} | 🚫 SKIP — next is empty")
        return False

    # --- 清單續行的特例（要放早） ---
    # 但若「上一行像短標題/單一 wikilink」或「下一行是純 wikilink 整行」，則不要合併
    if prev_is_list and next_indented_text and not looks_titleish(ps) and not is_pure_wikilink(cs):
        log(f"{base} | ✅ MERGE — LIST-CONT: prev_is_list & next_indented_text")
        return True

    # 一般早退條件
    if is_header_line(ps):
        log(f"{base} | 🚫 SKIP — prev is heading")
        return False
    if is_block_starter(ps):
        log(f"{base} | 🚫 SKIP — prev is block starter")
        return False
    if looks_titleish(ps) and prev_len_bytes < MIN_WRAP_LEN:
        log(f"{base} | 🚫 SKIP — prev looks titleish/short")
        return False
    if ps.endswith(SENTENCE_ENDERS):
        log(f"{base} | 🚫 SKIP — prev ends with sentence ender")
        return False
    if ends_with_forced_break(prev_line):
        log(f"{base} | 🚫 SKIP — prev has HARD_BREAK")
        return False

    # —— 有效長度：模擬自動 word-wrap（把下一行第一個 token 也算進門檻）——
    eff_prev_len = prev_len_bytes
    if curr_indent >= prev_indent:  # 僅同層或更深縮排才可能是續句
        add = first_token_bytes(cs)
        if add > 0:
            eff_prev_len += add + 1  # +1 模擬 join 時會加上的空白

    # 合併條件
    if curr_indent == prev_indent and eff_prev_len >= MIN_WRAP_LEN:
        log(f"{base} | ✅ MERGE — same indent & effective prev len ({eff_prev_len} >= {MIN_WRAP_LEN})")
        return True

    if curr_indent > prev_indent and eff_prev_len >= MIN_WRAP_LEN:
        log(f"{base} | ✅ MERGE — next deeper indent & effective prev len ({eff_prev_len} >= {MIN_WRAP_LEN})")
        return True

    log(f"{base} | 🚫 SKIP — default (did not meet merge conditions)")
    return False

# === 主流程 ===
def unwrap_hard_wraps(vault_path, log_path=None, verbose=False):
    changed_files = 0
    changed_lines_total = 0

    logger = Logger(log_path=log_path, verbose=verbose, title="Unwrap Hard Wraps Log")
    log = logger.log
    log(f"🧵 Unwrap Hard Wraps Log — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    log(f"Params: MIN_WRAP_LEN={MIN_WRAP_LEN} bytes, TITLEISH_MAX={TITLEISH_MAX} bytes\n")

    for root, _, files in os.walk(vault_path):
        for file in files:
            if not file.endswith(".md"):
                continue

            fp = os.path.join(root, file)
            sfp = get_safe_path(fp)
            rel = os.path.relpath(fp, vault_path)

            try:
                with open(sfp, "r", encoding="utf-8") as f:
                    lines = f.readlines()
            except Exception as e:
                log(f"⚠️  無法讀取 {rel}: {e}")
                continue

            yaml_start, yaml_end = find_yaml_block(lines)
            in_fence = False
            out = []
            i = 0
            merged_count = 0

            def in_yaml(idx):
                return yaml_start is not None and yaml_start <= idx <= yaml_end

            while i < len(lines):
                line = lines[i]

                # YAML 區塊保留
                if in_yaml(i):
                    out.append(line)
                    i += 1
                    continue

                # fenced code 切換
                if CODE_FENCE.match(line):
                    in_fence = not in_fence
                    out.append(line)
                    i += 1
                    continue

                # 表格行保留（不跨行合併）
                if in_fence or MD_TABLE_LINE.match(line):
                    out.append(line)
                    i += 1
                    continue

                # 嘗試「連鎖合併」：以 curr 為基底一路吃能併的下一行
                curr = line
                j = i + 1

                while j < len(lines):
                    nxt = lines[j]

                    # 下一行若是 YAML/fence/表格，或我們目前在 fence 中，就停
                    if in_yaml(j) or in_fence or MD_TABLE_LINE.match(nxt):
                        reason = "yaml/fence/table boundary"
                        log(f"⛔ [{rel}] L{i}->{j} stop: {reason}")
                        break

                    # 允許在同層 blockquote 內合併：只要 prev/nxt 都是 blockquote 且前綴一致
                    curr_bq, curr_body = split_bq_prefix(curr)
                    nxt_bq, nxt_body = split_bq_prefix(nxt)
                    same_bq_level = (curr_bq != "" and curr_bq == nxt_bq)

                    # 計算清單續行旗標
                    prev_is_list = bool(LIST_BULLET.match(curr.lstrip()) or LIST_ORDERED.match(curr.lstrip()))
                    next_indented_text = bool(
                        (nxt.startswith("  ") or nxt.startswith("\t")) and
                        not (LIST_BULLET.match(nxt) or LIST_ORDERED.match(nxt) or BLOCKQUOTE.match(nxt) or CODE_FENCE.match(nxt) or ATX_HEADING.match(nxt))
                    )

                    # 判斷是否合併
                    if should_unwrap(
                        curr, nxt,
                        prev_is_list=prev_is_list,
                        next_indented_text=next_indented_text,
                        same_bq_level=same_bq_level,
                        log=log, rel=rel, i=j-1
                    ):
                        if same_bq_level:
                            # blockquote 內部合併：保留一個前綴，把內容接起來
                            merged = curr_bq + curr_body.rstrip("\n").rstrip() + " " + nxt_body.lstrip()
                        else:
                            merged = curr.rstrip("\n").rstrip() + " " + nxt.lstrip()
                        curr = merged
                        j += 1
                        merged_count += 1
                        continue
                    else:
                        break

                # 寫出本段（可能已合併多行）
                out.append(curr)
                i = j

            if out != lines:
                try:
                    with open(sfp, "w", encoding="utf-8") as f:
                        f.writelines(out)
                    changed_files += 1
                    changed_lines_total += merged_count
                    log(f"✅ {rel}：合併 {merged_count} 處硬斷行")
                except Exception as e:
                    log(f"⚠️  無法寫入 {rel}: {e}")
            else:
                log(f"☑️ {rel}：無需變更")

    log(f"\n📊 統計：修正 {changed_files} 份檔案，共合併 {changed_lines_total} 處硬斷行")
    logger.save()
    return changed_files, changed_lines_total


if __name__ == "__main__":
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    VAULT = os.path.join(BASE_DIR, "TestData")
    LOG = os.path.join(BASE_DIR, "log", "unwrap_hard_wraps.log")
    unwrap_hard_wraps(VAULT, log_path=LOG, verbose=True)
