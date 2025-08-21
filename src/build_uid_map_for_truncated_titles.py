# src/build_uid_map_for_truncated_titles.py

from __future__ import annotations

import os
import re
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Tuple, List, Iterable, Optional

from utils.get_safe_path import get_safe_path
from utils.logger import Logger


# ===== Constants =====
LONG_FILENAME_UTF8_BYTES_THRESHOLD = 70  # 目前檔名約能使用97Byte，不排除有容量更小、提前截斷的情況，所以可能要設得比97小一些


# ===== Data Models =====
from dataclasses import dataclass
from typing import Dict, Optional

@dataclass
class TruncationMapEntry:
    """truncation_map 的 value 結構：{ uid, full_sentence }"""
    uid: str
    full_sentence: str

    # 方便 I/O 的小工具（可選）
    @staticmethod
    def from_dict(d: dict) -> "TruncationMapEntry":
        return TruncationMapEntry(uid=d["uid"], full_sentence=d["full_sentence"])

    def to_dict(self) -> dict:
        return {"uid": self.uid, "full_sentence": self.full_sentence}


@dataclass
class Indices:
    """規格：高層流程 Step1 所需的三個索引（皆為必備）"""
    full_to_uid: Dict[str, str]
    uid_to_expected_full: Dict[str, str]
    uid_to_key: Dict[str, str]

    # 查詢輔助（讀操作）
    def uid_for_full(self, full_sentence: str) -> Optional[str]:
        return self.full_to_uid.get(full_sentence)

    def key_for_uid(self, uid: str) -> Optional[str]:
        return self.uid_to_key.get(uid)

    def expected_full_for_uid(self, uid: str) -> Optional[str]:
        return self.uid_to_expected_full.get(uid)

    def has_uid(self, uid: str) -> bool:
        return uid in self.uid_to_expected_full

    def has_full(self, full_sentence: str) -> bool:
        return full_sentence in self.full_to_uid

    # 新增 map 條目時，保持三索引同步（寫操作）
    def register(self, key: str, entry: TruncationMapEntry) -> None:
        self.full_to_uid[entry.full_sentence] = entry.uid
        self.uid_to_expected_full[entry.uid] = entry.full_sentence
        self.uid_to_key[entry.uid] = key

    # 變更 full_sentence（例如 F2 序號化）時，安全更新索引
    def update_full_for_uid(self, uid: str, old_full: str, new_full: str) -> None:
        if self.full_to_uid.get(old_full) == uid:
            self.full_to_uid.pop(old_full, None)
        self.full_to_uid[new_full] = uid
        self.uid_to_expected_full[uid] = new_full
        # uid_to_key 不變（key 仍是被截斷的不完整語句）


@dataclass
class Stats:
    """規格：📊Log 與統計 所列計數器"""
    new_uid_assigned: int = 0
    supplemental_entries_added: int = 0   # 補登錄／新增 map 條目數
    renames_to_uid: int = 0               # 正名數（一般/Temp → uid）
    duplicates_deleted: int = 0           # F1 完全重複刪除
    conflicts_serialized: int = 0         # 同首句不同內容 → 已序號化處理
    temps_repaired: int = 0               # temp → 正式 uid
    orphan_targets_seen: int = 0          # map 遺失實體偵測
    # 其他可擴充欄位…

    # 微工具：累加器，避免各處手動 +1
    def inc_new_uid(self): self.new_uid_assigned += 1
    def inc_added(self): self.supplemental_entries_added += 1
    def inc_renamed(self): self.renames_to_uid += 1
    def inc_deleted_dup(self): self.duplicates_deleted += 1
    def inc_serialized(self): self.conflicts_serialized += 1
    def inc_repaired_temp(self): self.temps_repaired += 1
    def inc_orphan(self): self.orphan_targets_seen += 1



# ===== I/O & Map =====
def load_truncation_map(map_path: str) -> Dict[str, TruncationMapEntry]:
    """讀取 truncation_map.json → 以 key(str)→TruncationMapEntry 回傳。
    規格：map 由他程保養；若遇不一致，本程式不覆寫、不挪用，僅記錄 audit。
    """
    p = get_safe_path(map_path)
    if not os.path.exists(p):
        return {}
    try:
        with open(p, "r", encoding="utf-8") as f:
            raw = json.load(f)
        result: Dict[str, TruncationMapEntry] = {}
        for k, v in raw.items():
            # 容錯：v 可能是 dict 或已是正確結構
            uid = v["uid"] if isinstance(v, dict) else getattr(v, "uid")
            fs = v["full_sentence"] if isinstance(v, dict) else getattr(v, "full_sentence")
            result[k] = TruncationMapEntry(uid=uid, full_sentence=fs)
        return result
    except Exception:
        # 讀取失敗 → 回傳空 map（外部程式保養 map；這裡不嘗試修復）
        return {}


