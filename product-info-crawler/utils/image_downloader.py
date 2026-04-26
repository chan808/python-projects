import base64
from pathlib import Path
from urllib.parse import urlparse

import requests


IMAGE_OUTPUT_FOLDER_NAME = "Brand_Product_Images"


def get_image_output_dir(brand_id: str, reference: str, desktop_dir: Path = None) -> Path:
    desktop = desktop_dir or (Path.home() / "Desktop")
    return desktop / IMAGE_OUTPUT_FOLDER_NAME / brand_id / reference


def _download_via_browser(driver, url: str, dest_file: Path) -> bool:
    """브라우저의 fetch API로 이미지를 다운로드합니다 (CDN 인증 우회용)."""
    try:
        script = """
        var callback = arguments[arguments.length - 1];
        fetch(arguments[0], {credentials: 'include'})
            .then(function(r) { return r.blob(); })
            .then(function(blob) {
                var reader = new FileReader();
                reader.onloadend = function() { callback(reader.result); };
                reader.readAsDataURL(blob);
            })
            .catch(function() { callback(null); });
        """
        result = driver.execute_async_script(script, url)
        if not result or not isinstance(result, str) or not result.startswith("data:"):
            return False
        _, encoded = result.split(",", 1)
        image_bytes = base64.b64decode(encoded)
        if image_bytes:
            dest_file.write_bytes(image_bytes)
            return True
    except Exception:
        pass
    return False


def download_product_images(
    urls: list[str],
    dest_dir: Path,
    driver=None,
    timeout: int = 10,
) -> list[str]:
    """
    이미지 URL 목록을 dest_dir에 다운로드합니다.
    requests 실패 시 Selenium fetch API로 재시도합니다.
    반환: 저장된 로컬 파일 경로 목록
    """
    if not urls:
        return []

    session = requests.Session()
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
    })

    if driver:
        for cookie in driver.get_cookies():
            session.cookies.set(cookie["name"], cookie["value"])
        current_url = driver.current_url
        if current_url:
            parsed = urlparse(current_url)
            session.headers["Referer"] = f"{parsed.scheme}://{parsed.netloc}/"

    dest_dir.mkdir(parents=True, exist_ok=True)

    local_paths: list[str] = []
    for i, url in enumerate(urls, start=1):
        ext = Path(url.split("?")[0]).suffix or ".jpg"
        if not ext.startswith(".") or len(ext) > 5:
            ext = ".jpg"
        dest_file = dest_dir / f"{i:02d}{ext}"

        if dest_file.exists():
            local_paths.append(str(dest_file))
            continue

        downloaded = False
        try:
            resp = session.get(url, timeout=timeout)
            if resp.status_code == 200 and resp.content:
                dest_file.write_bytes(resp.content)
                local_paths.append(str(dest_file))
                downloaded = True
        except Exception:
            pass

        if not downloaded and driver:
            if _download_via_browser(driver, url, dest_file):
                local_paths.append(str(dest_file))

    return local_paths
