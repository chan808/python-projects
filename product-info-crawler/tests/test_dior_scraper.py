import unittest

from scrapers.dior_scraper import DiorScraper


class DiorScraperTest(unittest.TestCase):
    def test_extract_products_from_json_ld(self) -> None:
        scraper = DiorScraper(None, {"scraping_settings": {}, "selectors": {}})
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
                      "name": "Dior Wallet",
                      "url": "/ko_kr/fashion/products/123",
                      "sku": "WALLET-123",
                      "color": "Black",
                      "offers": {
                        "@type": "Offer",
                        "price": "1200000"
                      }
                    }
                  }
                ]
              }
            </script>
          </head>
        </html>
        """

        products = scraper.extract_products_from_html(html, "Wallet(Man)", "https://www.dior.com/ko_kr/fashion")

        self.assertEqual(len(products), 1)
        self.assertEqual(products[0]["name"], "Dior Wallet")
        self.assertEqual(products[0]["price"], 1200000)
        self.assertEqual(products[0]["reference"], "WALLET-123")
        self.assertEqual(products[0]["colors"], "Black")
        self.assertTrue(products[0]["url"].startswith("https://www.dior.com/"))

    def test_extract_products_from_selectors_as_fallback(self) -> None:
        scraper = DiorScraper(
            None,
            {
                "scraping_settings": {},
                "selectors": {
                    "product_card": "article.product-card",
                    "name": "h2",
                    "price": "span.price",
                    "link": "a",
                },
            },
        )
        html = """
        <html>
          <body>
            <article class="product-card">
              <a href="/ko_kr/fashion/products/abc">
                <h2>Dior Ring</h2>
                <span class="price">KRW 950,000</span>
              </a>
            </article>
          </body>
        </html>
        """

        products = scraper.extract_products_from_html(html, "Ring(Woman)", "https://www.dior.com")

        self.assertEqual(len(products), 1)
        self.assertEqual(products[0]["name"], "Dior Ring")
        self.assertEqual(products[0]["price"], 950000)
        self.assertEqual(products[0]["url"], "https://www.dior.com/ko_kr/fashion/products/abc")

    def test_detect_block_reason(self) -> None:
        scraper = DiorScraper(None, {"scraping_settings": {}, "selectors": {}})

        self.assertEqual(scraper._detect_block_reason("<html><body>403 Forbidden</body></html>"), "http_403")
        self.assertEqual(scraper._detect_block_reason("<html><body>Access Denied</body></html>"), "access_denied")
        self.assertIsNone(scraper._detect_block_reason("<html><body>normal page</body></html>"))


if __name__ == "__main__":
    unittest.main()
