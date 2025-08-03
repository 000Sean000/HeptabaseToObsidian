## ✅ 各模組用法

### 1. 初始化

```python
from utils.logger import Logger

logger = Logger(log_path="log/xyz.log", verbose=True, title="🧼 YAML Clean Log")
log = logger.log
```

```python
from utils.logger import Logger
```

```python
logger = Logger(log_path=log_path, verbose=verbose, title=None)
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
