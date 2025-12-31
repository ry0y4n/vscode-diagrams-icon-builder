#!/usr/bin/env python3
"""
Microsoft 365 Architecture Icons Fetcher

Downloads the latest Microsoft 365 architecture icons from Microsoft's official source.
https://learn.microsoft.com/ja-jp/microsoft-365/solutions/architecture-icons-templates
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path
from typing import Generator

import requests

from .base import BaseFetcher, IconCategory


class Microsoft365Fetcher(BaseFetcher):
    """Fetcher for Microsoft 365 Architecture Icons."""

    ICONS_PAGE_URL = (
        "https://learn.microsoft.com/ja-jp/microsoft-365/solutions/architecture-icons-templates"
    )
    # Raw markdown source for the page (more stable to parse than rendered HTML)
    ICONS_PAGE_MARKDOWN_URL = "https://raw.githubusercontent.com/MicrosoftDocs/microsoft-365-docs/public/microsoft-365/solutions/architecture-icons-templates.md"

    def __init__(self, cache_dir: Path):
        super().__init__(cache_dir)
        self._icons_dir: Path | None = None

    @property
    def name(self) -> str:
        return "microsoft365"

    @property
    def display_name(self) -> str:
        return "Microsoft 365 Architecture Icons"

    @staticmethod
    def _choose_best_zip_url(urls: list[str]) -> str:
        """Pick the most likely ZIP URL among candidates."""
        if not urls:
            raise ValueError("urls must be non-empty")

        # De-dup while preserving order
        seen: set[str] = set()
        deduped: list[str] = []
        for url in urls:
            if url not in seen:
                seen.add(url)
                deduped.append(url)

        def score(url: str) -> tuple[int, int]:
            lower = url.lower()
            points = 0

            # Prefer Microsoft domains
            if "download.microsoft.com" in lower:
                points += 8
            if "microsoft" in lower:
                points += 4

            # Prefer M365 / architecture / icons keywords
            if "microsoft-365" in lower or "microsoft_365" in lower or "m365" in lower:
                points += 10
            if "architecture" in lower:
                points += 6
            if "icon" in lower or "icons" in lower:
                points += 4
            if "template" in lower or "templates" in lower:
                points += 1

            # Slight preference for explicit zip
            if lower.endswith(".zip"):
                points += 1

            return (points, len(url))

        return max(deduped, key=score)

    def _find_download_url(self) -> str:
        """Find the latest download URL from Microsoft's page."""
        print(f"  Fetching download URL from {self.ICONS_PAGE_URL}...")

        # 1) Try the rendered page for direct .zip URLs (may not exist).
        page = requests.get(self.ICONS_PAGE_URL, timeout=30)
        page.raise_for_status()
        zip_urls = re.findall(r"https?://[^\"'\s>]+\.zip", page.text, flags=re.IGNORECASE)
        if zip_urls:
            url = self._choose_best_zip_url(zip_urls)
            print(f"  Found: {url}")
            return url

        # 2) Fallback: parse the page's raw markdown from GitHub.
        md = requests.get(self.ICONS_PAGE_MARKDOWN_URL, timeout=30)
        md.raise_for_status()

        # The markdown contains an fwlink for SVG icons.
        match = re.search(r"\[Download SVG icons\]\(([^)]+)\)", md.text, flags=re.IGNORECASE)
        if not match:
            raise RuntimeError("Could not find 'Download SVG icons' link in page markdown")

        fwlink = match.group(1).strip()
        resolved = self._resolve_download_url(fwlink)
        print(f"  Found: {resolved}")
        return resolved

    @staticmethod
    def _resolve_download_url(url: str) -> str:
        """Resolve fwlink/aka.ms URLs to the final downloadable URL."""
        try:
            response = requests.head(url, timeout=30, allow_redirects=True)
            if response.status_code >= 400:
                raise requests.HTTPError(f"HTTP {response.status_code}")
            return response.url
        except Exception:
            # Some endpoints don't support HEAD; fall back to GET (streaming) just to resolve.
            response = requests.get(url, timeout=30, allow_redirects=True, stream=True)
            response.raise_for_status()
            return response.url

    def _download_zip(self, url: str) -> Path:
        """Download the ZIP file."""
        zip_path = self.cache_dir / "microsoft365_icons.zip"

        # Check if already downloaded (simple cache)
        if zip_path.exists():
            print(f"  Using cached: {zip_path}")
            return zip_path

        print("  Downloading...")
        response = requests.get(url, timeout=120, stream=True)
        response.raise_for_status()

        total_size = int(response.headers.get("content-length", 0))

        with open(zip_path, "wb") as f:
            downloaded = 0
            for chunk in response.iter_content(chunk_size=8192):
                if not chunk:
                    continue
                f.write(chunk)
                downloaded += len(chunk)
                if total_size:
                    percent = (downloaded / total_size) * 100
                    print(f"\r  Downloaded: {percent:.1f}%", end="", flush=True)

        if total_size:
            print()

        print(f"  Saved: {zip_path} ({zip_path.stat().st_size // 1024 // 1024} MB)")
        return zip_path

    def _extract_zip(self, zip_path: Path) -> Path:
        """Extract the ZIP file."""
        extract_dir = self.cache_dir / "microsoft365_icons"

        # Check if already extracted
        if extract_dir.exists() and any(extract_dir.iterdir()):
            print(f"  Using cached extraction: {extract_dir}")
            return extract_dir

        print("  Extracting...")
        extract_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(extract_dir)

        print(f"  Extracted to: {extract_dir}")
        return extract_dir

    def fetch(self) -> Path:
        """Download and extract Microsoft 365 icons."""
        print(f"[{self.display_name}]")

        url = self._find_download_url()
        zip_path = self._download_zip(url)
        self._icons_dir = self._extract_zip(zip_path)

        return self._icons_dir

    def _iter_svg_leaf_dirs(self) -> list[Path]:
        """Return directories that directly contain SVG files.

        We treat each such directory as one icon category to avoid accidentally
        collapsing different themes (Microsoft Blue/Teams Purple/etc.) into one.
        """
        if not self._icons_dir:
            raise RuntimeError("Must call fetch() first")

        svg_dirs: set[Path] = set()

        # Include any directory that has SVGs directly within it.
        for svg_file in self._icons_dir.rglob("*.svg"):
            svg_dirs.add(svg_file.parent)

        return sorted(svg_dirs, key=lambda p: str(p))

    def get_categories(self) -> Generator[IconCategory, None, None]:
        """Get Microsoft 365 icon categories."""
        if not self._icons_dir:
            raise RuntimeError("Must call fetch() first")

        category_dirs = self._iter_svg_leaf_dirs()
        print(f"  Found {len(category_dirs)} SVG folders")

        for category_dir in category_dirs:
            svg_files = sorted(category_dir.glob("*.svg"))
            if not svg_files:
                continue

            rel = category_dir.relative_to(self._icons_dir)
            # Use the relative path as the category name to keep it unique.
            category_name = " / ".join(rel.parts)
            yield IconCategory(name=category_name, svg_files=svg_files)

    def cleanup(self) -> None:
        """Remove cached files."""
        import shutil

        if self.cache_dir.exists():
            shutil.rmtree(self.cache_dir)
