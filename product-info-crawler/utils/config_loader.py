import json
from dataclasses import dataclass
from pathlib import Path


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class BrandConfigSummary:
    brand_id: str
    display_name: str
    scraper_key: str
    config_path: Path


REQUIRED_TOP_LEVEL_KEYS = ("brand", "google_sheets", "selectors", "categories")
REQUIRED_BRAND_KEYS = ("id", "display_name", "scraper")
REQUIRED_GOOGLE_SHEETS_KEYS = ("service_account_file", "spreadsheet_name")
REQUIRED_SELECTOR_KEYS = ("product_card", "name", "price", "link")


def _validate_required_keys(section: dict, required_keys: tuple[str, ...], section_name: str) -> None:
    missing_keys = [key for key in required_keys if not section.get(key)]
    if missing_keys:
        missing = ", ".join(missing_keys)
        raise ConfigError(f"{section_name} 필수 키가 비어 있습니다: {missing}")


def load_brand_config(config_path: Path, project_root: Path, validate_credentials: bool = False) -> dict:
    if not config_path.exists():
        raise ConfigError(f"설정 파일이 없습니다: {config_path.name}")

    try:
        with config_path.open("r", encoding="utf-8") as file:
            config = json.load(file)
    except json.JSONDecodeError as exc:
        raise ConfigError(f"JSON 형식이 잘못되었습니다: {exc}") from exc

    if not isinstance(config, dict):
        raise ConfigError("설정 파일의 최상위 값은 객체여야 합니다.")

    _validate_required_keys(config, REQUIRED_TOP_LEVEL_KEYS, "config")

    brand_config = config["brand"]
    google_sheets_config = config["google_sheets"]
    selectors = config["selectors"]
    categories = config["categories"]

    if not isinstance(brand_config, dict):
        raise ConfigError("brand는 객체여야 합니다.")
    if not isinstance(google_sheets_config, dict):
        raise ConfigError("google_sheets는 객체여야 합니다.")
    if not isinstance(selectors, dict):
        raise ConfigError("selectors는 객체여야 합니다.")
    if not isinstance(categories, dict) or not categories:
        raise ConfigError("categories에는 최소 1개 이상의 카테고리 URL이 필요합니다.")

    _validate_required_keys(brand_config, REQUIRED_BRAND_KEYS, "brand")
    _validate_required_keys(google_sheets_config, REQUIRED_GOOGLE_SHEETS_KEYS, "google_sheets")
    _validate_required_keys(selectors, REQUIRED_SELECTOR_KEYS, "selectors")

    service_account_path = Path(google_sheets_config["service_account_file"])
    if not service_account_path.is_absolute():
        service_account_path = project_root / service_account_path

    if validate_credentials and not service_account_path.exists():
        raise ConfigError(
            f"서비스 계정 키 파일이 없습니다: {service_account_path.relative_to(project_root)}"
        )

    for category_name, url in categories.items():
        if not isinstance(url, str) or not url.strip():
            raise ConfigError(f"categories.{category_name} URL이 비어 있습니다.")

    config["google_sheets"]["service_account_file"] = str(service_account_path)
    return config


def discover_brand_configs(config_dir: Path, project_root: Path) -> list[BrandConfigSummary]:
    if not config_dir.exists():
        raise ConfigError(f"config 디렉터리가 없습니다: {config_dir}")

    brand_summaries: list[BrandConfigSummary] = []
    seen_brand_ids: set[str] = set()

    for config_path in sorted(config_dir.glob("*.json")):
        config = load_brand_config(config_path, project_root)
        brand = config["brand"]
        brand_id = brand["id"]

        if brand_id in seen_brand_ids:
            raise ConfigError(f"중복된 brand.id가 있습니다: {brand_id}")

        seen_brand_ids.add(brand_id)
        brand_summaries.append(
            BrandConfigSummary(
                brand_id=brand_id,
                display_name=brand["display_name"],
                scraper_key=brand["scraper"],
                config_path=config_path,
            )
        )

    if not brand_summaries:
        raise ConfigError("config 디렉터리에 브랜드 설정 파일이 없습니다.")

    return brand_summaries