def save_truncation_map(map_path: str, truncation_map: Dict[str, TruncationMapEntry]) -> None:
    """安全寫回 truncation_map.json（確保資料夾存在、UTF-8）。
    """
    p = get_safe_path(map_path)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    serializable = {k: {"uid": v.uid, "full_sentence": v.full_sentence} for k, v in truncation_map.items()}
    with open(p, "w", encoding="utf-8") as f:
        json.dump(serializable, f, ensure_ascii=False, indent=2)


def build_indices_from_map(truncation_map: Dict[str, TruncationMapEntry]) -> Indices:
    """由 map 建立 full_to_uid / uid_to_expected_full / uid_to_key 三索引。"""
    full_to_uid: Dict[str, str] = {}
    uid_to_expected_full: Dict[str, str] = {}
    uid_to_key: Dict[str, str] = {}
    for k, entry in truncation_map.items():
        full_to_uid[entry.full_sentence] = entry.uid
        uid_to_expected_full[entry.uid] = entry.full_sentence
        uid_to_key[entry.uid] = k
    return Indices(full_to_uid=full_to_uid, uid_to_expected_full=uid_to_expected_full, uid_to_key=uid_to_key)


# ===== File Scanning =====
def iter_vault_md_files(vault_path: str) -> Iterable[Path]:
    """遍歷整個 Vault（全域）找出所有 .md 檔（含 uid / 非 uid / temp），yield 絕對路徑 Path。"""
    vp = os.path.abspath(vault_path)
    for root, _, files in os.walk(vp):
        for fn in files:
            if fn.lower().endswith(".md"):
                yield Path(get_safe_path(os.path.join(root, fn)))


def read_lines(path: Path) -> List[str]:
    """讀取單檔所有行（保留換行符）。"""
    with open(get_safe_path(str(path)), "r", encoding="utf-8", errors="ignore") as f:
        return f.readlines()


# ===== Markdown Cleaning =====
def skip_yaml(lines: List[str]) -> List[str]:
    """規格 1：跳過 YAML 區塊（首行/次行皆以單獨 '---' 為邊界，含邊界）。"""
    if not lines:
        return lines
    i = 0
    # 僅當第一行是 '---' 時才視為 YAML 開頭
    if lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                return lines[i + 1 :]
        # 沒有收尾，保守起見：視為沒 YAML
        return lines
    return lines


def first_nonempty_line(lines: List[str]) -> str:
    """規格 1：取第一個非空行（可能是 list/blockquote 起頭）。"""
    for ln in lines:
        if ln.strip():
            return ln
    return ""


def clean_markdown_line(line: str) -> str:
    """規格 1：清理 Markdown（僅限）
    - 行首清單符號：- * +
    - 行首有序清單：<數字> 或 <數字>. 後接空白
    - 標題起頭：一個或多個 # 後接空白
    - 區塊引用：一個或多個 > 後接空白
    - 行內樣式：**粗體**、*斜體*（不跨越 ** 的情形）、`行內程式碼`
    - Wikilink 去殼：
        [[page|alias]] → alias
        [[uid|@full_sentence]] → 去 @ 的 alias
        [[page]] → page
    - 尾碼日期等：去除「結尾的 空白 + 純數字」尾碼（僅純數字）
    - 去前後空白
    冪等：不移除 '(n)' 序號化尾綴。
    """
    s = line.lstrip()
    s = re.sub(r"^[-+*]\s+", "", s)               # 無序清單
    s = re.sub(r"^\d+\.?\s*", "", s)              # 有序清單
    s = re.sub(r"^#+\s*", "", s)                  # 標題
    s = re.sub(r"^>+\s*", "", s)                  # 區塊引用
    s = re.sub(r"\*\*(.*?)\*\*", r"\1", s)        # 粗體
    s = re.sub(r"(?<!\*)\*(?!\*)([^*]+)\*(?!\*)", r"\1", s)  # 斜體（不跨 **）
    s = re.sub(r"`([^`]+)`", r"\1", s)            # 行內程式碼

    # Wikilink：[[page|alias]] / [[uid|@full_sentence]] / [[page]]
    def _wikilink_repl(m: re.Match) -> str:
        page = m.group(1)
        alias = m.group(2)
        if alias is not None:
            alias = alias.lstrip("@")
            return alias
        return page

    s = re.sub(r"\[\[([^\|\]]+)(?:\|([^\]]+))?\]\]", _wikilink_repl, s)

    # 去除尾端「空白 + 純數字」尾碼（不會移除 '(n)'）
    s = re.sub(r"\s*\d+$", "", s).strip()
    return s


