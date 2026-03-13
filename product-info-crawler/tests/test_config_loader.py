import json
import tempfile
import unittest
from pathlib import Path

from utils.config_loader import ConfigError, discover_brand_configs, load_brand_config


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


class ConfigLoaderTest(unittest.TestCase):
    def test_load_brand_config_resolves_relative_service_account_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            config_dir = project_root / "config"
            credentials_dir = project_root / "credentials"
            config_dir.mkdir()
            credentials_dir.mkdir()
            (credentials_dir / "service_account.json").write_text("{}", encoding="utf-8")

            config_path = config_dir / "sample.json"
            write_json(
                config_path,
                {
                    "brand": {
                        "id": "sample",
                        "display_name": "Sample",
                        "scraper": "sample",
                    },
                    "google_sheets": {
                        "service_account_file": "credentials/service_account.json",
                        "spreadsheet_name": "테스트 시트",
                    },
                    "selectors": {
                        "product_card": ".card",
                        "name": ".name",
                        "price": ".price",
                        "link": "a",
                    },
                    "categories": {
                        "bags": "https://example.com/bags",
                    },
                },
            )

            config = load_brand_config(config_path, project_root)

            self.assertEqual(
                config["google_sheets"]["service_account_file"],
                str(project_root / "credentials" / "service_account.json"),
            )

    def test_discover_brand_configs_returns_sorted_brand_summaries(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            config_dir = project_root / "config"
            credentials_dir = project_root / "credentials"
            config_dir.mkdir()
            credentials_dir.mkdir()
            (credentials_dir / "service_account.json").write_text("{}", encoding="utf-8")

            common_payload = {
                "google_sheets": {
                    "service_account_file": "credentials/service_account.json",
                    "spreadsheet_name": "테스트 시트",
                },
                "selectors": {
                    "product_card": ".card",
                    "name": ".name",
                    "price": ".price",
                    "link": "a",
                },
                "categories": {
                    "bags": "https://example.com/bags",
                },
            }

            write_json(
                config_dir / "b_brand.json",
                {
                    "brand": {"id": "b_brand", "display_name": "Brand B", "scraper": "b_brand"},
                    **common_payload,
                },
            )
            write_json(
                config_dir / "a_brand.json",
                {
                    "brand": {"id": "a_brand", "display_name": "Brand A", "scraper": "a_brand"},
                    **common_payload,
                },
            )

            brands = discover_brand_configs(config_dir, project_root)

            self.assertEqual([brand.brand_id for brand in brands], ["a_brand", "b_brand"])

    def test_discover_brand_configs_rejects_duplicate_brand_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            config_dir = project_root / "config"
            credentials_dir = project_root / "credentials"
            config_dir.mkdir()
            credentials_dir.mkdir()
            (credentials_dir / "service_account.json").write_text("{}", encoding="utf-8")

            common_payload = {
                "google_sheets": {
                    "service_account_file": "credentials/service_account.json",
                    "spreadsheet_name": "테스트 시트",
                },
                "selectors": {
                    "product_card": ".card",
                    "name": ".name",
                    "price": ".price",
                    "link": "a",
                },
                "categories": {
                    "bags": "https://example.com/bags",
                },
            }

            write_json(
                config_dir / "brand_one.json",
                {
                    "brand": {"id": "duplicate", "display_name": "Brand One", "scraper": "brand_one"},
                    **common_payload,
                },
            )
            write_json(
                config_dir / "brand_two.json",
                {
                    "brand": {"id": "duplicate", "display_name": "Brand Two", "scraper": "brand_two"},
                    **common_payload,
                },
            )

            with self.assertRaises(ConfigError):
                discover_brand_configs(config_dir, project_root)


if __name__ == "__main__":
    unittest.main()
