#!/usr/bin/env python3
"""
HWiNFO Language File Filtering Tool
Generates a lang.txt containing only the specified locales.

使用例:
  python3 lang_filter.py lang.txt lang_en.txt en
  python3 lang_filter.py lang.txt lang_ja_en.txt en ja
  python3 lang_filter.py lang.txt lang_cjk.txt en ja zh-CN zh-TW ko
"""

import sys
import re
import argparse
from pathlib import Path

SUPPORTED_LOCALES = [
    "en", "fr", "de", "es", "pt-BR", "it", "nl", "da",
    "zh-CN", "zh-TW", "ja", "ko", "vi", "ar", "ru", "uk",
    "cs", "sk", "hu", "pl", "sv", "fi", "no", "el", "tr", "lv", "he"
]


def parse_lang_file(filepath):
    blocks = []
    current_block = None
    pending_comments = []

    with open(filepath, encoding="utf-8") as f:
        for line in f:
            line_stripped = line.rstrip("\r\n")

            if line_stripped.startswith(";"):
                pending_comments.append(line_stripped)
                continue

            tag_match = re.match(r"^\{\{(.*?)\}\}", line_stripped)
            if tag_match:
                if current_block is not None:
                    blocks.append(current_block)
                current_block = {
                    "tag": tag_match.group(1),
                    "pre_comments": pending_comments,
                    "entries": {},
                }
                pending_comments = []
                continue

            kv_match = re.match(r"^([a-zA-Z0-9\-]+)=(.*)$", line_stripped)
            if kv_match and current_block is not None:
                current_block["entries"][kv_match.group(1)] = kv_match.group(2)
                continue

            if line_stripped == "" and current_block is not None:
                blocks.append(current_block)
                current_block = None
                pending_comments = []

    if current_block is not None:
        blocks.append(current_block)

    return blocks


def write_filtered_file(blocks, locales, output_path):
    seen = set()
    ordered = []
    for l in (["en"] + locales):
        if l not in seen:
            seen.add(l)
            ordered.append(l)

    with open(output_path, "w", encoding="utf-8", newline="\r\n") as f:
        for block in blocks:
            for c in block["pre_comments"]:
                f.write(c + "\n")
            f.write("{{" + block["tag"] + "}}\n")
            for locale in ordered:
                if locale in block["entries"]:
                    f.write(f"{locale}={block['entries'][locale]}\n")
            f.write("\n")


def main():
    parser = argparse.ArgumentParser(
        description="HWiNFO Locale Extractor for lang.txt",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Supported Locale:\n  " + ", ".join(SUPPORTED_LOCALES),
    )
    parser.add_argument("input", help="Input (lang.txt)")
    parser.add_argument("output", help="Output")
    parser.add_argument("locales", nargs="+", help="Target Locale Codes (e.g., en ja zh-CN)")

    args = parser.parse_args()

    unknown = [l for l in args.locales if l not in SUPPORTED_LOCALES]
    if unknown:
        print(f"Warning: Unknown locale code: {', '.join(unknown)}", file=sys.stderr)

    if "en" not in args.locales:
        print("Info: 'en' will be included by default.")
        args.locales = ["en"] + args.locales

    print(f"Input:     {args.input}")
    print(f"Output:     {args.output}")
    print(f"Locale: {', '.join(args.locales)}")

    blocks = parse_lang_file(args.input)
    print(f"  → {len(blocks)} block detected")

    write_filtered_file(blocks, args.locales, args.output)

    out_lines = Path(args.output).read_text(encoding="utf-8").count("\n")
    orig_lines = Path(args.input).read_text(encoding="utf-8").count("\n")
    print(f"Done: {out_lines:,} lines processed ({out_lines/orig_lines*100:.1f}%of source)")


if __name__ == "__main__":
    main()