# ===== Filename vs First Sentence (Semantic Truncation) =====
def remove_trailing_number(text: str) -> str:
    """規格 2：檔名預處理：移除尾端『空白 + 純數字』。"""
    return re.sub(r"\s*\d+$", "", text.strip())


def compare_filename_and_line(filename: str, cleaned: str) -> Tuple[bool, str]:
    """規格 2：語意斷句判定（逐字比、有效字元集合、噪聲互相抵銷）
    回傳：(是否符合語意斷句, 理由)
    """
    def _is_valid_char(c: str) -> bool:
        return c.isalnum() or c in " -_()[]"

    fn = remove_trailing_number(filename)
    i, j = 0, 0
    while i < len(fn) and j < len(cleaned):
        c1, c2 = fn[i], cleaned[j]
        if c1 == c2:
            i += 1; j += 1
        elif not _is_valid_char(c1) or not _is_valid_char(c2):
            i += 1; j += 1  # 噪聲互相抵銷
        else:
            return False, f"❌ 字元不符：'{c1}' ≠ '{c2}' 位置 {i}"
    if i < len(fn):
        return False, f"❌ 檔名未完全匹配：僅比對至 {i}/{len(fn)}"
    remaining = cleaned[j:].strip()
    if remaining == "" or re.fullmatch(r"\d+", remaining):
        return False, "❌ 剩餘內容僅為數字或空白"
    return True, "✔️ 首句包含額外語意，構成語意斷句"


def is_truncated(filename_clean: str, full_sentence: str, threshold: int = LONG_FILENAME_UTF8_BYTES_THRESHOLD) -> Tuple[bool, str]:
    """規格 3：被截斷判定（終止符 / 長度門檻 + 補述）。"""
    tail = full_sentence[len(filename_clean):].strip() if len(full_sentence) >= len(filename_clean) else ""
    filename_byte_length = len(filename_clean.encode("utf-8"))
    if tail in {".", "?", "!"}:
        return True, f"✔️ 補述為符號：'{tail}' → 認定為截斷"
    if filename_byte_length >= threshold and tail:
        return True, f"✔️ 檔名長且有補述（{filename_byte_length} bytes）→ 認定為截斷"
    return False, f"❌ 檔名長度 {filename_byte_length} bytes，補述非關鍵 → 非截斷"


# ===== Key Generation (for uid_XXX not in map / must include) =====
def synthesize_truncation_key_from_cleaned(cleaned: str, threshold: int = LONG_FILENAME_UTF8_BYTES_THRESHOLD) -> str:
    """規格 6：以 cleaned 反推『標準截斷 key』
    1) 終止符截斷（去掉尾端單一 . ? !）
    2) 位元組門檻截斷（≤ threshold，去尾空白/純數字；需在 UTF-8 字元邊界）
    3) 強制截斷（移除最後一個語詞；再不行則移除最後一字元）
    """
    s = cleaned.strip()
    # 1) 終止符
    if s and s[-1] in ".?!":
        return s[:-1].rstrip()
    # 2) 位元組門檻
    b = 0
    out_chars: List[str] = []
    for ch in s:
        ch_b = len(ch.encode("utf-8"))
        if b + ch_b > threshold:
            break
        out_chars.append(ch)
        b += ch_b
    base = "".join(out_chars).rstrip()
    base = re.sub(r"\s*\d+$", "", base).strip()
    # 3) 強制截斷
    if not base or base.isdigit():
        base = s
    if base == s:
        # 移除最後一個語詞
        t = re.sub(r"\s*\S+\s*$", "", s).rstrip()
        base = t if t else (s[:-1] if len(s) > 0 else s)
    return base


def uniquify_key(base_key: str, truncation_map: Dict[str, TruncationMapEntry]) -> str:
    """規格 6-4：僅針對 key 自身做單層 '(n)' 遞增，直到唯一。"""
    if base_key not in truncation_map:
        return base_key
    pat = re.compile(rf"^{re.escape(base_key)}\s*\((\d+)\)$")
    used = {base_key}
    for k in truncation_map.keys():
        m = pat.match(k)
        if m:
            used.add(k)
    n = 2
    while True:
        cand = f"{base_key} ({n})"
        if cand not in used and cand not in truncation_map:
            return cand
        n += 1


