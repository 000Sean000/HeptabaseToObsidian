# src/utils/logger.py
import os
from datetime import datetime
from utils.get_safe_path import get_safe_path


class Logger:
    def __init__(self, log_path=None, verbose=False, title=None):
        self.verbose = verbose
        self.log_path = get_safe_path(log_path) if log_path else None
        self.log_lines = []
        self.title = title or "📘 Log"
        self._line_buffer = ""  # ← 新增：用來支援 end=""

    def log(self, msg, end="\n"):
        """
        行為類似 print：支援 end 參數（預設換行）。
        - end == "": 先把文字累積在 _line_buffer，不立即寫入一行
        - 其他：把累積 + 這次訊息組成一行，寫入 log_lines
        """
        if end == "":
            self._line_buffer += str(msg)
            if self.verbose:
                print(msg, end="")
            return

        # end 不是空字串：把累積的內容 + 本次訊息收斂成一行
        line = f"{self._line_buffer}{msg}"
        self.log_lines.append(line)
        if self.verbose:
            print(line)
        self._line_buffer = ""

    def save(self):
        # 如果最後還有殘留的行緩衝，補進去
        if self._line_buffer:
            self.log_lines.append(self._line_buffer)
            self._line_buffer = ""

        if self.log_path:
            os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
            with open(self.log_path, "w", encoding="utf-8") as f:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                f.write(f"{self.title} — {timestamp}\n\n")
                f.write("\n".join(self.log_lines))

    def info(self):
        self.log(f"self.log_path: {self.log_path}")
