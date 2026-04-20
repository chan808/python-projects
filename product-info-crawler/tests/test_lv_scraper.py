import unittest

from scrapers.lv_scraper import LvScraper


class LvScraperTest(unittest.TestCase):
    def test_extract_products_from_json_ld(self) -> None:
        scraper = LvScraper(None, {"scraping_settings": {}, "selectors": {}})
        html = """
        <html>
          <head>
            <script type="application/ld+json">
              {
                "@context": "https://schema.org",
                "@type": "ItemList",
                "itemListElement": [
                  {
                    "@type": "ListItem",
                    "item": {
                      "@type": "Product",
                      "name": "Capucines BB",
                      "url": "/kor-kr/women/handbags/products/capucines-bb-bag-M48865",
                      "sku": "M48865",
                      "color": "Magnolia",
                      "offers": {
                        "@type": "Offer",
                        "price": "8700000"
                      }
                    }
                  }
                ]
              }
            </script>
          </head>
        </html>
        """

        products = scraper.extract_products_from_html(html, "Bag(Woman)", "https://kr.louisvuitton.com")

        self.assertEqual(len(products), 1)
        self.assertEqual(products[0]["name"], "Capucines BB")
        self.assertEqual(products[0]["price"], 8700000)
        self.assertEqual(products[0]["reference"], "M48865")
        self.assertEqual(products[0]["colors"], "Magnolia")
        self.assertTrue(products[0]["url"].startswith("https://kr.louisvuitton.com/"))

    def test_extract_products_from_selectors_as_fallback(self) -> None:
        scraper = LvScraper(
            None,
            {
                "scraping_settings": {},
                "selectors": {
                    "product_card": "li.lv-product-card",
                    "name": "p.lv-product-card__name",
                    "price": "span.lv-product-card__price",
                    "link": "a",
                },
            },
        )
        html = """
        <html>
          <body>
            <li class="lv-product-card" data-sku="M81704">
              <a href="/kor-kr/men/wallets-and-small-leather-goods/wallets/products/multiple-wallet-M81704">
                <p class="lv-product-card__name">Multiple Wallet</p>
                <span class="lv-product-card__price">KRW 990,000</span>
              </a>
            </li>
          </body>
        </html>
        """

        products = scraper.extract_products_from_html(html, "Wallet(Man)", "https://kr.louisvuitton.com")

        self.assertEqual(len(products), 1)
        self.assertEqual(products[0]["name"], "Multiple Wallet")
        self.assertEqual(products[0]["price"], 990000)
        self.assertEqual(products[0]["reference"], "M81704")
        self.assertTrue("louisvuitton.com" in products[0]["url"])

    def test_detect_block_reason(self) -> None:
        scraper = LvScraper(None, {"scraping_settings": {}, "selectors": {}})

        self.assertEqual(scraper._detect_block_reason("<html><body>403 Forbidden</body></html>"), "http_403_forbidden")
        self.assertEqual(scraper._detect_block_reason("<html><body>Access Denied</body></html>"), "general_access_denied")
        self.assertEqual(
            scraper._detect_block_reason("<html><body>Just a moment... cloudflare</body></html>"),
            "cloudflare_wait",
        )
        self.assertIsNone(scraper._detect_block_reason("<html><body>normal page</body></html>"))

    def test_deduplication(self) -> None:
        scraper = LvScraper(None, {"scraping_settings": {}, "selectors": {}})
        html = """
        <html>
          <head>
            <script type="application/ld+json">
              [
                {
                  "@type": "Product",
                  "name": "Speedy 25",
                  "url": "https://kr.louisvuitton.com/kor-kr/women/handbags/products/speedy-25-M41113",
                  "sku": "M41113",
                  "offers": {"price": "2000000"}
                },
                {
                  "@type": "Product",
                  "name": "Speedy 25",
                  "url": "https://kr.louisvuitton.com/kor-kr/women/handbags/products/speedy-25-M41113",
                  "sku": "M41113",
                  "offers": {"price": "2000000"}
                }
              ]
            </script>
          </head>
        </html>
        """

        products = scraper.extract_products_from_html(html, "Bag(Woman)", "https://kr.louisvuitton.com")
        self.assertEqual(len(products), 1)


if __name__ == "__main__":
    unittest.main()
