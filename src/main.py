#!/usr/bin/env python3
"""
Draw.io Icon Library Generator

Main script to fetch icons from various sources and generate
Draw.io custom library XML files.
"""

import argparse
import shutil
from pathlib import Path

from src.fetchers.azure import AzureFetcher
from src.converters.svg_to_drawio import (
    create_library_entry_from_file,
    create_library_xml,
)


def generate_azure_libraries(output_dir: Path, cache_dir: Path) -> dict:
    """
    Generate Draw.io libraries for all Azure icon categories.
    
    Args:
        output_dir: Directory to save generated XML files
        cache_dir: Directory for cached downloads
        
    Returns:
        Dictionary with generation statistics
    """
    fetcher = AzureFetcher(cache_dir)
    fetcher.fetch()
    
    azure_output = output_dir / "azure"
    azure_output.mkdir(parents=True, exist_ok=True)
    
    stats = {
        "categories": 0,
        "icons": 0,
        "files": [],
    }
    
    print("\nGenerating libraries...")
    
    for category in fetcher.get_categories():
        # Create safe filename
        safe_name = category.name.lower().replace(' ', '-').replace('+', 'and')
        safe_name = ''.join(c for c in safe_name if c.isalnum() or c == '-')
        output_path = azure_output / f"{safe_name}.xml"
        
        # Convert all SVGs in category
        entries = []
        for svg_file in category.svg_files:
            try:
                entry = create_library_entry_from_file(svg_file)
                entries.append(entry)
            except Exception as e:
                print(f"    ✗ {svg_file.name}: {e}")
        
        if entries:
            # Generate library XML
            library_xml = create_library_xml(entries)
            output_path.write_text(library_xml, encoding='utf-8')
            
            stats["categories"] += 1
            stats["icons"] += len(entries)
            stats["files"].append(str(output_path.relative_to(output_dir.parent)))
            
            print(f"  ✓ {category.name}: {len(entries)} icons → {output_path.name}")
    
    return stats


def generate_index_json(output_dir: Path, stats: dict) -> None:
    """Generate an index.json file listing all available libraries."""
    import json
    
    index = {
        "azure": {
            "name": "Azure Architecture Icons",
            "categories": stats["files"],
            "total_icons": stats["icons"],
        }
    }
    
    index_path = output_dir / "index.json"
    index_path.write_text(json.dumps(index, indent=2), encoding='utf-8')
    print(f"\n  Generated index: {index_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Generate Draw.io custom icon libraries"
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=Path("output"),
        help="Output directory for generated XML files"
    )
    parser.add_argument(
        "--cache", "-c",
        type=Path,
        default=Path("temp"),
        help="Cache directory for downloaded files"
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Clean cache after generation"
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("Draw.io Icon Library Generator")
    print("=" * 60)
    
    # Generate Azure libraries
    stats = generate_azure_libraries(args.output, args.cache)
    
    # Generate index
    generate_index_json(args.output, stats)
    
    print("\n" + "=" * 60)
    print(f"Summary:")
    print(f"  Categories: {stats['categories']}")
    print(f"  Total icons: {stats['icons']}")
    print(f"  Output: {args.output.absolute()}")
    print("=" * 60)
    
    if args.clean:
        print("\nCleaning cache...")
        shutil.rmtree(args.cache, ignore_errors=True)
        print("  Done.")


if __name__ == "__main__":
    main()
