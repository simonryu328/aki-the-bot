#!/usr/bin/env python3
"""
Interactive tool to map stickers to available Telegram reaction emojis.

This tool:
1. Parses sticker logs
2. Identifies emojis that are NOT in the available reactions list
3. Lets you interactively assign them to available reaction emojis
4. Generates stickers.json with proper mappings
"""

import re
import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set

# Available Telegram reaction emojis (from system_frame.py)
AVAILABLE_REACTIONS = [
    "👍", "👎", "❤️", "🔥", "🥰", "👏", "😁", "🤔", "🤯", "😱", 
    "😢", "🎉", "🤩", "🤮", "💩", "🙏", "👌", "🕊", "🤡", "🥱", 
    "🥴", "😍", "🐳", "❤️‍🔥", "🌚", "🌭", "💯", "🤣", "⚡️", "🍌", 
    "🏆", "💔", "🤨", "😐", "🍓", "🍾", "💋", "🖕", "😈", "😴", 
    "😭", "🤓", "👻", "👨‍💻", "👀", "🎃", "🙈", "😇", "😨", "🤝", 
    "✍️", "🤗", "🫡", "🎅", "🎄", "☃️", "💅", "🤪", "🗿", "🆒", 
    "💘", "🙉", "🦄", "😘", "💊", "🙊", "😎", "👾", "🤷‍♂️", "🤷", 
    "🤷‍♀️", "😡"
]


