#!/usr/bin/env python3
"""
Test script for Level 3 "Life Story" compaction.
Reads the first 3 chapters from the generated memory-only output for Simon
and generates a distilled narrative in Aki's voice.
"""
import asyncio
import sys
import re
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import settings
from utils.llm_client import llm_client
from prompts.life_story import LIFE_STORY_PROMPT

async def main():
    user_name = "Simon"
    input_file = Path(__file__).parent.parent / "docs" / "chapter_output_memory_only.txt"
    
    if not input_file.exists():
        print(f"Error: {input_file} not found.")
        return

    content = input_file.read_text(encoding="utf-8")
    
    # Simple regex to split by chapter headers
    # The header is: ============================================================ (line)
    #               Chapter N (...)
    #               ============================================================ (line)
    
    # We want to catch the start of a chapter
    blocks = re.split(r'={20,}\s+Chapter \d+', content)
    
    # block[0] is everything before Chapter 1
    # block[1] is Chapter 1 (including the trailing ==== separator and date range)
    # Let's clean up block 1-3
    
    chapters = []
    for i in range(1, 4): # first 3 chapters
        if i < len(blocks):
            # The split takes away the "Chapter N" part, and the next line is "===== (date range) ====="
            # We need to clean the leading separator
            raw_block = blocks[i]
            # Remove the second separator and date range line
            cleaned = re.sub(r'^.*?={20,}', '', raw_block, flags=re.DOTALL).strip()
            chapters.append(f"CHAPTER {i}:\n{cleaned}")

    if not chapters:
        print("No chapters found to process.")
        return

    full_chapters_text = "\n\n".join(chapters)
    
    print(f"--- Processing {len(chapters)} Chapters ---\n")
    # print(full_chapters_text[:500] + "...") # Debug

    prompt = LIFE_STORY_PROMPT.format(
        user_name=user_name,
        chapters=full_chapters_text
    )

    print("⏳ Generating Life Story (Aki's Voice)...")
    try:
        response = await llm_client.chat(
            model=settings.MODEL_MEMORY,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=1000,
        )
        
        print(f"\n{'#'*60}")
        print(f"# LIFE STORY: {user_name}")
        print(f"{'#'*60}\n")
        print(response.strip())
        print(f"\n{'#'*60}")
        
        # Save to file
        output_file = Path(__file__).parent.parent / "docs" / "life_story_test_simon.txt"
        output_file.write_text(response.strip(), encoding="utf-8")
        print(f"\nOutput saved to {output_file}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
