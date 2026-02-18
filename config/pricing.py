from typing import Dict, TypedDict

class ModelPricing(TypedDict):
    input: float
    output: float

# Pricing per 1M tokens
# Sources: 
# OpenAI: https://openai.com/api/pricing/
# Anthropic: https://www.anthropic.com/pricing
# Google: https://ai.google.dev/pricing
MODEL_PRICING: Dict[str, ModelPricing] = {
    # OpenAI
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "o1-mini": {"input": 3.00, "output": 12.00},
    "o1-preview": {"input": 15.00, "output": 60.00},
    
    # Anthropic
    "claude-3-5-sonnet-20240620": {"input": 3.00, "output": 15.00},
    "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00},
    "claude-3-haiku-20240307": {"input": 0.25, "output": 1.25},
    "claude-3-opus-20240229": {"input": 15.00, "output": 75.00},
    
    # Google
    "gemini-1.5-flash": {"input": 0.075, "output": 0.30},
    "gemini-1.5-pro": {"input": 1.25, "output": 5.00},
    
    # Default fallback
    "default": {"input": 0.50, "output": 1.50},
}

def get_model_pricing(model_name: str) -> ModelPricing:
    """Get pricing for a specific model, handling provider prefixes."""
    # Strip potential provider prefixes (e.g., "anthropic/claude...", "openai/gpt...")
    clean_name = model_name.split("/")[-1]
    
    # Direct match
    if clean_name in MODEL_PRICING:
        return MODEL_PRICING[clean_name]
    
    # Fallback for versioned models (e.g. gpt-4o-2024-05-13 -> gpt-4o)
    for key in MODEL_PRICING:
        if key in clean_name:
            return MODEL_PRICING[key]
            
    return MODEL_PRICING["default"]

def calculate_cost(
    model: str, 
    input_tokens: int, 
    output_tokens: int,
    cache_read_tokens: int = 0,
    cache_creation_tokens: int = 0
) -> float:
    """
    Calculate estimated cost for a transaction.
    
    Handles standard tokens and Anthropic Prompt Caching (if applicable).
    
    Anthropic Caching Pricing (approximate multipliers):
    - Cache Write: ~1.25x base input price
    - Cache Read: ~0.1x base input price
    """
    pricing = get_model_pricing(model)
    
    # 1. Standard Input Cost
    # If using caching, 'input_tokens' usually excludes cached tokens, but logic depends on provider.
    # We assume 'input_tokens' passed here are the raw non-cached input tokens.
    cost_input = (input_tokens / 1_000_000) * pricing["input"]
    
    # 2. Output Cost
    cost_output = (output_tokens / 1_000_000) * pricing["output"]
    
    # 3. Cache Costs (Anthropic specific mostly)
    cost_cache_write = (cache_creation_tokens / 1_000_000) * (pricing["input"] * 1.25)
    cost_cache_read = (cache_read_tokens / 1_000_000) * (pricing["input"] * 0.1)
    
    return cost_input + cost_output + cost_cache_write + cost_cache_read
