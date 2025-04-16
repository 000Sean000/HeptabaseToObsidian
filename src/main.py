import os

# 基本路徑設定
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
VAULT_DIR = os.path.join(BASE_DIR, "TestData")
LOG_DIR = os.path.join(BASE_DIR, "log")

# 確保 log 資料夾存在
os.makedirs(LOG_DIR, exist_ok=True)
