import json
import os
from pathlib import Path

APP_NAME = "Rajhi Wages Manager"
APP_AR_NAME = "برنامج أجور الراجحي"
CONFIG_DIR = Path(os.getenv("APPDATA") or Path.home()) / "RajhiWagesManager"
CONFIG_FILE = CONFIG_DIR / "config.json"
DEFAULT_DB_NAME = "rajhi_wages_shared.db"

DEFAULT_SETTINGS = {
    "db_path": str(CONFIG_DIR / DEFAULT_DB_NAME),
    "establishment_name": "",
    "establishment_bank": "RJHI",
    "establishment_id": "",
    "establishment_account": "",
    "currency": "SAR",
    "mol_establishment_id": "",
    "payment_description": "Payroll",
    "beneficiary_bank_code": "RJHI",
    "last_export_folder": str(Path.home() / "Desktop"),
}

def ensure_config_dir():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def load_settings():
    ensure_config_dir()
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            merged = DEFAULT_SETTINGS.copy()
            merged.update(data)
            return merged
        except Exception:
            return DEFAULT_SETTINGS.copy()
    save_settings(DEFAULT_SETTINGS.copy())
    return DEFAULT_SETTINGS.copy()


def save_settings(settings):
    ensure_config_dir()
    CONFIG_FILE.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")
