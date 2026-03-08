# Aeromux Database Builder
# Copyright (C) 2025-2026 Nandor Toth <dev@nandortoth.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

import logging
import tarfile
import time
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

_MAX_RETRIES = 5
_INITIAL_BACKOFF = 5  # seconds
_RETRYABLE_EXCEPTIONS = (httpx.TimeoutException, httpx.ConnectError)


@dataclass
class DownloadResult:
    """Result of a download operation."""

    path: Path
    size_bytes: int


@dataclass
class ExtractResult:
    """Result of a ZIP extraction operation."""

    path: Path
    file_count: int


def _with_retry[T](fn: Callable[[], T], description: str) -> T:
    """Execute fn() with retry on transient network errors.

    Retries up to _MAX_RETRIES times with doubling backoff
    starting at _INITIAL_BACKOFF seconds (5s, 10s, 20s, 40s).

    Args:
        fn: Zero-argument callable to execute.
        description: Human-readable label for log messages.

    Raises:
        httpx.TimeoutException: After all retry attempts are exhausted.
        httpx.ConnectError: After all retry attempts are exhausted.
    """
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            return fn()
        except _RETRYABLE_EXCEPTIONS as exc:
            if attempt == _MAX_RETRIES:
                logger.error("  %s failed after %d attempts: %s", description, _MAX_RETRIES, exc)
                raise
            backoff = _INITIAL_BACKOFF * (2 ** (attempt - 1))
            logger.warning(
                "  %s failed (attempt %d/%d): %s — retrying in %ds...",
                description, attempt, _MAX_RETRIES, exc, backoff,
            )
            time.sleep(backoff)


def download(
    url: str,
    filename: str,
    dest_dir: Path,
    progress_callback: Callable[[int, int | None], None] | None = None,
) -> DownloadResult:
    """Download a file to the specified directory.

    Args:
        url: Remote URL of the data source archive.
        filename: Local filename to save under in the destination directory.
        dest_dir: Directory to save the downloaded file in.
        progress_callback: Optional callback invoked with (downloaded_bytes, total_bytes)
            after each chunk.

    Returns:
        DownloadResult with path and file size.

    Raises:
        httpx.HTTPStatusError: When the server returns a non-2xx response.
        httpx.TimeoutException: After all retry attempts are exhausted.
        httpx.ConnectError: After all retry attempts are exhausted.
    """
    dest = dest_dir / filename

    logger.debug("Downloading %s", url)

    def _do_download() -> int:
        downloaded = 0
        with httpx.stream("GET", url, follow_redirects=True) as response:
            response.raise_for_status()
            total = response.headers.get("content-length")
            total_bytes = int(total) if total else None

            with open(dest, "wb") as f:
                for chunk in response.iter_bytes(chunk_size=8192):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback:
                        progress_callback(downloaded, total_bytes)
        return downloaded

    downloaded = _with_retry(_do_download, f"Download {filename}")

    logger.debug("Downloaded %s (%d bytes)", filename, downloaded)
    return DownloadResult(path=dest, size_bytes=downloaded)


def fetch_text(url: str) -> str:
    """Download a URL and return its text content.

    Args:
        url: Remote URL to fetch.

    Returns:
        Response body as a string.

    Raises:
        httpx.HTTPStatusError: When the server returns a non-2xx response.
        httpx.TimeoutException: After all retry attempts are exhausted.
        httpx.ConnectError: After all retry attempts are exhausted.
    """
    logger.debug("Fetching %s", url)

    def _do_fetch() -> str:
        response = httpx.get(url, follow_redirects=True)
        response.raise_for_status()
        return response.text

    return _with_retry(_do_fetch, f"Fetch {url}")


def extract_zip(zip_path: Path, dest_dir: Path | None = None) -> ExtractResult:
    """Extract a ZIP archive to a directory.

    Args:
        zip_path: Path to the ZIP file to extract.
        dest_dir: Destination directory. Defaults to a sibling directory
            named after the archive stem.

    Returns:
        ExtractResult with path and file count.
    """
    if dest_dir is None:
        dest_dir = zip_path.parent / zip_path.stem

    logger.debug("Extracting %s to %s", zip_path, dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path, "r") as zf:
        file_count = len(zf.namelist())
        zf.extractall(dest_dir)

    logger.debug("Extracted %d files to %s", file_count, dest_dir)
    return ExtractResult(path=dest_dir, file_count=file_count)


def extract_tarball(tar_path: Path, dest_dir: Path | None = None) -> ExtractResult:
    """Extract a tar.gz archive to a directory.

    Args:
        tar_path: Path to the tar.gz file to extract.
        dest_dir: Destination directory. Defaults to a sibling directory
            named after the archive stem (without .tar.gz).

    Returns:
        ExtractResult with path and file count.
    """
    if dest_dir is None:
        stem = tar_path.name
        for suffix in (".tar.gz", ".tgz"):
            if stem.endswith(suffix):
                stem = stem[: -len(suffix)]
                break
        dest_dir = tar_path.parent / stem

    logger.debug("Extracting %s to %s", tar_path, dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    with tarfile.open(tar_path, "r:gz") as tf:
        file_count = len(tf.getnames())
        tf.extractall(dest_dir, filter="data")

    logger.debug("Extracted %d files to %s", file_count, dest_dir)
    return ExtractResult(path=dest_dir, file_count=file_count)