# ===== F1 / F2 / F3 =====
def files_are_fully_identical(path_a: Path, path_b: Path) -> bool:
    """F1：完全重複判定（先比 cleaned，再比整檔逐字，含 YAML）。"""
    # 首句 cleaned 比對
    ln_a = first_nonempty_line(skip_yaml(read_lines(path_a)))
    ln_b = first_nonempty_line(skip_yaml(read_lines(path_b)))
    if clean_markdown_line(ln_a) != clean_markdown_line(ln_b):
        return False
    # 整檔逐字
    with open(get_safe_path(str(path_a)), "r", encoding="utf-8", errors="ignore") as fa, \
         open(get_safe_path(str(path_b)), "r", encoding="utf-8", errors="ignore") as fb:
        return fa.read() == fb.read()


def serialize_full_sentence(sentence: str, existing_full_values: Iterable[str]) -> str:
    """F2：生成唯一化的 full_sentence 'S (n)'。不含 I/O。"""
    s = sentence
    existing = set(existing_full_values)
    if s not in existing:
        return s
    n = 2
    while True:
        cand = f"{s} ({n})"
        if cand not in existing:
            return cand
        n += 1


def apply_serialized_suffix_to_file_headline(path: Path, new_sentence: str) -> None:
    """F2：把 '(n)' 同步寫回檔案首句（唯一允許的內容變更）。"""
    p = get_safe_path(str(path))
    lines = read_lines(path)
    # 找 YAML 結束
    start_idx = 0
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                start_idx = i + 1
                break
    # 找第一個非空行
    idx = None
    for i in range(start_idx, len(lines)):
        if lines[i].strip():
            idx = i
            break
    if idx is None:
        # 空檔：直接插入一行
        lines.append(new_sentence + "\n")
    else:
        lines[idx] = new_sentence + "\n"
    with open(p, "w", encoding="utf-8") as f:
        f.writelines(lines)


def get_unused_uid(vault_path: str, start_index: int) -> Tuple[str, int]:
    """F3：新 UID 指派。需同時檢查 map 與整個 Vault 檔名，保證全域唯一。"""
    idx = max(1, int(start_index))
    while True:
        uid = f"uid_{idx:03d}"
        target = f"{uid}.md"
        found = False
        for root, _, files in os.walk(os.path.abspath(vault_path)):
            if target in files:
                found = True
                break
        if not found:
            return uid, idx + 1
        idx += 1


# ===== Rename / Temp Utilities =====
def ensure_global_unique_rename(src: Path, dest: Path) -> None:
    """安全正名（必要時先把占用者移 temp 或用中繼名再換名，避免覆寫）。"""
    src_p = Path(get_safe_path(str(src)))
    dest_p = Path(get_safe_path(str(dest)))
    os.makedirs(os.path.dirname(str(dest_p)), exist_ok=True)
    if dest_p.exists():
        move_to_temp_name(dest_p)  # 先把占用者讓位
    os.rename(str(src_p), str(dest_p))


def move_to_temp_name(path: Path) -> Path:
    """將檔名換成 uid_fix_temp(n).md（n=1,2,3… 唯一）。"""
    parent = Path(str(path)).parent
    n = 1
    while True:
        cand = parent / f"uid_fix_temp({n}).md"
        cand_p = Path(get_safe_path(str(cand)))
        if not cand_p.exists():
            os.rename(get_safe_path(str(path)), str(cand_p))
            return cand_p
        n += 1


def uid_for_path(path: Path) -> Optional[str]:
    """若檔名為 uid_XXX.md 回傳 uid_XXX，否則 None。"""
    name = path.name
    m = re.fullmatch(r"(uid_\d{3,})\.md", name)
    return m.group(1) if m else None


def is_temp_file(path: Path) -> bool:
    """判斷是否 uid_fix_temp(n).md。"""
    return re.fullmatch(r"uid_fix_temp\(\d+\)\.md", path.name) is not None


# ===== Case Dispatchers (all orchestrators only) =====
def handle_uid_named_file(
    path: Path,
    cleaned: str,
    truncation_map: Dict[str, TruncationMapEntry],
    indices: Indices,
    stats: Stats,
    logger: Logger,
) -> None:
    """Case A：檔名為 uid_XXX.md。
    → 直接進入『共用邏輯』；如需，依規格先搬移占用者、正名、或序號化＋新 UID。
    """
    common_logic_with_cleaned(
        path=path,
        cleaned=cleaned,
        from_uid_named=True,
        truncation_map=truncation_map,
        indices=indices,
        stats=stats,
        logger=logger,
    )


