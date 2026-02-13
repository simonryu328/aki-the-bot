#!/usr/bin/env python3
"""
Parse sticker logs and generate stickers.json grouped by emoji.
Uses regex to find all file IDs and their associated metadata.
"""

import re
import json
from collections import defaultdict
from pathlib import Path


def parse_sticker_logs(log_file: str) -> dict:
    """Parse sticker logs and group by emoji using regex to find all file IDs."""
    
    with open(log_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    stickers_by_emoji = defaultdict(list)
    seen_file_ids = set()  # Track duplicates
    
    # Find all File ID occurrences
    file_id_pattern = r'File ID:\s*(\S+)'
    file_id_matches = list(re.finditer(file_id_pattern, content))
    
    for match in file_id_matches:
        file_id = match.group(1).strip()
        
        # Skip duplicates
        if file_id in seen_file_ids:
            continue
        seen_file_ids.add(file_id)
        
        # Get the text around this file_id (from match start to next "---" or end)
        start_pos = match.start()
        
        # Find the end of this sticker block (next "---" or end of file)
        next_separator = content.find('---', start_pos)
        if next_separator == -1:
            block = content[start_pos:]
        else:
            block = content[start_pos:next_separator]
        
        # Extract emoji (should be right after File ID)
        emoji_match = re.search(r'Emoji:\s*(.+?)(?:\n|$)', block)
        if not emoji_match:
            continue
        emoji = emoji_match.group(1).strip()
        
        # Extract pack
        pack_match = re.search(r'Pack:\s*(.+?)(?:\n|$)', block)
        pack = pack_match.group(1).strip() if pack_match else "Unknown"
        
        # Extract vibe/note if present (look for "vibe:" in this block only)
        vibe_match = re.search(r'vibe:\s*(.+?)(?:\n\n|---|\Z)', block, re.IGNORECASE | re.DOTALL)
        note = None
        if vibe_match:
            note = vibe_match.group(1).strip()
            # Clean up the note - remove extra whitespace
            note = ' '.join(note.split())
        
        # Build sticker entry
        sticker_entry = {
            "file_id": file_id,
            "pack": pack
        }
        
        if note:
            sticker_entry["note"] = note
        
        # Add to emoji group
        stickers_by_emoji[emoji].append(sticker_entry)
    
    # Convert defaultdict to regular dict and sort
    result = dict(sorted(stickers_by_emoji.items()))
    
    return result


def main():
    """Main function."""
    # Paths
    log_file = Path(__file__).parent.parent / "docs" / "sticker logs.txt"
    output_file = Path(__file__).parent.parent / "config" / "stickers.json"
    
    print(f"Parsing sticker logs from: {log_file}")
    
    # Parse logs
    stickers = parse_sticker_logs(str(log_file))
    
    # Print summary
    print(f"\nFound {len(stickers)} unique emojis:")
    total_stickers = 0
    for emoji, sticker_list in stickers.items():
        count = len(sticker_list)
        total_stickers += count
        print(f"  {emoji}: {count} sticker(s)")
    
    # Write to JSON
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(stickers, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Stickers saved to: {output_file}")
    print(f"Total stickers: {total_stickers}")


if __name__ == "__main__":
    main()

# Made with Bob
