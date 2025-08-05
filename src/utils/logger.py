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


    def log(self, msg):
        self.log_lines.append(msg)
        if self.verbose:
            print(msg)

    def save(self):
        if self.log_path:
            os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
            with open(self.log_path, "w", encoding="utf-8") as f:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                f.write(f"{self.title} — {timestamp}\n\n")
                f.write("\n".join(self.log_lines))