def handle_general_named_file(
    path: Path,
    base_filename: str,
    cleaned: str,
    truncation_map: Dict[str, TruncationMapEntry],
    indices: Indices,
    stats: Stats,
    logger: Logger,
) -> None:
    """Case B：一般檔名（非 uid 開頭）。
    1) 語意斷句 compare_filename_and_line
    2) 被截斷 is_truncated
    3) 若皆為是 → 進入『共用邏輯』；需要時先轉為 uid_XXX.md。
    """
    ok, reason = compare_filename_and_line(base_filename, cleaned)
    if not ok:
        log_event(logger, action="skip-nonsegbreak", src=path, detail=reason)
        return

    filename_clean = remove_trailing_number(base_filename)
    truncated, reason_trunc = is_truncated(filename_clean, cleaned, LONG_FILENAME_UTF8_BYTES_THRESHOLD)
    log_event(logger, action="truncation-check", src=path, detail=reason_trunc)
    if not truncated:
        return

    # 進入共用邏輯（來路為一般檔名）
    common_logic_with_cleaned(
        path=path,
        cleaned=cleaned,
        from_uid_named=False,
        truncation_map=truncation_map,
        indices=indices,
        stats=stats,
        logger=logger,
    )


def handle_temp_file(
    path: Path,
    cleaned: str,
    truncation_map: Dict[str, TruncationMapEntry],
    indices: Indices,
    stats: Stats,
    logger: Logger,
) -> None:
    """Case C：uid_fix_temp(n).md → 依規格轉正（或刪除冗餘）。
    完成轉正後不長留 temp（正名後自然消失）。
    """
    expected_uid = indices.uid_for_full(cleaned)
    parent = path.parent

    if expected_uid:
        expected_path = parent / f"{expected_uid}.md"
        if expected_path.exists():
            # 首句一致？→ F1
            ln_expected = first_nonempty_line(skip_yaml(read_lines(expected_path)))
            if clean_markdown_line(ln_expected) == cleaned:
                if files_are_fully_identical(path, expected_path):
                    # 冗餘暫存 → 刪除
                    os.remove(get_safe_path(str(path)))
                    stats.inc_deleted_dup()
                    log_event(logger, action="delete-duplicate-temp", src=path, dst=expected_path)
                    return
                else:
                    # 同首句不同內容 → F2 + F3 新 UID，改名、新增條目；key 以 expected 的 key 為 base 遞增
                    new_full = serialize_full_sentence(cleaned, indices.full_to_uid.keys())
                    if new_full != cleaned:
                        apply_serialized_suffix_to_file_headline(path, new_full)
                    # 以 map（全域）與當前資料夾確保唯一 UID
                    used = set(indices.uid_to_expected_full.keys())
                    n = 1
                    while True:
                        cand = f"uid_{n:03d}"
                        if cand not in used and not (parent / f"{cand}.md").exists():
                            new_uid = cand
                            break
                        n += 1
                    # 改名
                    dest = parent / f"{new_uid}.md"
                    ensure_global_unique_rename(path, dest)
                    # key 基於 expected 的既有 key 遞增
                    base_key = indices.key_for_uid(expected_uid) or synthesize_truncation_key_from_cleaned(cleaned)
                    key = uniquify_key(base_key, truncation_map)
                    add_map_entry(truncation_map, key, new_uid, new_full, indices)
                    stats.inc_serialized(); stats.inc_new_uid(); stats.inc_renamed(); stats.inc_added()
                    log_event(logger, action="temp-serialize-newuid", src=path, dst=dest, detail=f"key={key}")
                    return
            else:
                # 首句不同：此 temp 與 expected 無關 → 視為新內容（F2 視需求）+ 新 UID
                pass  # 落到下面「expected_uid 不存在或不適用」的路徑

        # expected_uid.md 不存在（map 遺失實體）→ 不得直接占用該 uid；視為新增內容
        stats.inc_orphan()
        # F2（必要）+ F3
        new_full = serialize_full_sentence(cleaned, indices.full_to_uid.keys())
        if new_full != cleaned:
            apply_serialized_suffix_to_file_headline(path, new_full)

        used = set(indices.uid_to_expected_full.keys())
        n = 1
        while True:
            cand = f"uid_{n:03d}"
            if cand not in used and not (parent / f"{cand}.md").exists():
                new_uid = cand
                break
            n += 1
        dest = parent / f"{new_uid}.md"
        ensure_global_unique_rename(path, dest)
        base_key = indices.key_for_uid(expected_uid) or synthesize_truncation_key_from_cleaned(cleaned)
        key = uniquify_key(base_key, truncation_map)
        add_map_entry(truncation_map, key, new_uid, new_full, indices)
        stats.inc_new_uid(); stats.inc_renamed(); stats.inc_added()
        log_event(logger, action="temp-newuid-orphan-map", src=path, dst=dest, detail=f"key={key}")
        return

    # cleaned 不在 map → 新內容：F2（如需）＋ F3
    new_full = cleaned  # 若 map 無此句，通常不需序號化
    if new_full in indices.full_to_uid:
        new_full = serialize_full_sentence(new_full, indices.full_to_uid.keys())
        if new_full != cleaned:
            apply_serialized_suffix_to_file_headline(path, new_full)

    used = set(indices.uid_to_expected_full.keys())
    n = 1
    while True:
        cand = f"uid_{n:03d}"
        if cand not in used and not (parent / f"{cand}.md").exists():
            new_uid = cand
            break
        n += 1
    dest = parent / f"{new_uid}.md"
    ensure_global_unique_rename(path, dest)

    base_key = synthesize_truncation_key_from_cleaned(new_full)
    key = uniquify_key(base_key, truncation_map)
    add_map_entry(truncation_map, key, new_uid, new_full, indices)
    stats.inc_new_uid(); stats.inc_renamed(); stats.inc_added()
    log_event(logger, action="temp-newuid-fresh", src=path, dst=dest, detail=f"key={key}")


