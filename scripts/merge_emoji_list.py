#!/usr/bin/env python3
"""
Merge emojis from stickers.json with existing Telegram reactions.
Outputs a deduplicated list for system_frame.py
"""

import json
from pathlib import Path


def main():
    # Read stickers.json
    stickers_file = Path(__file__).parent.parent / "config" / "stickers.json"
    with open(stickers_file, 'r', encoding='utf-8') as f:
        stickers = json.load(f)
    
    # Existing Telegram reactions from system_frame.py
    existing_reactions = [
        '👍', '👎', '❤️', '🔥', '🥰', '👏', '😁', '🤔', '🤯', '😱', 
        '😢', '🎉', '🤩', '🤮', '💩', '🙏', '👌', '🕊', '🤡', '🥱', 
        '🥴', '😍', '🐳', '❤️‍🔥', '🌚', '🌭', '💯', '🤣', '⚡️', '🍌', 
        '🏆', '💔', '🤨', '😐', '🍓', '🍾', '💋', '🖕', '😈', '😴', 
        '😭', '🤓', '👻', '👨‍💻', '👀', '🎃', '🙈', '😇', '😨', '🤝', 
        '✍️', '🤗', '🫡', '🎅', '🎄', '☃️', '💅', '🤪', '🗿', '🆒', 
        '💘', '🙉', '🦄', '😘', '💊', '🙊', '😎', '👾', '🤷‍♂️', '🤷', 
        '🤷‍♀️', '😡'
    ]
    
    # Get sticker emojis
    sticker_emojis = list(stickers.keys())
    
    # Combine and deduplicate
    all_emojis = existing_reactions + sticker_emojis
    unique_emojis = []
    seen = set()
    
    for emoji in all_emojis:
        if emoji not in seen:
            unique_emojis.append(emoji)
            seen.add(emoji)
    
    # Print results
    print(f"Existing reactions: {len(existing_reactions)}")
    print(f"Sticker emojis: {len(sticker_emojis)}")
    print(f"Total unique emojis: {len(unique_emojis)}")
    print(f"Duplicates removed: {len(all_emojis) - len(unique_emojis)}")
    print("\n" + "="*80)
    print("MERGED EMOJI LIST (for system_frame.py):")
    print("="*80)
    
    # Format for system_frame.py (10 emojis per line)
    for i in range(0, len(unique_emojis), 10):
        line = ' '.join(unique_emojis[i:i+10])
        print(line)


if __name__ == "__main__":
    main()

# Made with Bob
