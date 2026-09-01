import os
import sys
from pathlib import Path


def get_base_dir():
    configured = os.environ.get("BILJART_DATA_DIR")
    if configured:
        return os.path.abspath(configured)

    # In packaged mode use the executable directory, in source mode use project root.
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))

    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def get_user_data_dir():
    configured = os.environ.get("BILJART_USER_HOME_DIR")
    if configured:
        return os.path.abspath(configured)

    return os.path.join(str(Path.home()), "BiljartClup")


BASE_DIR = get_base_dir()
USER_DATA_DIR = get_user_data_dir()
INSTANCE_DIR = os.path.join(BASE_DIR, "instance")
DB_PATH = os.path.join(INSTANCE_DIR, "biljart.db")
BACKUP_DIR = os.path.join(USER_DATA_DIR, "Backups")
REPORT_DIR = os.path.join(USER_DATA_DIR, "Rapporten")

os.makedirs(INSTANCE_DIR, exist_ok=True)
os.makedirs(BACKUP_DIR, exist_ok=True)
os.makedirs(REPORT_DIR, exist_ok=True)
