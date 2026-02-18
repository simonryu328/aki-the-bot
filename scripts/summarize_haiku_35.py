
import asyncio
import os
import sys
from sqlalchemy import select

# Add project root to path
sys.path.append(os.getcwd())

from memory.database_async import db
from memory.models import TokenUsage
from config.pricing import calculate_cost

async def summarize_haiku_35_costs():
    model_name = "claude-3-5-haiku-20241022"
    print(f"📊 Summarizing usage for: {model_name}\n")
    
    async with db.get_session() as session:
        stmt = select(TokenUsage).where(TokenUsage.model == model_name)
        result = await session.execute(stmt)
        usages = result.scalars().all()
        
    if not usages:
        print("No usage records found for Claude 3.5 Haiku.")
        return

    total_input = 0
    total_output = 0
    total_cache_read = 0
    total_cache_creation = 0
    total_cost = 0.0
    call_counts = {}

    for u in usages:
        cost = calculate_cost(
            model=u.model,
            input_tokens=u.input_tokens,
            output_tokens=u.output_tokens,
            cache_read_tokens=u.cache_read_tokens or 0,
            cache_creation_tokens=u.cache_creation_tokens or 0
        )
        total_input += u.input_tokens
        total_output += u.output_tokens
        total_cache_read += (u.cache_read_tokens or 0)
        total_cache_creation += (u.cache_creation_tokens or 0)
        total_cost += cost
        
        call_counts[u.call_type] = call_counts.get(u.call_type, 0) + 1

    print(f"📈 TOTAL STATS:")
    print(f"  Calls:          {len(usages)}")
    print(f"  Input Tokens:   {total_input:,}")
    print(f"  Output Tokens:  {total_output:,}")
    print(f"  Cache Read:     {total_cache_read:,}")
    print(f"  Cache Write:    {total_cache_creation:,}")
    print(f"  Total Cost:     ${total_cost:.4f}")
    
    print("\n🏷️ CALL TYPE BREAKDOWN:")
    for c_type, count in call_counts.items():
        print(f"  - {c_type}: {count} calls")

if __name__ == "__main__":
    asyncio.run(summarize_haiku_35_costs())
