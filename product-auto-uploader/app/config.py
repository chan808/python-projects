from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union

from app.models import AppConfig, BrowserConfig, MustitConfig, RuntimePaths

APP_NAME = "ProductAutoUploader"
PROJECT_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_BROWSER_CONFIG = {
    "headless": False,
    "slow_mo_ms": 250,
    "navigation_timeout_ms": 15000,
    "action_timeout_ms": 10000,
}


def load_config() -> AppConfig:
    user_settings = load_user_settings()
    settings_dir, runtime_root, config_path = get_app_directories()

    paths_raw = user_settings.get("paths", {})
    browser_raw = user_settings.get("browser", {})
    mustit_raw = user_settings.get("mustit", {})

    browser_defaults = copy.deepcopy(DEFAULT_BROWSER_CONFIG)
    browser_defaults.update(browser_raw)

    paths = RuntimePaths(
        project_root=PROJECT_ROOT,
        settings_dir=settings_dir,
        runtime_root=runtime_root,
        user_config_path=config_path,
        register_pic_root=_resolve_path(
            paths_raw.get("register_pic_root") or str(_default_register_pic_root()),
            base_dir=settings_dir,
        ),
        logs_dir=runtime_root / "logs",
        screenshots_dir=runtime_root / "screenshots",
        output_dir=runtime_root / "output",
    )

    browser = BrowserConfig(
        headless=_read_bool(os.getenv("PAU_BROWSER_HEADLESS"), browser_defaults.get("headless", False)),
        slow_mo_ms=int(os.getenv("PAU_BROWSER_SLOW_MO_MS", browser_defaults.get("slow_mo_ms", 250))),
        navigation_timeout_ms=int(browser_defaults.get("navigation_timeout_ms", 15000)),
        action_timeout_ms=int(browser_defaults.get("action_timeout_ms", 10000)),
        user_data_dir=runtime_root / "playwright-profile",
    )

    mustit = MustitConfig(
        register_url=str(mustit_raw.get("register_url", "")).strip(),
        login_check_selector=str(mustit_raw.get("login_check_selector", "")).strip(),
        allow_manual_login=bool(mustit_raw.get("allow_manual_login", True)),
        manual_login_timeout_ms=int(mustit_raw.get("manual_login_timeout_ms", 300000)),
        selectors_path=_resolve_path(
            mustit_raw.get("selectors_path") or "./selectors/mustit.json",
            base_dir=PROJECT_ROOT,
        ),
    )

    config = AppConfig(
        paths=paths,
        browser=browser,
        mustit=mustit,
        brand_aliases={str(key).lower(): str(value) for key, value in user_settings.get("brand_aliases", {}).items()},
        last_product=user_settings.get("ui", {}).get("last_product", {}),
    )
    ensure_runtime_dirs(config)
    return config


def load_user_settings() -> Dict[str, Any]:
    settings_dir, _, config_path = get_app_directories()
    settings_dir.mkdir(parents=True, exist_ok=True)

    defaults = _build_default_user_settings()
    if not config_path.exists():
        save_user_settings(defaults)
        return defaults

    current = _read_json(config_path)
    merged = _deep_merge(defaults, current)
    if merged != current:
        save_user_settings(merged)
    return merged


def save_user_settings(user_settings: Dict[str, Any]) -> Path:
    settings_dir, _, config_path = get_app_directories()
    settings_dir.mkdir(parents=True, exist_ok=True)
    normalized = _deep_merge(_build_default_user_settings(), user_settings)
    config_path.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")
    return config_path


def save_last_product(product_payload: Dict[str, Any]) -> Path:
    settings = load_user_settings()
    settings.setdefault("ui", {})
    settings["ui"]["last_product"] = product_payload
    return save_user_settings(settings)


def get_app_directories() -> Tuple[Path, Path, Path]:
    appdata_root = Path(os.getenv("APPDATA", Path.home() / "AppData" / "Roaming"))
    localappdata_root = Path(os.getenv("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    settings_dir = appdata_root / APP_NAME
    runtime_root = localappdata_root / APP_NAME
    config_path = settings_dir / "user-config.json"
    return settings_dir, runtime_root, config_path


def ensure_runtime_dirs(config: AppConfig) -> None:
    config.paths.settings_dir.mkdir(parents=True, exist_ok=True)
    config.paths.runtime_root.mkdir(parents=True, exist_ok=True)
    config.paths.logs_dir.mkdir(parents=True, exist_ok=True)
    config.paths.screenshots_dir.mkdir(parents=True, exist_ok=True)
    config.paths.output_dir.mkdir(parents=True, exist_ok=True)
    config.browser.user_data_dir.mkdir(parents=True, exist_ok=True)


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_path(value: Union[str, Path], base_dir: Optional[Path] = None) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    root = base_dir or PROJECT_ROOT
    return (root / path).resolve()


def _read_bool(env_value: Optional[str], default: bool) -> bool:
    if env_value is None:
        return bool(default)
    return env_value.strip().lower() in {"1", "true", "yes", "on"}


def _build_default_user_settings() -> Dict[str, Any]:
    return {
        "paths": {
            "register_pic_root": str(_default_register_pic_root()),
        },
        "browser": copy.deepcopy(DEFAULT_BROWSER_CONFIG),
        "mustit": {
            "register_url": "",
            "login_check_selector": "",
            "allow_manual_login": True,
            "manual_login_timeout_ms": 300000,
            "selectors_path": "./selectors/mustit.json",
        },
        "brand_aliases": {},
        "ui": {
            "last_product": {
                "category": "",
                "brand_name": "",
                "product_code": "",
                "product_name": "",
                "price": "",
                "submit_mode": "preview",
            }
        },
    }


def _default_register_pic_root() -> Path:
    return Path.home() / "Desktop" / "registerPic"


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged
