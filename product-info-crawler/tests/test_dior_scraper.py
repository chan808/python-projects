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

        products = scraper._extract_products_from_json_ld(html, "Wallet(Man)")

        self.assertEqual(len(products), 1)
        self.assertEqual(products[0]["name"], "Dior Wallet")
        self.assertEqual(products[0]["price"], 1200000)
        self.assertEqual(products[0]["reference"], "WALLET-123")
        self.assertEqual(products[0]["colors"], "Black")
        self.assertTrue(products[0]["url"].startswith("https://www.dior.com/"))

    def test_parse_price_returns_none_for_empty_value(self) -> None:
        scraper = DiorScraper(None, {"scraping_settings": {}, "selectors": {}})
        self.assertIsNone(scraper._parse_price(""))
        self.assertEqual(scraper._parse_price("KRW 1,980,000"), 1980000)


if __name__ == "__main__":
    unittest.main()