# ===== Shared Logic (cleaned in map? ) =====
def common_logic_with_cleaned(
    path: Path,
    cleaned: str,
    from_uid_named: bool,
    truncation_map: Dict[str, TruncationMapEntry],
    indices: Indices,
    stats: Stats,
    logger: Logger,
) -> None:
    """共用邏輯（規格：以 cleaned 是否在 map 分流；a) 來自 uid 檔；b) 來自非 uid 檔）
    (1) cleaned 已在 map → expected_uid 分支（F1 / 轉 temp / 正名）
    (2) cleaned 不在 map → 新內容：
        - 來路 b) 非 uid 檔 → F3 新 UID → 改檔名 → key=原始被截斷檔名(預處理後) → 新增條目
        - 來路 a) uid 檔 → 依『以 uid 收錄時 key 規則』合成 key → 必收錄 or 衝突改 temp 後 Case C
    """
    parent = path.parent
    expected_uid = indices.uid_for_full(cleaned)

    # (1) cleaned 已在 map
    if expected_uid:
        expected_path = parent / f"{expected_uid}.md"

        if from_uid_named:
            current_uid = uid_for_path(path)
            if current_uid == expected_uid:
                # 一致 → 無動作
                log_event(logger, action="noop-consistent", src=path)
                return

        if expected_path.exists():
            # 比對首句
            ln_expected = first_nonempty_line(skip_yaml(read_lines(expected_path)))
            if clean_markdown_line(ln_expected) == cleaned:
                # F1：完全重複？
                if files_are_fully_identical(path, expected_path):
                    # 冗餘 → 刪除當前檔案
                    os.remove(get_safe_path(str(path)))
                    stats.inc_deleted_dup()
                    log_event(logger, action="delete-duplicate", src=path, dst=expected_path)
                    return
                else:
                    # 兩者共存 → 對「當前檔案」序號化 + 新 UID + 新條目；key 以 expected 的 key 為 base 遞增
                    new_full = serialize_full_sentence(cleaned, indices.full_to_uid.keys())
                    if new_full != cleaned:
                        apply_serialized_suffix_to_file_headline(path, new_full)
                    # 指派新 UID（以 map + 當前資料夾檢查）
                    used = set(indices.uid_to_expected_full.keys())
                    n = 1
                    while True:
                        cand = f"uid_{n:03d}"
                        if cand not in used and not (parent / f"{cand}.md").exists():
                            new_uid = cand
                            break
                        n += 1
                    dest = parent / f"{new_uid}.md"
                    ensure_global_unique_rename(path, dest)

                    base_key = indices.key_for_uid(expected_uid) or synthesize_truncation_key_from_cleaned(cleaned)
                    key = uniquify_key(base_key, truncation_map)
                    add_map_entry(truncation_map, key, new_uid, new_full, indices)
                    stats.inc_serialized(); stats.inc_new_uid(); stats.inc_renamed(); stats.inc_added()
                    log_event(logger, action="serialize-newuid", src=path, dst=dest, detail=f"key={key}")
                    return
            else:
                # 首句不同 → 占用者需要更正檔名：先把占用者移 temp，再把當前檔案正名為 expected_uid.md
                moved = move_to_temp_name(expected_path)
                log_event(logger, action="preempt-occupier-to-temp", src=expected_path, dst=moved)
                dest = parent / f"{expected_uid}.md"
                ensure_global_unique_rename(path, dest)
                stats.inc_renamed()
                log_event(logger, action="rename-to-expected-uid", src=path, dst=dest)
                return
        else:
            # 無人占用 → 直接正名為 expected_uid.md（不改內容）
            dest = parent / f"{expected_uid}.md"
            ensure_global_unique_rename(path, dest)
            stats.inc_renamed()
            log_event(logger, action="rename-to-expected-uid", src=path, dst=dest)
            return

    # (2) cleaned 不在 map → 新內容
    if from_uid_named:
        # 來路 a) uid 檔：必收錄或衝突轉 temp（由 Case C 後續處理）
        current_uid = uid_for_path(path)
        if current_uid and not indices.has_uid(current_uid):
            # 必收錄：以 cleaned 反推標準 key → 唯一化 → 新增條目
            base_key = synthesize_truncation_key_from_cleaned(cleaned)
            key = uniquify_key(base_key, truncation_map)
            add_map_entry(truncation_map, key, current_uid, cleaned, indices)
            stats.inc_added()
            log_event(logger, action="register-uid-file", src=path, detail=f"key={key}")
        else:
            # UID 衝突（map 已使用此 UID）→ 改名為 temp，留待 Case C
            moved = move_to_temp_name(path)
            log_event(logger, action="uid-conflict-move-temp", src=path, dst=moved)
        return

    # 來路 b) 非 uid 檔：F3 新 UID → 改檔名 → key=原始被截斷檔名(預處理後) → 新增條目
    used = set(indices.uid_to_expected_full.keys())
    n = 1
    while True:
        cand = f"uid_{n:03d}"
        if cand not in used and not (parent / f"{cand}.md").exists():
            new_uid = cand
            break
        n += 1

    dest = parent / f"{new_uid}.md"
    ensure_global_unique_rename(path, dest)

    base_key = remove_trailing_number(path.stem)  # 檔名預處理後作為 key base
    key = uniquify_key(base_key, truncation_map)
    add_map_entry(truncation_map, key, new_uid, cleaned, indices)
    stats.inc_new_uid(); stats.inc_renamed(); stats.inc_added()
    log_event(logger, action="general-newuid", src=path, dst=dest, detail=f"key={key}")



