
# src/utils.py

import os

def get_safe_path(path: str) -> str:
    """針對 Windows 自動加上長路徑前綴，避免超過 MAX_PATH 錯誤"""
    if os.name == "nt":
        abs_path = os.path.abspath(path)
        if not abs_path.startswith(r"\\?\\"):
            return r"\\?\\" + abs_path
        return abs_path
    return path

"""
#### 2. **在需要處理路徑的模組中引用**：

```python
from utils import get_safe_path
```

---

#### 3. **在所有涉及檔案的操作前套用它**：

你只要在開檔、讀寫、移動、判斷存在等動作前都加這一行即可：

```python
file_path = get_safe_path(file_path)
```

---

### 🚨 哪些常見操作都該使用 `get_safe_path()`？

| 操作                 | 套用範例                                                |
| ------------------ | --------------------------------------------------- |
| `open()`           | `open(get_safe_path(path), ...)`                    |
| `os.path.exists()` | `os.path.exists(get_safe_path(path))`               |
| `os.rename()`      | `os.rename(get_safe_path(src), get_safe_path(dst))` |
| `os.remove()`      | `os.remove(get_safe_path(path))`                    |
| `Path().open()`    | `Path(get_safe_path(path)).open()`                  |


✅ 總結原則：

|路徑類型|需要 get_safe_path？|原因            |
|-------|------|------------------------------|
|絕對路徑|✅ 是|Windows 的長路徑限制針對絕對路徑|
|相對路徑|❌ 否|加工後反而變成非法路徑|



"""