def parse_sticker_logs(log_file: str) -> List[Dict]:
    """Parse sticker logs and return list of sticker entries."""
    
    with open(log_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    entries = re.split(r'\n---+\n', content)
    stickers = []
    
    for entry in entries:
        file_id_match = re.search(r'File ID:\s*(\S+)', entry)
        if not file_id_match:
            continue
        file_id = file_id_match.group(1)
        
        emoji_match = re.search(r'Emoji:\s*(.+?)(?:\n|$)', entry)
        if not emoji_match:
            continue
        emoji = emoji_match.group(1).strip()
        
        pack_match = re.search(r'Pack:\s*(.+?)(?:\n|$)', entry)
        pack = pack_match.group(1).strip() if pack_match else "Unknown"
        
        vibe_match = re.search(r'vibe:\s*(.+?)(?:\n|---|$)', entry, re.IGNORECASE)
        note = vibe_match.group(1).strip() if vibe_match else None
        
        stickers.append({
            "file_id": file_id,
            "emoji": emoji,
            "pack": pack,
            "note": note
        })
    
    return stickers


def categorize_stickers(stickers: List[Dict]) -> tuple[List[Dict], List[Dict]]:
    """Categorize stickers into matched and unmatched."""
    matched = []
    unmatched = []
    
    for sticker in stickers:
        if sticker["emoji"] in AVAILABLE_REACTIONS:
            matched.append(sticker)
        else:
            unmatched.append(sticker)
    
    return matched, unmatched


def display_available_reactions():
    """Display available reactions in a grid."""
    print("\n" + "="*80)
    print("AVAILABLE TELEGRAM REACTIONS:")
    print("="*80)
    
    # Display in rows of 10
    for i in range(0, len(AVAILABLE_REACTIONS), 10):
        row = AVAILABLE_REACTIONS[i:i+10]
        print("  " + "  ".join(f"{j+i+1:2d}. {emoji}" for j, emoji in enumerate(row)))
    
    print("="*80 + "\n")


def interactive_mapping(unmatched: List[Dict]) -> Dict[str, str]:
    """Interactively map unmatched emojis to available reactions."""
    
    if not unmatched:
        print("✅ All sticker emojis are already in the available reactions list!")
        return {}
    
    print(f"\n🔍 Found {len(unmatched)} stickers with emojis NOT in the reactions list:\n")
    
    # Group by emoji
    by_emoji = defaultdict(list)
    for sticker in unmatched:
        by_emoji[sticker["emoji"]].append(sticker)
    
    mappings = {}
    
    for emoji, sticker_list in by_emoji.items():
        print(f"\n{'='*80}")
        print(f"Emoji: {emoji} ({len(sticker_list)} sticker(s))")
        print(f"{'='*80}")
        
        # Show sticker details
        for i, sticker in enumerate(sticker_list, 1):
            print(f"  {i}. Pack: {sticker['pack']}")
            if sticker['note']:
                print(f"     Note: {sticker['note']}")
        
        display_available_reactions()
        
        while True:
            choice = input(f"Map '{emoji}' to which reaction? (number 1-{len(AVAILABLE_REACTIONS)}, or 's' to skip): ").strip().lower()
            
            if choice == 's':
                print(f"⏭️  Skipped {emoji}")
                break
            
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(AVAILABLE_REACTIONS):
                    target_emoji = AVAILABLE_REACTIONS[idx]
                    mappings[emoji] = target_emoji
                    print(f"✅ Mapped {emoji} → {target_emoji}")
                    break
                else:
                    print(f"❌ Invalid number. Please enter 1-{len(AVAILABLE_REACTIONS)}")
            except ValueError:
                print("❌ Invalid input. Please enter a number or 's' to skip")
    
    return mappings


def generate_stickers_json(stickers: List[Dict], mappings: Dict[str, str]) -> Dict:
    """Generate the final stickers.json structure with deduplication."""
    
    result = defaultdict(list)
    seen_file_ids = defaultdict(set)  # Track file_ids per emoji to avoid duplicates
    
    for sticker in stickers:
        original_emoji = sticker["emoji"]
        
        # Use mapping if available, otherwise use original emoji
        target_emoji = mappings.get(original_emoji, original_emoji)
        
        # Only include if target emoji is in available reactions
        if target_emoji in AVAILABLE_REACTIONS:
            file_id = sticker["file_id"]
            
            # Skip if we've already seen this file_id for this emoji
            if file_id in seen_file_ids[target_emoji]:
                continue
            
            seen_file_ids[target_emoji].add(file_id)
            
            entry = {
                "file_id": file_id,
                "pack": sticker["pack"]
            }
            
            if sticker["note"]:
                entry["note"] = sticker["note"]
            
            result[target_emoji].append(entry)
    
    return dict(sorted(result.items()))


def main():
    """Main function."""
    log_file = Path(__file__).parent.parent / "docs" / "sticker logs.txt"
    output_file = Path(__file__).parent.parent / "config" / "stickers.json"
    
    print("🎨 Interactive Sticker Mapper")
    print("="*80)
    print(f"Reading from: {log_file}")
    
    # Parse logs
    all_stickers = parse_sticker_logs(str(log_file))
    
    # Deduplicate by file_id
    seen_ids = set()
    stickers = []
    duplicates = 0
    
    for sticker in all_stickers:
        if sticker["file_id"] not in seen_ids:
            seen_ids.add(sticker["file_id"])
            stickers.append(sticker)
        else:
            duplicates += 1
    
    print(f"📊 Found {len(all_stickers)} total sticker entries")
    if duplicates > 0:
        print(f"🔄 Removed {duplicates} duplicate(s)")
    print(f"✨ {len(stickers)} unique stickers")
    
    # Categorize
    matched, unmatched = categorize_stickers(stickers)
    print(f"✅ {len(matched)} stickers with matching emojis")
    print(f"⚠️  {len(unmatched)} stickers need mapping")
    
    # Interactive mapping
    mappings = interactive_mapping(unmatched)
    
    # Generate JSON
    result = generate_stickers_json(stickers, mappings)
    
    # Summary
    print("\n" + "="*80)
    print("📋 SUMMARY")
    print("="*80)
    print(f"Total reaction emojis with stickers: {len(result)}")
    for emoji, sticker_list in result.items():
        print(f"  {emoji}: {len(sticker_list)} sticker(s)")
    
    # Save
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Stickers saved to: {output_file}")
    print(f"Total stickers mapped: {sum(len(v) for v in result.values())}")
    
    if mappings:
        print(f"\n🔄 Applied {len(mappings)} custom mapping(s):")
        for orig, target in mappings.items():
            print(f"  {orig} → {target}")


if __name__ == "__main__":
    main()

# Made with Bob
