from typing import Optional

from selenium import webdriver


class BaseScraper:
    requires_driver = True

    def __init__(self, driver: Optional[webdriver.Chrome], config: dict):
        self.driver = driver
        self.config = config

    def parse_category(self, category_name: str, url: str):
        raise NotImplementedError
