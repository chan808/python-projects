"""Crawler registry – single place to discover available brand crawlers."""

from __future__ import annotations

from typing import Dict, List, Type

from core.crawler.base import BaseCrawler


class CrawlerRegistry:
    """Simple registry that maps brand names → crawler classes.

    Brand crawlers register themselves by importing this module and calling
    ``CrawlerRegistry.register(MyCrawler)``.
    """

    _registry: Dict[str, Type[BaseCrawler]] = {}

    @classmethod
    def register(cls, crawler_class: Type[BaseCrawler]) -> Type[BaseCrawler]:
        """Register a crawler class. Can also be used as a decorator."""
        instance = crawler_class()
        cls._registry[instance.brand_name.lower()] = crawler_class
        return crawler_class

    @classmethod
    def get(cls, brand_name: str) -> Type[BaseCrawler]:
        key = brand_name.lower()
        if key not in cls._registry:
            raise KeyError(f"No crawler registered for brand '{brand_name}'")
        return cls._registry[key]

    @classmethod
    def available_brands(cls) -> List[str]:
        return sorted(cls._registry.keys())

    @classmethod
    def _ensure_loaded(cls) -> None:
        """Import all crawler modules so they self-register."""
        if cls._registry:
            return
        # Import brand modules – each module calls register() at import time.
        import core.crawler.celine           # noqa: F401
        import core.crawler.dior             # noqa: F401
        import core.crawler.bottega_veneta   # noqa: F401
        # Kering Group
        import core.crawler.gucci            # noqa: F401
        import core.crawler.saint_laurent    # noqa: F401
        import core.crawler.balenciaga       # noqa: F401
        import core.crawler.boucheron        # noqa: F401
        # LVMH Group
        import core.crawler.fendi            # noqa: F401
        import core.crawler.berluti          # noqa: F401
        import core.crawler.loro_piana       # noqa: F401
        import core.crawler.chaumet          # noqa: F401
        import core.crawler.bulgari          # noqa: F401
        # Prada Group
        import core.crawler.prada            # noqa: F401
        import core.crawler.miu_miu          # noqa: F401
        # Richemont Group
        import core.crawler.cartier          # noqa: F401
        # Independent Brands
        import core.crawler.damiani          # noqa: F401
        import core.crawler.burberry         # noqa: F401
