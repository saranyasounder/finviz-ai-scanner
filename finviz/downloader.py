from datetime import datetime
from pathlib import Path


DOWNLOAD_ROOT = Path("downloads")


def download(page):
    """
    Downloads the current Finviz screener CSV.

    Returns:
        Path: Full path of the downloaded CSV.
    """

    now = datetime.now()

    # Example: downloads/2026-07-25/
    download_dir = DOWNLOAD_ROOT / now.strftime("%Y-%m-%d")
    download_dir.mkdir(parents=True, exist_ok=True)

    filename = (
        f"finviz_"
        f"{now.strftime('%H-%M-%S')}.csv"
    )

    file_path = download_dir / filename

    print("Downloading screener...")

    with page.expect_download() as download_info:
        page.get_by_text("Export").click()

    download = download_info.value

    download.save_as(str(file_path))

    print(f"Saved to: {file_path}")

    return file_path