# ===== Map Mutations =====
def add_map_entry(
    truncation_map: Dict[str, TruncationMapEntry],
    key: str,
    uid: str,
    full_sentence: str,
    indices: Indices,
) -> None:
    """新增 map 條目（三重唯一：key/uid/full_sentence）。同步刷新 indices。"""
    # 三重唯一性檢查（不覆寫、不挪用）
    if key in truncation_map:
        raise ValueError(f"map key already exists: {key}")
    if uid in indices.uid_to_expected_full:
        raise ValueError(f"uid already exists in map: {uid}")
    if full_sentence in indices.full_to_uid:
        raise ValueError(f"full_sentence already exists in map: {full_sentence}")

    entry = TruncationMapEntry(uid=uid, full_sentence=full_sentence)
    truncation_map[key] = entry
    # 保持三索引同步
    indices.register(key, entry)


# ===== Logging =====
def log_params(logger: Logger) -> None:
    """在 log 開頭列印主要參數（如 bytes 門檻等）。"""
    logger.log("=== build_uid_map_for_truncated_titles: run params ===")
    logger.log(f"- LONG_FILENAME_UTF8_BYTES_THRESHOLD = {LONG_FILENAME_UTF8_BYTES_THRESHOLD}")
    logger.log("=====================================================")


def log_event(
    logger: Logger, *, action: str, src: Optional[Path] = None, dst: Optional[Path] = None, detail: str = ""
) -> None:
    """統一事件記錄：rename/delete/serialize/audit 等，需包含來源與目的相對路徑。"""
    parts = [f"[{action}]"]
    if src is not None:
        parts.append(f"src={src}")
    if dst is not None:
        parts.append(f"dst={dst}")
    if detail:
        parts.append(f"info={detail}")
    logger.log(" ".join(parts))

