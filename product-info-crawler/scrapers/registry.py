from importlib import import_module

from scrapers.base_scraper import BaseScraper


def _snake_to_camel(value: str) -> str:
    return "".join(part.capitalize() for part in value.split("_"))


def get_scraper_class(scraper_key: str) -> type[BaseScraper]:
    module_name = f"scrapers.{scraper_key}_scraper"
    class_name = f"{_snake_to_camel(scraper_key)}Scraper"

    try:
        module = import_module(module_name)
    except ImportError as exc:
        raise ImportError(f"스크래퍼 모듈을 찾지 못했습니다: {module_name}") from exc

    try:
        scraper_class = getattr(module, class_name)
    except AttributeError as exc:
        raise ImportError(f"스크래퍼 클래스를 찾지 못했습니다: {class_name}") from exc

    if not issubclass(scraper_class, BaseScraper):
        raise TypeError(f"{class_name}는 BaseScraper를 상속해야 합니다.")

    return scraper_class
