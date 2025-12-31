#!/usr/bin/env python3
"""
Microsoft Fabric Icons Fetcher

Downloads the latest Fabric icons from Microsoft's official source.
https://learn.microsoft.com/en-us/fabric/fundamentals/icons
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path
from typing import Generator

import requests

from .base import BaseFetcher, IconCategory


class FabricFetcher(BaseFetcher):
    """Fetcher for Microsoft Fabric Icons."""

    ICONS_PAGE_URL = "https://learn.microsoft.com/en-us/fabric/fundamentals/icons"
    
    # GitHub repository URL pattern
    GITHUB_PATTERN = r'https://github\.com/microsoft/fabric-samples/blob/[^/]+/[^"\'<>\s]+\.zip'
    
    # Direct download URL from GitHub (convert blob URL to raw URL)
    GITHUB_RAW_URL = "https://github.com/microsoft/fabric-samples/raw/main/docs-samples/Icons.zip"

    def __init__(self, cache_dir: Path):
        super().__init__(cache_dir)
        self._icons_dir: Path | None = None

    @property
    def name(self) -> str:
        return "fabric"

    @property
    def display_name(self) -> str:
        return "Microsoft Fabric Icons"

    def _find_download_url(self) -> str:
        """Find the latest download URL from Microsoft's page."""
        print(f"  Fetching download URL from {self.ICONS_PAGE_URL}...")

        try:
            response = requests.get(self.ICONS_PAGE_URL, timeout=30)
            response.raise_for_status()

            # Find GitHub link in page content
            match = re.search(self.GITHUB_PATTERN, response.text)
            if match:
                github_url = match.group(0)
                # Convert blob URL to raw URL for direct download
                raw_url = github_url.replace("/blob/", "/raw/")
                print(f"  Found: {raw_url}")
                return raw_url
        except Exception as e:
            print(f"  Warning: Could not fetch from page ({e}), using fallback URL")

        # Fallback to known direct download URL
        print(f"  Using fallback URL: {self.GITHUB_RAW_URL}")
        return self.GITHUB_RAW_URL

    def _download_zip(self, url: str) -> Path:
        """Download the ZIP file."""
        zip_path = self.cache_dir / "fabric_icons.zip"

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

        print(f"\n  Saved: {zip_path} ({zip_path.stat().st_size // 1024 // 1024} MB)")
        return zip_path

    def _extract_zip(self, zip_path: Path) -> Path:
        """Extract the ZIP file."""
        extract_dir = self.cache_dir / "fabric_icons"

        # Check if already extracted
        if extract_dir.exists() and any(extract_dir.iterdir()):
            print(f"  Using cached extraction: {extract_dir}")
            return extract_dir

        print("  Extracting...")
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(extract_dir)

        print(f"  Extracted to: {extract_dir}")
        return extract_dir

    def fetch(self) -> Path:
        """Download and extract Fabric icons."""
        print(f"[{self.display_name}]")

        url = self._find_download_url()
        zip_path = self._download_zip(url)
        self._icons_dir = self._extract_zip(zip_path)

        return self._icons_dir

    def _find_svg_root(self) -> Path:
        """Find the root directory containing SVG category folders."""
        if not self._icons_dir:
            raise RuntimeError("Must call fetch() first")

        # Look for SVG files recursively
        svg_files = sorted(self._icons_dir.rglob('*.svg'))
        if not svg_files:
            raise RuntimeError(f"No SVG files found in {self._icons_dir}")

        # Collect all immediate parent directories of SVG files
        svg_parents = set(svg_file.parent for svg_file in svg_files)
        
        # If all SVGs are in the same directory with no subdirectories
        if len(svg_parents) == 1:
            return svg_parents.pop()
        
        # Find the common ancestor that contains multiple category directories
        # Group by depth from icons_dir
        depth_to_dirs: dict[int, set[Path]] = {}
        for svg_parent in svg_parents:
            rel_path = svg_parent.relative_to(self._icons_dir)
            depth = len(rel_path.parts)
            
            # Get the directory at each depth level
            for d in range(depth):
                ancestor = self._icons_dir / Path(*rel_path.parts[:d+1])
                depth_to_dirs.setdefault(d, set()).add(ancestor)
        
        # Find the shallowest depth with multiple directories (categories)
        for depth in sorted(depth_to_dirs.keys()):
            dirs_at_depth = depth_to_dirs[depth]
            if len(dirs_at_depth) > 1:
                # Found multiple categories - return their parent
                if depth == 0:
                    return self._icons_dir
                # Return the parent of these directories
                first_dir = list(dirs_at_depth)[0]
                return first_dir.parent
        
        # Fallback
        return self._icons_dir

    def get_categories(self) -> Generator[IconCategory, None, None]:
        """Get Fabric icon categories."""
        if not self._icons_dir:
            raise RuntimeError("Must call fetch() first")

        svg_root = self._find_svg_root()
        print(f"  SVG root: {svg_root}")

        # Check if all SVGs are in a flat structure (no subdirectories)
        direct_svgs = sorted(svg_root.glob('*.svg'))
        subdirs = [d for d in svg_root.iterdir() if d.is_dir()]

        if direct_svgs and not subdirs:
            # Flat structure - all icons in one category
            yield IconCategory(name="Fabric Icons", svg_files=direct_svgs)
        else:
            # Hierarchical structure - each subdirectory is a category
            for category_dir in sorted(svg_root.iterdir()):
                if not category_dir.is_dir():
                    continue

                # Find all SVG files (may be in subdirectories)
                svg_files = sorted(category_dir.rglob('*.svg'))

                if svg_files:
                    # Clean up category name
                    category_name = category_dir.name.replace('-', ' ').replace('_', ' ')
                    yield IconCategory(name=category_name, svg_files=svg_files)

    def cleanup(self) -> None:
        """Remove cached files."""
        import shutil
        if self.cache_dir.exists():
            shutil.rmtree(self.cache_dir)


if __name__ == "__main__":
    # Test the fetcher
    cache_dir = Path("./temp/fabric_cache")
    fetcher = FabricFetcher(cache_dir)

    fetcher.fetch()

    print("\nCategories found:")
    for category in fetcher.get_categories():
        print(f"  - {category.name}: {len(category.svg_files)} icons")
