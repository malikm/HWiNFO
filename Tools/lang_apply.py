#!/usr/bin/env python3
"""
HWiNFO lang.txt Translate Apply Tool

Applies the contents of an edited filter file (e.g., lang_ja_en.txt) to the original lang.txt and generates a new file.

Behavior:
 - Translations in the edited file will overwrite entries in the original file.
 - Locales or entries not found in the edited file will remain unchanged.
 - Blocks are matched using the en= values; adding or deleting blocks is not supported.

Usage:
  python3 lang_apply.py lang.txt lang_ja_en_edited.txt lang_out.txt
  python3 lang_apply.py lang.txt lang_ja_en_edited.txt lang_out.txt --report
"""

import sys
import re
import argparse
from pathlib import Path


def parse_lang_file(filepath):
    """Parses lang.txt and returns a list of blocks. Uses the 'en=' value as the key."""
    blocks = []
    current_block = None
    pending_comments = []

    with open(filepath, encoding="utf-8") as f:
        for line in f:
            s = line.rstrip("\r\n")

            if s.startswith(";"):
                pending_comments.append(s)
                continue

            tag_match = re.match(r"^\{\{(.*?)\}\}", s)
            if tag_match:
                if current_block is not None:
                    blocks.append(current_block)
                current_block = {
                    "tag": tag_match.group(1),
                    "pre_comments": pending_comments,
                    "entries": {},       # locale -> value
                    "entry_order": [],   # Preserve original order
                }
                pending_comments = []
                continue

            kv = re.match(r"^([a-zA-Z0-9\-]+)=(.*)$", s)
            if kv and current_block is not None:
                locale, value = kv.group(1), kv.group(2)
                current_block["entries"][locale] = value
                if locale not in current_block["entry_order"]:
                    current_block["entry_order"].append(locale)
                continue

            if s == "" and current_block is not None:
                blocks.append(current_block)
                current_block = None
                pending_comments = []

    if current_block is not None:
        blocks.append(current_block)

    return blocks


def build_index(blocks):
    """Returns a block index keyed by the 'en=' value."""
    index = {}
    for block in blocks:
        en_val = block["entries"].get("en")
        if en_val is not None:
            index[en_val] = block
    return index


def apply_edits(base_blocks, edit_index, verbose=False):
    """
    Updates base_blocks by applying translations from edit_index where keys
    match. Returns the total count of modified entries.
    """
    stats = {"updated": 0, "unchanged": 0, "not_found": 0}

    for block in base_blocks:
        en_val = block["entries"].get("en")
        if en_val is None:
            continue

        edit_block = edit_index.get(en_val)
        if edit_block is None:
            stats["not_found"] += 1
            continue

        changed = False
        for locale, new_val in edit_block["entries"].items():
            if locale == "en":
                continue  # en は変更しない
            old_val = block["entries"].get(locale)
            if old_val != new_val:
                block["entries"][locale] = new_val
                # entry_order にない場合は追加
                if locale not in block["entry_order"]:
                    block["entry_order"].append(locale)
                changed = True
                if verbose:
                    print(f"  [{locale}] {en_val!r}")
                    print(f"    前: {old_val!r}")
                    print(f"    後: {new_val!r}")

        if changed:
            stats["updated"] += 1
        else:
            stats["unchanged"] += 1

    return stats


def write_lang_file(blocks, output_path):
    """ブロックリストを lang.txt 形式で書き出す。"""
    with open(output_path, "w", encoding="utf-8", newline="\r\n") as f:
        for block in blocks:
            for c in block["pre_comments"]:
                f.write(c + "\n")
            f.write("{{" + block["tag"] + "}}\n")
            for locale in block["entry_order"]:
                if locale in block["entries"]:
                    f.write(f"{locale}={block['entries'][locale]}\n")
            f.write("\n")


def main():
    parser = argparse.ArgumentParser(
        description="編集済みフィルタファイルの翻訳を元の lang.txt に適用します",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("base",   help="元ファイル (lang.txt)")
    parser.add_argument("edited", help="編集済みファイル (lang_ja_en_edited.txt など)")
    parser.add_argument("output", help="出力ファイルパス")
    parser.add_argument("--report", action="store_true",
                        help="変更されたエントリを詳細表示する")
    parser.add_argument("--dry-run", action="store_true",
                        help="ファイルを書き出さずに変更件数だけ確認する")

    args = parser.parse_args()

    print(f"Original:       {args.base}")
    print(f"Edited: {args.edited}")
    print(f"Output:             {args.output}")
    print()

    print("Analyze...")
    base_blocks = parse_lang_file(args.base)
    edit_blocks = parse_lang_file(args.edited)
    print(f"  Original:       {len(base_blocks)} block")
    print(f"  Edited: {len(edit_blocks)} block")
    print()

    edit_index = build_index(edit_blocks)

    if args.report:
        print("=== Change Details ===")
    stats = apply_edits(base_blocks, edit_index, verbose=args.report)
    if args.report:
        print()

    print("=== Results ===")
    print(f"  Updated blocks:    {stats['updated']:>5}")
    print(f"  Unchanged blocks:    {stats['unchanged']:>5}")
    print(f"  Not in edited file: {stats['not_found']:>5}")

    if args.dry_run:
        print("\n[dry-run] file writing skipped.")
        return

    write_lang_file(base_blocks, args.output)
    out_lines = Path(args.output).read_text(encoding="utf-8").count("\n")
    print(f"\nDone: {args.output} ({out_lines:,} lines)")


if __name__ == "__main__":
    main()
