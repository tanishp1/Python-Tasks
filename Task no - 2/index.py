import asyncio
import aiohttp
import os
import time
from pathlib import Path
from urllib.parse import urlparse
from PIL import Image, ImageDraw, ImageFont
import math

DOWNLOAD_DIR = Path("downloaded_images")
MAX_CONCURRENT_REQUESTS = 20   # tune based on target server limits
TIMEOUT = aiohttp.ClientTimeout(total=30)

def get_filename(url: str, index: int) -> str:
    name = f"image_{index}.jpg"
    return name

async def download_one(session: aiohttp.ClientSession, url: str, index: int,
                        semaphore: asyncio.Semaphore, results: dict):
    filepath = DOWNLOAD_DIR / get_filename(url, index)
    async with semaphore:  # limits concurrent connections
        try:
            async with session.get(url) as response:
                response.raise_for_status()
                content = await response.read()
                # File I/O is offloaded so it doesn't block the event loop
                await asyncio.to_thread(filepath.write_bytes, content)
                results[url] = "success"
        except Exception as e:
            results[url] = f"failed: {e}"

async def download_all(urls: list[str]):
    DOWNLOAD_DIR.mkdir(exist_ok=True)
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
    results = {}

    connector = aiohttp.TCPConnector(limit=MAX_CONCURRENT_REQUESTS)
    async with aiohttp.ClientSession(connector=connector, timeout=TIMEOUT) as session:
        tasks = [
            download_one(session, url, i, semaphore, results)
            for i, url in enumerate(urls)
        ]
        await asyncio.gather(*tasks)  # session & connector auto-cleaned on exit

    return results

def display_images_grid(folder: Path, thumb_size=(200, 300), cols=10):
    image_files = sorted(folder.glob("*.jpg")) + sorted(folder.glob("*.png"))
    if not image_files:
        print("No images found to display.")
        return

    rows = math.ceil(len(image_files) / cols)
    grid_w = cols * thumb_size[0]
    grid_h = rows * thumb_size[1]
    grid = Image.new("RGB", (grid_w, grid_h), color=(30, 30, 30))

    for idx, img_path in enumerate(image_files):
        try:
            img = Image.open(img_path).resize(thumb_size)
            x = (idx % cols) * thumb_size[0]
            y = (idx // cols) * thumb_size[1]
            grid.paste(img, (x, y))
        except Exception as e:
            print(f"Could not open {img_path.name}: {e}")

    grid.show(title="Downloaded Images")
    print(f"Displaying {len(image_files)} images in grid ({cols} columns x {rows} rows)")


if __name__ == "__main__":
    urls = [f"https://picsum.photos/seed/{i}/200/300" for i in range(100)]  # real public image URLs

    start = time.perf_counter()
    results = asyncio.run(download_all(urls))
    elapsed = time.perf_counter() - start

    failures = {u: r for u, r in results.items() if "failed" in r}
    print(f"Downloaded {len(urls) - len(failures)}/{len(urls)} in {elapsed:.2f}s")
    if failures:
        print("Failures:", failures)

    display_images_grid(DOWNLOAD_DIR)