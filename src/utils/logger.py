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

"""
## ✅ 各模組用法

### 1. 初始化

```python
from utils.logger import Logger

logger = Logger(log_path="log/xyz.log", verbose=True, title="🧼 YAML Clean Log")
log = logger.log
```

### 2. 用 `log(...)` 和原本一樣記錄訊息

```python
log("開始處理 markdown...")
log(f"✅ {rel_path} 處理完成")
```

### 3. 程式結尾記得 `.save()`

```python
logger.save()
```

"""