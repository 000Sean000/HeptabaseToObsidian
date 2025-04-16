import os

# 基本路徑設定
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
VAULT_DIR = os.path.join(BASE_DIR, "TestData")
LOG_DIR = os.path.join(BASE_DIR, "log")

# 確保 log 資料夾存在
os.makedirs(LOG_DIR, exist_ok=True)

from detect_invalid_md_filenames import detect_invalid_md_filenames

log_path = os.path.join(LOG_DIR, "invalid_filenames.log")
detect_invalid_md_filenames(VAULT_DIR, log_path=log_path, verbose=True)

from rename_md_files_safely import rename_md_files_safely

rename_log = os.path.join(LOG_DIR, "rename_phase.log")
rename_map_file = os.path.join(LOG_DIR, "rename_map.json")

rename_md_files_safely(VAULT_DIR, map_path=rename_map_file, log_path=rename_log, verbose=True)

from convert_links_to_wikilinks import convert_links_to_wikilinks

link_log = os.path.join(LOG_DIR, "link_conversion.log")
rename_map_file = os.path.join(LOG_DIR, "rename_map.json")

convert_links_to_wikilinks(
    vault_path=VAULT_DIR,
    rename_map_path=rename_map_file,
    log_path=link_log,
    verbose=True
)

from fix_relative_web_links import fix_relative_web_links

fix_relative_web_links(
    vault_path=VAULT_DIR,
    log_path=os.path.join(LOG_DIR, "web_link_fix.log"),
    verbose=True
)

