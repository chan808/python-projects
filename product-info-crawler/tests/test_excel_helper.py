import tempfile
import unittest
from pathlib import Path

from utils.excel_helper import (
    EXCEL_OUTPUT_FOLDER_NAME,
    get_excel_output_path,
    sanitize_excel_file_name,
    sanitize_excel_sheet_name,
)


class ExcelHelperTest(unittest.TestCase):
    def test_get_excel_output_path_creates_desktop_output_folder(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            desktop_dir = Path(temp_dir) / "Desktop"
            desktop_dir.mkdir()

            output_path = get_excel_output_path("Celine", desktop_dir=desktop_dir)

            self.assertEqual(output_path.name, "Celine.xlsx")
            self.assertEqual(output_path.parent.name, EXCEL_OUTPUT_FOLDER_NAME)
            self.assertTrue(output_path.parent.exists())

    def test_sanitize_excel_file_name_replaces_invalid_characters(self) -> None:
        self.assertEqual(sanitize_excel_file_name('Brand:/\\"?*<>|'), "Brand_________")

    def test_sanitize_excel_sheet_name_limits_length_and_invalid_characters(self) -> None:
        sheet_name = sanitize_excel_sheet_name("Shoes:/[Woman] 2026 Spring Collection Very Long Name")

        self.assertNotIn(":", sheet_name)
        self.assertLessEqual(len(sheet_name), 31)


if __name__ == "__main__":
    unittest.main()
