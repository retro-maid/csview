import os
import sys
import json

# PyInstaller 環境でもリソースパスを正しく取得する
def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        base_path = sys._MEIPASS  # PyInstallerが一時的に展開するフォルダ
    else:
        base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    return os.path.join(base_path, relative_path)

# バージョン情報の読み込み（resourcesから）
def load_app_info():
    try:
        version_path = resource_path("version.json")
        with open(version_path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        return {
            "version": "unknown",
            "copyright": "unknown",
            "release_date": "unknown",
            "description": "No version info available."
        }

# 起動時バージョン確認用の state ファイル
def get_state_file_path():
    return os.path.join(os.path.expanduser("~"), ".csview", "state.json")

def load_previous_version():
    try:
        with open(get_state_file_path(), encoding="utf-8") as f:
            return json.load(f).get("version")
    except Exception:
        return None

def save_current_version(version):
    os.makedirs(os.path.dirname(get_state_file_path()), exist_ok=True)
    with open(get_state_file_path(), "w", encoding="utf-8") as f:
        json.dump({"version": version}, f, indent=2)
