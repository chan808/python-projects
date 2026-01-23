from selenium import webdriver
from bs4 import BeautifulSoup
import time
import re
import urllib.parse
import json
from utils.helper import scroll_to_bottom, parse_price

class BaseScraper:
    def __init__(self, driver: webdriver.Chrome, config: dict):
        self.driver = driver
        self.config = config

    def parse_category(self, category_name: str, url: str):
        """사이트별 구현 필요"""
        raise NotImplementedError