def log_stats_summary(
    logger: Logger,
    stats: Stats,
    truncation_map: Dict[str, TruncationMapEntry],
    *,
    map_count_before: Optional[int] = None,
) -> None:
    """在 log 結尾輸出統計總表（含 map 規模變化）。"""
    after = len(truncation_map)
    delta = None if map_count_before is None else (after - map_count_before)

    logger.log("")  # 空行分隔
    logger.log("📊 Summary (this run)")
    if map_count_before is not None:
        logger.log(f"  - map_entries_before: {map_count_before}")
        logger.log(f"  - map_entries_after : {after}")
        logger.log(f"  - map_entries_delta : {delta:+d}")
    else:
        logger.log(f"  - map_entries_after : {after}")

    logger.log("  - new_uid_assigned          : {}".format(stats.new_uid_assigned))
    logger.log("  - supplemental_entries_added: {}".format(stats.supplemental_entries_added))
    logger.log("  - renames_to_uid            : {}".format(stats.renames_to_uid))
    logger.log("  - duplicates_deleted        : {}".format(stats.duplicates_deleted))
    logger.log("  - conflicts_serialized      : {}".format(stats.conflicts_serialized))
    logger.log("  - temps_repaired            : {}".format(stats.temps_repaired))
    logger.log("  - orphan_targets_seen       : {}".format(stats.orphan_targets_seen))


# ===== Orchestrator =====
def build_uid_map_for_truncated_titles(
    vault_path: str, map_path: str, log_path: str, verbose: bool = False
) -> Dict[str, TruncationMapEntry]:
    """
    主流程（僅呼叫，無實作邏輯）：
    1) 建 logger、列印參數
    2) 讀 map → 建索引
    3) 第一輪遍歷（Case A/B）：
       - 跳過 temp
       - 讀檔、skip_yaml、取第一行、clean
       - 依檔名類型分派：uid / 一般
    4) 重建索引（第一輪已改 map/檔名）
    5) 第二輪遍歷（Case C）：只處理 temp
    6) 儲存 map、寫 log、輸出統計
    """
    logger = Logger(log_path=log_path, verbose=verbose, title=None)
    log_params(logger)

    truncation_map = load_truncation_map(get_safe_path(map_path))
    map_count_before = len(truncation_map) 
    indices = build_indices_from_map(truncation_map)
    stats = Stats()

    # ---------- Pass 1: Case A / B ----------
    for path in iter_vault_md_files(vault_path):
        if is_temp_file(path):
            continue  # 第一輪跳過 Case C

        lines = read_lines(path)
        content_lines = skip_yaml(lines)
        line = first_nonempty_line(content_lines)
        cleaned = clean_markdown_line(line)
        base_filename = path.stem

        if (uid := uid_for_path(path)) is not None:
            handle_uid_named_file(path, cleaned, truncation_map, indices, stats, logger)     # Case A
        else:
            handle_general_named_file(path, base_filename, cleaned, truncation_map, indices, stats, logger)  # Case B

    # （可選）Checkpoint：第一輪後先存一次，便於復原／審計
    # save_truncation_map(get_safe_path(map_path), truncation_map)
    # logger.save()

    # 重要：第一輪可能改了 map/檔名，第二輪前重建索引
    indices = build_indices_from_map(truncation_map)

    # ---------- Pass 2: Case C ----------
    for path in iter_vault_md_files(vault_path):
        if not is_temp_file(path):
            continue  # 只處理 temp

        lines = read_lines(path)
        content_lines = skip_yaml(lines)
        line = first_nonempty_line(content_lines)
        cleaned = clean_markdown_line(line)

        handle_temp_file(path, cleaned, truncation_map, indices, stats, logger)  # Case C

    log_stats_summary(logger, stats, truncation_map, map_count_before=map_count_before)
    save_truncation_map(get_safe_path(map_path), truncation_map)
    logger.save()
    return truncation_map



# ===== CLI Entrypoint =====
if __name__ == "__main__":
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    VAULT_DIR = os.path.join(BASE_DIR, "TestData")
    MAP_PATH = os.path.join(BASE_DIR, "log", "truncation_map.json")
    LOG_PATH = os.path.join(BASE_DIR, "log", "truncation_detect.log")

    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    # 只示意呼叫，不做任何實作
    build_uid_map_for_truncated_titles(VAULT_DIR, MAP_PATH, LOG_PATH, verbose=True)
