"""
Soul Agent - The core conversational agent.

Copyright 2026 Simon Ryu. Licensed under Apache 2.0.

This module implements proprietary algorithms including:
- Multi-stage processing with thinking/observation/reflection layers
- Time-windowed compact summarization with exchange tracking
- Context-aware response generation with smart message splitting

Accepts a swappable persona to define personality and behavior.
Inspired by soul.md: listens for what's beneath the words,
recognizes weight, and holds the story.
"""

import asyncio
from typing import List, Dict, Optional
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
import re
import hashlib
import pytz
import dateparser

from utils.llm_client import llm_client, LLMResponse
from config.settings import settings
from memory.memory_manager_async import memory_manager
from schemas import ConversationSchema, UserContextSchema, UserSchema
from core import get_logger
from prompts import (
    REFLECTION_PROMPT,
    COMPACT_PROMPT,
    MEMORY_PROMPT,
    DAILY_MESSAGE_PROMPT,
    FALLBACK_QUOTES,
)
from prompts.personalized_insights import PERSONALIZED_INSIGHTS_PROMPT
from prompts.spotify_dj import SPOTIFY_DJ_PROMPT
from utils.spotify_manager import spotify_manager
import json
from prompts.system_frame import SYSTEM_FRAME
from prompts.personas import COMPANION_PERSONA

logger = get_logger(__name__)


@dataclass
class SoulResponse:
    """Response from the companion agent."""
    response: str  # Full response (for storage)
    messages: List[str] = None  # Split messages (for sending)
    thinking: Optional[str] = None
    observations: Optional[List[str]] = None
    emoji: Optional[str] = None  # Reaction emoji
    usage: Optional[LLMResponse] = None  # Token usage from the LLM call

    def __post_init__(self):
        if self.messages is None:
            self.messages = [self.response]


class SoulAgent:
    """
    A companion who witnesses someone's story.

    Not an assistant. Not a chatbot. A presence that listens,
    understands, and remembers what matters.
    """

    # Store last thinking, prompts, and context per user for debugging
    _last_thinking: Dict[int, str] = {}
    _last_system_prompt: Dict[int, str] = {}
    _last_observation_prompt: Dict[int, str] = {}
    _last_compact_prompt: Dict[int, str] = {}
    _last_profile_context: Dict[int, str] = {}
    _last_raw_response: Dict[int, str] = {}  # Store raw LLM response before parsing
    _message_count: Dict[int, int] = {}
    _reaction_counter: Dict[int, int] = {}  # Track messages until next reaction
    
    # In-memory formatted string caches (user_id -> string)
    _observations_cache: Dict[int, str] = {}
    _profile_string_cache: Dict[int, str] = {}
    _last_recent_exchanges: Dict[int, str] = {}

    def __init__(self, model: str = settings.MODEL_CONVERSATION, persona: str = COMPANION_PERSONA):
        """Initialize companion agent.

        Args:
            model: LLM model to use.
            persona: The personality prompt to slot into the system frame.
        """
        self.model = model
        self.persona = persona
        self.memory = memory_manager

    async def _get_user_tz(self, user_id: int, user: Optional['UserSchema'] = None) -> str:
        """Get the IANA timezone string for a user, falling back to settings.TIMEZONE.
        
        Args:
            user_id: User ID
            user: Pre-fetched user object (optional)
            
        Returns:
            IANA timezone string (e.g. 'America/New_York')
        """
        if user and getattr(user, 'timezone', None):
            return user.timezone
        fetched = await self.memory.get_user_by_id(user_id)
        if fetched and getattr(fetched, 'timezone', None):
            return fetched.timezone
        return settings.TIMEZONE

    async def respond(
        self,
        user_id: int,
        message: str,
        context: UserContextSchema,
        conversation_history: List[ConversationSchema],
        user: Optional['UserSchema'] = None,
    ) -> SoulResponse:
        """
        Respond to a message as a companion.

        Args:
            user_id: User ID
            message: What they said
            context: Their profile and context
            conversation_history: Recent conversation
            user: Pre-fetched user object

        Returns:
            SoulResponse with response, thinking
        """
        # Resolve user name and context
        if user is None:
            user = await self.memory.get_user_by_id(user_id)
        user_name = user.name if user and user.name else "them"

        # Fetch conversation context
        recent_exchanges_text, history_text = await self._build_conversation_context(user_id, conversation_history, user)
        
        # Build time context using user's timezone
        user_tz_str = await self._get_user_tz(user_id, user)
        now = datetime.now(pytz.timezone(user_tz_str))
        current_time = now.strftime("%A, %B %d at %I:%M %p")
        hour = now.hour
        if 5 <= hour < 12:
            time_context = "It's morning."
        elif 12 <= hour < 17:
            time_context = "It's afternoon."
        elif 17 <= hour < 21:
            time_context = "It's evening."
        else:
            time_context = "It's late night."

        # Assemble system prompt from frame + persona
        from prompts.system_frame import SYSTEM_STATIC, SYSTEM_DYNAMIC
        
        # 1. Static part (Persona + Format)
        # Allow persona to use {user_name} via .format()
        try:
            formatted_persona = self.persona.format(user_name=user_name)
        except (KeyError, ValueError):
            formatted_persona = self.persona
            
        static_text = SYSTEM_STATIC.format(persona=formatted_persona)
        
        # 2. Dynamic part - Split into Semi-Static (Exchanges) and Volatile (History/Time)
        # We place RECENT EXCHANGES in its own block so it can be cached independently
        # and doesn't get invalidated by the clock.
        exchanges_block = f"\n---\n\nRECENT EXCHANGES:\n{recent_exchanges_text}"
        volatile_block = f"\n---\n\nCURRENT CONVERSATION:\n{history_text}\n\n---\n\nRIGHT NOW:\n{current_time}. {time_context}"
        
        # Update debug context
        SoulAgent._last_system_prompt[user_id] = static_text + exchanges_block + volatile_block
        SoulAgent._last_recent_exchanges[user_id] = recent_exchanges_text

        # Create list-based system prompt for caching support
        # We use 2 out of 4 available cache breakpoints
        system_prompt_blocks = [
            {
                "type": "text",
                "text": static_text,
                "cache_control": {"type": "ephemeral"} # 1st Breakpoint: Persona/Format
            },
            {
                "type": "text",
                "text": exchanges_block,
                "cache_control": {"type": "ephemeral"} # 2nd Breakpoint: Summaries/Memories
            },
            {
                "type": "text",
                "text": volatile_block
            }
        ]

        llm_response = await llm_client.chat_with_system_and_usage(
            model=self.model,
            system_prompt=system_prompt_blocks,
            user_message=message,
            temperature=0.7,
            max_tokens=1000,
        )
        raw_response = llm_response.content
        
        # Store raw response for debug
        SoulAgent._last_raw_response[user_id] = raw_response
        
        # Log response and savings
        log_func = logger.info if settings.LOG_RAW_LLM else logger.debug
        
        cache_msg = ""
        if llm_response and llm_response.cache_read_tokens > 0:
            savings = llm_response.cache_read_tokens
            cache_msg = f" | ⚡ CACHE HIT: {savings} tokens saved"
        elif llm_response and llm_response.cache_creation_tokens > 0:
            cache_msg = f" | 🆕 CACHE CREATED: {llm_response.cache_creation_tokens} tokens"

        logger.info(
            f"Response generated{cache_msg}",
            user_id=user_id,
            tokens=llm_response.total_tokens if llm_response else 0,
        )

        # Parse thinking, response, messages, and emoji
        thinking, response, messages, emoji = self._parse_response(raw_response)
        
        # Store thinking for debug
        SoulAgent._last_thinking[user_id] = thinking or "(no thinking captured)"

        # Determine if we should trigger reaction this time
        should_react = self._should_trigger_reaction(user_id)

        result = SoulResponse(
            response=response,
            messages=messages,
            thinking=thinking,
            emoji=emoji,  # Always include emoji for stickers (reactions are filtered in telegram_handler)
            usage=llm_response,
        )

        # Background: Create compact summary logic
        asyncio.create_task(
            self._maybe_create_compact_summary(
                user_id=user_id,
                conversation_history=conversation_history,
            )
        )

        return result

    async def _build_conversation_context(
        self,
        user_id: int,
        conversation_history: List[ConversationSchema],
        user: Optional[UserSchema] = None,
    ) -> tuple[str, str]:
        """Build recent exchanges and current conversation context.
        
        Always includes:
        - Most recent N memory entries (RECENT EXCHANGES)
        - Most recent M raw messages (CURRENT CONVERSATION)
        
        This provides both high-level context from memory entries and detailed recent context
        from raw messages, regardless of overlap.
        
        Args:
            user_id: User ID
            conversation_history: Recent conversation messages
            user: Pre-fetched user object (optional, will fetch if not provided)
            
        Returns:
            Tuple of (recent_exchanges_text, current_conversation_text)
        """
        # Resolve user timezone
        if user is None:
            user = await self.memory.get_user_by_id(user_id)
        user_tz_str = await self._get_user_tz(user_id, user)
        tz = pytz.timezone(user_tz_str)
        
        # Get diary entries to pick from
        diary_entries = await self.memory.get_diary_entries(user_id, limit=settings.DIARY_FETCH_LIMIT)
        
        # Filter into pools (diary_entries is newest first)
        all_memories = [e for e in diary_entries if e.entry_type == 'conversation_memory']
        all_summaries = [e for e in diary_entries if e.entry_type == 'compact_summary']
        
        # 1. Take up to 2 most recent summaries (Ranges 1 and 2)
        summary_entries = all_summaries[:settings.COMPACT_SUMMARY_LIMIT]
        
        # 2. Determine cutoff: the earliest point covered by selected summaries
        cutoff = None
        if summary_entries:
            oldest_summary = summary_entries[-1]
            cutoff = oldest_summary.exchange_start or oldest_summary.timestamp
            
        # 3. Take up to 2 most recent memories that are OLDER than the summaries (Ranges 3 and 4)
        if cutoff:
            # We look for memories where the entire exchange ended before our cutoff
            memory_entries = [m for m in all_memories if (m.exchange_end or m.timestamp) <= cutoff][:settings.MEMORY_ENTRY_LIMIT]
        else:
            # Fallback if no summaries are found
            memory_entries = all_memories[:settings.MEMORY_ENTRY_LIMIT]
        
        # We want prompt order: [Oldest Memory, Newer Memory, Oldest Summary, Newer Summary] (Ranges 4, 3, 2, 1)
        context_items = []
        
        def format_recent_entry(entry):
            """Helper to format a memory or summary entry with timestamps."""
            if entry.exchange_start and entry.exchange_end:
                start_utc = entry.exchange_start.replace(tzinfo=pytz.utc)
                end_utc = entry.exchange_end.replace(tzinfo=pytz.utc)
                start_local = start_utc.astimezone(tz)
                end_local = end_utc.astimezone(tz)
                
                # Format: [Jan 15, 10:30 AM - 11:45 AM] content
                start_str = start_local.strftime("%b %d, %I:%M %p")
                end_str = end_local.strftime("%I:%M %p")
                return f"[{start_str} - {end_str}] {entry.content}"
            else:
                # Fallback for entries without exchange timestamps
                entry_utc = entry.timestamp.replace(tzinfo=pytz.utc)
                entry_local = entry_utc.astimezone(tz)
                ts_str = entry_local.strftime("%b %d, %I:%M %p")
                return f"[{ts_str}] {entry.content}"

        # Add memory entries first (ordered oldest to newest)
        for memory in reversed(memory_entries):
            context_items.append(format_recent_entry(memory))
            
        # Add summary entries next (ordered oldest to newest)
        for summary in reversed(summary_entries):
            context_items.append(format_recent_entry(summary))
        
        if context_items:
            recent_exchanges_text = "\n".join(context_items)
        else:
            # No entries yet, show placeholder
            recent_exchanges_text = "(No previous exchanges remembered yet)"
        
        # 4. Optimized History Slicing (Current Conversation)
        # We only want to show raw messages that aren't already covered by a summary.
        if summary_entries:
            latest_summary = summary_entries[0]
            # summary_end is the timestamp of the last message included in that summary
            summary_end = latest_summary.exchange_end or latest_summary.timestamp
            
            # Filter history: 1. Everything after summary + 2. Small "glue" overlap (3 msgs)
            after_summary = []
            overlap = []
            
            # conversation_history is chronological (oldest to newest)
            # We iterate backwards to pick newest first
            for conv in reversed(conversation_history):
                conv_ts = conv.timestamp.replace(tzinfo=None) if conv.timestamp else datetime.utcnow()
                sum_ts = summary_end.replace(tzinfo=None)
                
                if conv_ts > sum_ts:
                    after_summary.append(conv)
                elif len(overlap) < 3: # Keep 3 messages for conversational "glue"
                    overlap.append(conv)
                else:
                    break
            
            # Combine and restore chronological order
            current_convos = list(reversed(after_summary + overlap))
            
            # Safety: if for some reason the above returns nothing, fallback
            if not current_convos:
                current_convos = conversation_history[:settings.CONVERSATION_CONTEXT_LIMIT]
        else:
            # Fallback for new users with no summaries yet
            current_convos = conversation_history[:settings.CONVERSATION_CONTEXT_LIMIT]
        
        # Get user name for formatting - use pre-fetched user if available
        if user is None:
            user = await self.memory.get_user_by_id(user_id)
        user_name = user.name if user and user.name else "them"
        
        # Format current conversation
        current_conversation_text = self._format_history(current_convos, user_name, tz_str=user_tz_str)
        
        return recent_exchanges_text, current_conversation_text


    def _format_history(self, conversations: List[ConversationSchema], user_name: str = "them", tz_str: str = None) -> str:
        """Format conversation history with timestamps converted to local time."""
        if not conversations:
            return "(This is the beginning of your conversation.)"

        tz = pytz.timezone(tz_str or settings.TIMEZONE)
        lines = []
        for conv in conversations:
            role = user_name if conv.role == "user" else "Aki"
            if conv.timestamp:
                utc_time = conv.timestamp.replace(tzinfo=pytz.utc)
                local_time = utc_time.astimezone(tz)
                ts = local_time.strftime("%Y-%m-%d %H:%M")
            else:
                ts = ""
            lines.append(f"[{ts}] {role}: {conv.message}")

        return "\n".join(lines)

    def _should_trigger_reaction(self, user_id: int) -> bool:
        """Determine if we should trigger a reaction for this message.
        
        Uses a counter that increments each message. When counter reaches
        a random value between MIN and MAX, trigger reaction and reset.
        """
        import random
        
        # Initialize counter if not exists
        if user_id not in SoulAgent._reaction_counter:
            # Set initial target (random between min and max)
            target = random.randint(
                settings.REACTION_MIN_MESSAGES,
                settings.REACTION_MAX_MESSAGES
            )
            SoulAgent._reaction_counter[user_id] = target
        
        # Decrement counter
        SoulAgent._reaction_counter[user_id] -= 1
        
        # Check if we should trigger
        if SoulAgent._reaction_counter[user_id] <= 0:
            # Reset with new random target
            target = random.randint(
                settings.REACTION_MIN_MESSAGES,
                settings.REACTION_MAX_MESSAGES
            )
            SoulAgent._reaction_counter[user_id] = target
            return True
        
        return False

    def _parse_response(self, raw: str) -> tuple[Optional[str], str, List[str], Optional[str]]:
        """Parse thinking, response, messages, and emoji from raw LLM output.
        
        Supports multiple formats:
        1. XML strict: <?xml version="1.0"?><message>...</message>
        2. Legacy XML tags: <thinking>, <emoji>, <response>
        3. [BREAK] markers: "text[BREAK]more text[BREAK]even more"
        4. Fallback: Plain text or ||| separator
        5. Auto-split: Long responses split intelligently
        """
        thinking = None
        emoji = None
        response = raw

        # Try XML strict format first (new format)
        xml_match = re.search(r'<\?xml version="1\.0"\?>\s*<message>(.*?)</message>', raw, re.DOTALL)
        if xml_match:
            message_content = xml_match.group(1)
            
            # Extract thinking from XML
            thinking_match = re.search(r'<thinking>(.*?)</thinking>', message_content, re.DOTALL)
            if thinking_match:
                thinking = thinking_match.group(1).strip()
            
            # Extract emoji from XML
            emoji_match = re.search(r'<emoji>(.*?)</emoji>', message_content, re.DOTALL)
            if emoji_match:
                emoji = emoji_match.group(1).strip()
            
            # Extract response from XML
            response_match = re.search(r'<response>(.*?)</response>', message_content, re.DOTALL)
            if response_match:
                response_content = response_match.group(1).strip()
                
                # Check for [BREAK] markers
                if '[BREAK]' in response_content:
                    messages = [msg.strip() for msg in response_content.split('[BREAK]') if msg.strip()]
                else:
                    messages = [response_content]
            else:
                messages = [""]
        else:
            # Fall back to legacy format parsing
            # Extract thinking
            thinking_match = re.search(r'<thinking>(.*?)</thinking>', raw, re.DOTALL)
            if thinking_match:
                thinking = thinking_match.group(1).strip()
                # Remove thinking from response
                response = re.sub(r'<thinking>.*?</thinking>', '', raw, flags=re.DOTALL).strip()

            # Extract emoji
            emoji_match = re.search(r'<emoji>(.*?)</emoji>', response, re.DOTALL)
            if emoji_match:
                emoji = emoji_match.group(1).strip()
                # Remove emoji tag from response
                response = re.sub(r'<emoji>.*?</emoji>', '', response, flags=re.DOTALL).strip()

            # Try to extract structured <response> tag first
            response_match = re.search(r'<response>(.*?)</response>', response, re.DOTALL)
            if response_match:
                response_content = response_match.group(1).strip()
                
                # Check for [BREAK] markers within <response>
                if '[BREAK]' in response_content:
                    messages = [msg.strip() for msg in response_content.split('[BREAK]') if msg.strip()]
                # Check for <message> tags
                elif '<message>' in response_content:
                    message_matches = re.findall(r'<message>(.*?)</message>', response_content, re.DOTALL)
                    messages = [msg.strip() for msg in message_matches if msg.strip()]
                else:
                    # Single message in <response> tag
                    messages = [response_content]
            # Handle unclosed <response> tag (LLM didn't close it properly)
            elif response.startswith('<response>'):
                # Extract everything after <response> tag
                response_content = response[len('<response>'):].strip()
                
                # Check for [BREAK] markers
                if '[BREAK]' in response_content:
                    messages = [msg.strip() for msg in response_content.split('[BREAK]') if msg.strip()]
                else:
                    messages = [response_content]
            else:
                # No <response> tag - check for [BREAK] markers in raw response
                if '[BREAK]' in response:
                    messages = [msg.strip() for msg in response.split('[BREAK]') if msg.strip()]
                # Fallback: check for ||| separator
                elif '|||' in response:
                    messages = [msg.strip() for msg in response.split('|||') if msg.strip()]
                else:
                    # Remove any stray tags and use as-is
                    clean_response = re.sub(r'</?(?:response|message)>', '', response).strip()
                    messages = [clean_response] if clean_response else [response.strip()]
        
        # Auto-split long single messages (fallback for when LLM doesn't use markers)
        if len(messages) == 1 and len(messages[0]) > settings.AUTO_SPLIT_THRESHOLD:
            messages = self._smart_split_message(messages[0])

        # Full response for storage (join with newlines)
        full_response = '\n'.join(messages)

        return thinking, full_response, messages, emoji
    
    def _smart_split_message(self, text: str, max_length: int = None) -> List[str]:
        """Intelligently split a long message into natural chunks.
        
        Splits on:
        - Sentence boundaries (. ! ?)
        - Line breaks
        - Natural pauses (emoji followed by text)
        """
        if max_length is None:
            max_length = settings.SMART_SPLIT_MAX_LENGTH
            
        # If short enough, return as-is
        if len(text) <= max_length:
            return [text]
        
        messages = []
        
        # First try splitting on double line breaks (paragraph breaks)
        paragraphs = text.split('\n\n')
        if len(paragraphs) > 1:
            current = ""
            for para in paragraphs:
                if len(current) + len(para) > max_length and current:
                    messages.append(current.strip())
                    current = para
                else:
                    current = current + '\n\n' + para if current else para
            if current:
                messages.append(current.strip())
            return messages
        
        # Fall back to sentence splitting
        sentences = re.split(r'([.!?]+\s+)', text)
        current = ""
        
        for i in range(0, len(sentences), 2):
            sentence = sentences[i]
            punctuation = sentences[i + 1] if i + 1 < len(sentences) else ""
            full_sentence = sentence + punctuation
            
            if len(current) + len(full_sentence) > max_length and current:
                messages.append(current.strip())
                current = full_sentence
            else:
                current += full_sentence
        
        if current:
            messages.append(current.strip())
        
        return messages if messages else [text]

    def _parse_when_to_datetime(self, when: str) -> datetime:
        """Convert a 'when' string to a naive datetime object (for database storage).

        Tries in order:
        1. ISO 8601 format (YYYY-MM-DDTHH:MM)
        2. Natural language via dateparser
        3. Legacy hardcoded options (tomorrow_morning, etc.)
        4. Default to 24 hours from now
        """
        tz = pytz.timezone(settings.TIMEZONE)
        now = datetime.now(tz)
        when_stripped = when.strip()
        when_lower = when_stripped.lower()

        # 1. Try ISO 8601 format first (e.g., 2026-02-05T10:00)
        try:
            # Try with time
            if 'T' in when_stripped:
                parsed = datetime.fromisoformat(when_stripped)
                # If no timezone, assume local timezone
                if parsed.tzinfo is None:
                    parsed = tz.localize(parsed)
                logger.debug("Parsed ISO timestamp", when=when_stripped, result=parsed.isoformat())
                return parsed.replace(tzinfo=None)
        except ValueError:
            pass

        # 2. Try dateparser for natural language (e.g., "tomorrow at 10am", "in 3 hours")
        try:
            parsed = dateparser.parse(
                when_stripped,
                settings={
                    'TIMEZONE': settings.TIMEZONE,
                    'RETURN_AS_TIMEZONE_AWARE': True,
                    'PREFER_DATES_FROM': 'future',
                }
            )
            if parsed:
                logger.debug("Parsed natural language time", when=when_stripped, result=parsed.isoformat())
                return parsed.replace(tzinfo=None)
        except Exception as e:
            logger.debug("dateparser failed", when=when_stripped, error=str(e))

        # 3. Legacy hardcoded options (for backwards compatibility)
        if when_lower == "tomorrow_morning":
            target = now.replace(hour=9, minute=0, second=0, microsecond=0)
            if now.hour >= 9:
                target = target + timedelta(days=1)
        elif when_lower == "tomorrow_evening":
            target = now.replace(hour=19, minute=0, second=0, microsecond=0)
            if now.hour >= 19:
                target = target + timedelta(days=1)
        elif when_lower == "in_24h":
            target = now + timedelta(hours=24)
        elif when_lower == "in_few_days":
            target = now + timedelta(days=3)
        elif when_lower == "next_week":
            target = now + timedelta(days=7)
        else:
            # 4. Default to 24 hours from now
            logger.warning("Could not parse time, defaulting to 24h", when=when_stripped)
            target = now + timedelta(hours=24)

        return target.replace(tzinfo=None)

    async def _maybe_create_compact_summary(
        self,
        user_id: int,
        conversation_history: Optional[List[ConversationSchema]] = None,
    ) -> None:
        """Check if compact summary should be created based on database count.
        
        This replaces the in-memory counter with a database-based check,
        making it restart-proof.
        
        Args:
            user_id: User ID
            conversation_history: Pre-fetched conversation history (optional, will fetch if not provided)
        """
        try:
            # 1. Get last compact timestamp
            diary_entries = await self.memory.get_diary_entries(user_id, limit=settings.DIARY_FETCH_LIMIT)
            last_compact = None
            for entry in diary_entries:
                if entry.entry_type == 'compact_summary':
                    last_compact = entry.timestamp
                    break
            
            # 2. Fetch conversations to check threshold - ignore passed history for checking
            # because orchestrator only passes CONVERSATION_CONTEXT_LIMIT (20), which is
            # lower than COMPACT_INTERVAL (30), causing triggers to never fire.
            threshold = max(settings.COMPACT_INTERVAL, settings.MEMORY_ENTRY_INTERVAL)
            
            if last_compact:
                # Fetch messages after last compact with enough limit to hit threshold
                all_convos = await self.memory.db.get_conversations_after(
                    user_id, last_compact, limit=max(100, threshold + 10)
                )
            else:
                # No compact exists, fetch recent history
                all_convos = await self.memory.db.get_recent_conversations(
                    user_id, limit=max(100, threshold + 10)
                )
                
            message_count = len(all_convos)
            
            # Bundle background tasks
            tasks = []
            
            # Trigger compact summary if we have enough messages
            if message_count >= settings.COMPACT_INTERVAL:
                logger.info("Triggering compact summary", user_id=user_id, message_count=message_count)
                tasks.append(self._create_compact_summary(user_id=user_id, conversation_history=all_convos))
            
            # Trigger memory entry if we have enough messages (can be different threshold)
            if message_count >= settings.MEMORY_ENTRY_INTERVAL:
                logger.info("Triggering memory entry", user_id=user_id, message_count=message_count)
                tasks.append(self._create_memory_entry(user_id=user_id, conversation_history=all_convos))
            
            if tasks:
                await asyncio.gather(*tasks)
            
        except Exception as e:
            logger.error("Failed to check compact trigger", user_id=user_id, error=str(e))

    async def _create_compact_summary(
        self,
        user_id: int,
        conversation_history: Optional[List[ConversationSchema]] = None,
    ) -> None:
        """Create a compact summary of recent message exchanges.
        
        Args:
            user_id: User ID
            conversation_history: Pre-fetched conversation history (optional, will fetch if not provided)
        """
        logger.info("Running compact summarization", user_id=user_id)
        try:
            # Get user name and timezone
            user = await self.memory.get_user_by_id(user_id)
            user_name = user.name if user and user.name else "them"
            user_tz_str = await self._get_user_tz(user_id, user)
            tz = pytz.timezone(user_tz_str)
            
            # Use pre-fetched conversations if available, otherwise fetch
            if conversation_history is None:
                recent_convos = await self.memory.db.get_recent_conversations(
                    user_id, limit=100
                )
            else:
                # Use the first N messages from pre-fetched history
                recent_convos = conversation_history[:100]
            if not recent_convos:
                logger.debug("No recent conversations to summarize", user_id=user_id)
                return
            
            # Extract start and end times from conversation objects
            first_conv = recent_convos[0]
            last_conv = recent_convos[-1]
            
            if first_conv.timestamp:
                utc_start = first_conv.timestamp.replace(tzinfo=pytz.utc)
                start_time = utc_start.astimezone(tz).strftime("%Y-%m-%d %H:%M")
            else:
                start_time = "unknown"
            
            if last_conv.timestamp:
                utc_end = last_conv.timestamp.replace(tzinfo=pytz.utc)
                end_time = utc_end.astimezone(tz).strftime("%Y-%m-%d %H:%M")
            else:
                end_time = "unknown"
            
            # Format conversations with timestamps
            # Use user's name for their messages and "Aki" for assistant messages
            convo_lines = []
            for conv in recent_convos:
                role = user_name if conv.role == "user" else "Aki"
                if conv.timestamp:
                    utc_time = conv.timestamp.replace(tzinfo=pytz.utc)
                    local_time = utc_time.astimezone(tz)
                    ts = local_time.strftime("%Y-%m-%d %H:%M")
                else:
                    ts = ""
                convo_lines.append(f"[{ts}] {role}: {conv.message}")
            recent_conversation = "\n".join(convo_lines)
            
            # Build prompt with explicit start/end times
            prompt = COMPACT_PROMPT.format(
                user_name=user_name,
                start_time=start_time,
                end_time=end_time,
                recent_conversation=recent_conversation,
            )
            SoulAgent._last_compact_prompt[user_id] = prompt
            
            # Generate summary
            result = await llm_client.chat(
                model=settings.MODEL_MEMORY,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=settings.SUMMARY_MAX_TOKENS,
            )
            
            logger.debug(
                "Compact summary generated", 
                user_id=user_id, 
                summary_length=len(result),
                summary=result[:100]
            )
            
            # Store summary as a diary entry with type "compact_summary"
            if result and result.strip():
                # The LLM returns the summary directly without a "SUMMARY:" prefix
                summary_content = result.strip()
                
                # Convert start/end times back to datetime objects for storage
                exchange_start_dt = None
                exchange_end_dt = None
                if first_conv.timestamp:
                    exchange_start_dt = first_conv.timestamp  # Store as UTC
                if last_conv.timestamp:
                    exchange_end_dt = last_conv.timestamp  # Store as UTC
                
                # Record token usage for compact summary
                if result.usage and result.usage.total_tokens > 0:
                    await self.memory.record_token_usage(
                        user_id=user_id,
                        model=result.usage.model,
                        input_tokens=result.usage.input_tokens,
                        output_tokens=result.usage.output_tokens,
                        total_tokens=result.usage.total_tokens,
                        cache_read_tokens=result.usage.cache_read_tokens,
                        cache_creation_tokens=result.usage.cache_creation_tokens,
                        call_type="compact",
                    )
                
                # Store in diary entries with exchange timestamps
                await self.memory.add_diary_entry(
                    user_id=user_id,
                    entry_type="compact_summary",
                    title="Conversation Summary",
                    content=summary_content,
                    importance=5,  # Medium importance
                    exchange_start=exchange_start_dt,
                    exchange_end=exchange_end_dt,
                )
                
                logger.info("Stored compact summary", user_id=user_id,
                           exchange_start=start_time, exchange_end=end_time)
            else:
                logger.warning("Empty compact summary generated", user_id=user_id)
            
        except Exception as e:
            logger.error("Failed to create compact summary", user_id=user_id, error=str(e))

    async def _create_memory_entry(
        self,
        user_id: int,
        conversation_history: Optional[List[ConversationSchema]] = None,
    ) -> None:
        """Create a memory entry about the user from recent conversation exchanges.
        
        Args:
            user_id: User ID
            conversation_history: Pre-fetched conversation history (optional, will fetch if not provided)
        """
        logger.info("Running memory entry creation", user_id=user_id)
        try:
            # Get user name and timezone
            user = await self.memory.get_user_by_id(user_id)
            user_name = user.name if user and user.name else "them"
            user_tz_str = await self._get_user_tz(user_id, user)
            tz = pytz.timezone(user_tz_str)
            
            # Use pre-fetched conversations if available, otherwise fetch
            if conversation_history is None:
                recent_convos = await self.memory.db.get_recent_conversations(
                    user_id, limit=100
                )
            else:
                # Use the first N messages from pre-fetched history
                recent_convos = conversation_history[:100]
            if not recent_convos:
                logger.debug("No recent conversations for memory entry", user_id=user_id)
                return
            
            # Extract start and end times from conversation objects
            first_conv = recent_convos[0]
            last_conv = recent_convos[-1]
            
            if first_conv.timestamp:
                utc_start = first_conv.timestamp.replace(tzinfo=pytz.utc)
                start_time = utc_start.astimezone(tz).strftime("%Y-%m-%d %H:%M")
            else:
                start_time = "unknown"
            
            if last_conv.timestamp:
                utc_end = last_conv.timestamp.replace(tzinfo=pytz.utc)
                end_time = utc_end.astimezone(tz).strftime("%Y-%m-%d %H:%M")
            else:
                end_time = "unknown"
            
            # Format conversations with timestamps
            convo_lines = []
            for conv in recent_convos:
                role = user_name if conv.role == "user" else "Aki"
                if conv.timestamp:
                    utc_time = conv.timestamp.replace(tzinfo=pytz.utc)
                    local_time = utc_time.astimezone(tz)
                    ts = local_time.strftime("%Y-%m-%d %H:%M")
                else:
                    ts = ""
                convo_lines.append(f"[{ts}] {role}: {conv.message}")
            recent_conversation = "\n".join(convo_lines)
            
            # Build prompt with explicit start/end times
            prompt = MEMORY_PROMPT.format(
                user_name=user_name,
                start_time=start_time,
                end_time=end_time,
                recent_conversation=recent_conversation,
            )
            
            # Generate memory entry
            result = await llm_client.chat(
                model=settings.MODEL_MEMORY,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5,  # Slightly higher temperature for more natural, personal writing
                max_tokens=settings.MEMORY_MAX_TOKENS,
            )
            
            logger.debug(
                "Memory entry generated", 
                user_id=user_id, 
                memory_length=len(result),
                memory=result[:100]
            )
            
            # Store memory as a diary entry with type "conversation_memory"
            if result and result.strip():
                # Parse title and content from tags
                title_match = re.search(r'<title>(.*?)</title>', result, re.DOTALL)
                memory_match = re.search(r'<memory>(.*?)</memory>', result, re.DOTALL)
                
                if title_match and memory_match:
                    title = title_match.group(1).strip()
                    memory_content = memory_match.group(1).strip()
                else:
                    # Fallback for old format or if parsing fails
                    title = "Conversation Memory"
                    memory_content = result.strip()
                    # Remove any stray tags if present
                    memory_content = re.sub(r'</?memory>', '', memory_content).strip()
                    memory_content = re.sub(r'</?title>', '', memory_content).strip()
                
                # Convert start/end times back to datetime objects for storage
                exchange_start_dt = None
                exchange_end_dt = None
                if first_conv.timestamp:
                    exchange_start_dt = first_conv.timestamp  # Store as UTC
                if last_conv.timestamp:
                    exchange_end_dt = last_conv.timestamp  # Store as UTC
                
                # Record token usage for memory entry
                if result.usage and result.usage.total_tokens > 0:
                    await self.memory.record_token_usage(
                        user_id=user_id,
                        model=result.usage.model,
                        input_tokens=result.usage.input_tokens,
                        output_tokens=result.usage.output_tokens,
                        total_tokens=result.usage.total_tokens,
                        cache_read_tokens=result.usage.cache_read_tokens,
                        cache_creation_tokens=result.usage.cache_creation_tokens,
                        call_type="memory",
                    )
                
                # Store in diary entries with exchange timestamps
                await self.memory.add_diary_entry(
                    user_id=user_id,
                    entry_type="conversation_memory",
                    title=title,
                    content=memory_content,
                    importance=6,  # Slightly higher importance than compact summaries
                    exchange_start=exchange_start_dt,
                    exchange_end=exchange_end_dt,
                )
                
                logger.info("Stored conversation memory", user_id=user_id, title=title,
                           exchange_start=start_time, exchange_end=end_time)
            else:
                logger.warning("Empty memory entry generated", user_id=user_id)
            
        except Exception as e:
            logger.error("Failed to create memory entry", user_id=user_id, error=str(e))
        except Exception as e:
            logger.error("Failed to create compact summary", user_id=user_id, error=str(e))
    async def generate_daily_message(
        self,
        user_id: int,
    ) -> tuple[str, bool]:
        """
        Generate a personal, motivational daily message for the user.
        
        Returns:
            Tuple of (message_content, is_fallback)
        """
        try:
            # 1. Get user context
            user = await self.memory.get_user_by_id(user_id)
            user_name = user.name if user and user.name else "friend"
            
            # Fetch minimal context for daily message: 1 summary and last 5 messages
            diary_entries = await self.memory.get_diary_entries(user_id, limit=10)
            summaries = [e for e in diary_entries if e.entry_type == 'compact_summary']
            memories = [e for e in diary_entries if e.entry_type == 'conversation_memory']
            
            # Use the single most recent summary or memory
            best_entry = summaries[0] if summaries else (memories[0] if memories else None)
            
            user_tz_str = await self._get_user_tz(user_id, user)
            tz = pytz.timezone(user_tz_str)
            context_text = "(No previous exchanges remembered yet)"
            if best_entry:
                ts = best_entry.timestamp.replace(tzinfo=pytz.utc).astimezone(tz).strftime("%b %d")
                context_text = f"[{ts}] {best_entry.content}"
            
            # Last 5 messages
            recent_convos = await self.memory.db.get_recent_conversations(user_id, limit=5)
            history_text = self._format_history(recent_convos, user_name, tz_str=user_tz_str)
            
            # 2. Check if we have any meaningful context
            if not recent_convos and context_text == "(No previous exchanges remembered yet)":
                import random
                return random.choice(FALLBACK_QUOTES), True
            
            # 3. Generate via LLM using dedicated daily message model
            prompt = DAILY_MESSAGE_PROMPT.format(
                user_name=user_name,
                context=context_text,
                recent_history=history_text,
            )
            
            logger.info("Generating daily message", user_id=user_id, model=settings.MODEL_DAILY_MESSAGE)
            
            message = await llm_client.chat(
                model=settings.MODEL_DAILY_MESSAGE,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.8,
                max_tokens=150,
            )
            
            if isinstance(message, str):
                raw = message.strip()
            else:
                raw = message.content.strip()
            
            # 4. Sanitize: strip markdown, headers, and commentary
            final_message = self._sanitize_daily_message(raw)
            
            # Handle potential empty response
            if not final_message:
                import random
                return random.choice(FALLBACK_QUOTES), True
                
            return final_message, False
            
        except Exception as e:
            logger.error("Failed to generate daily message", user_id=user_id, error=str(e))
            import random
            return random.choice(FALLBACK_QUOTES), True

    @staticmethod
    def _sanitize_daily_message(raw: str) -> str:
        """Strip markdown formatting, headers, and commentary from daily message output."""
        text = raw.strip()
        
        # Remove markdown headers (# Daily Message, ## etc.)
        text = re.sub(r'^#+\s.*\n?', '', text, flags=re.MULTILINE).strip()
        
        # Remove markdown bold/italic
        text = re.sub(r'\*{1,2}(.*?)\*{1,2}', r'\1', text)
        text = re.sub(r'_{1,2}(.*?)_{1,2}', r'\1', text)
        
        # If there's a "---" separator, only keep what's before it (the actual message)
        if '---' in text:
            text = text.split('---')[0].strip()
        
        # If multi-line, take only the first non-empty paragraph
        # (LLM sometimes appends "Why this works:" or similar commentary)
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        if paragraphs:
            text = paragraphs[0]
        
        # Collapse any remaining newlines into spaces
        text = ' '.join(text.split())
        
        # Trim to ~280 chars at sentence boundary if too long
        if len(text) > 300:
            cut = text[:280]
            last_period = max(cut.rfind('.'), cut.rfind('!'), cut.rfind('?'))
            if last_period > 100:
                text = cut[:last_period + 1]
            else:
                text = cut.rsplit(' ', 1)[0] + '…'
        
        return text.strip()

    @classmethod
    def get_last_thinking(cls, user_id: int) -> Optional[str]:
        """Get the last thinking for a user (for debugging)."""
        return cls._last_thinking.get(user_id)

    @classmethod
    def get_last_system_prompt(cls, user_id: int) -> Optional[str]:
        """Get the last companion system prompt for a user (for debugging)."""
        return cls._last_system_prompt.get(user_id)

    @classmethod
    def get_last_raw_response(cls, user_id: int) -> Optional[str]:
        """Get the last raw LLM response for a user (for debugging)."""
        return cls._last_raw_response.get(user_id)

    @classmethod
    def get_last_recent_exchanges(cls, user_id: int) -> Optional[str]:
        """Get the last recent exchanges context for a user (for debugging)."""
        return cls._last_recent_exchanges.get(user_id)


    async def generate_personalized_insights(
        self,
        user_id: int,
        store: bool = False,
    ) -> Dict:
        """
        Generate fun, personalized insights (unhinged quotes, observations, etc.) for the user.
        Uses DEEP CONTEXT: Fetches last 10 memories + ALL user messages from that time range.
        
        Args:
            user_id: User ID
            store: If True, saves to database as a diary entry
            
        Returns:
            Dictionary containing unhinged quotes, observations, and fun questions.
        """
        try:
            # 1. Get user context
            user = await self.memory.get_user_by_id(user_id)
            user_name = user.name if user and user.name else "friend"
            
            # 2. Fetch Deep Context
            # Step A: Get last 10 Conversation Memories (these serve as the "spine" of the history)
            memories = await self.memory.get_diary_entries(
                user_id=user_id, 
                limit=10, 
                entry_type="conversation_memory"
            )
            
            # Default context if no memories exist
            if not memories:
                return {
                    "unhinged_quotes": [],
                    "aki_observations": [],
                    "fun_questions": ["What's your favorite way to start the day?", "What's a topic you could talk about for hours?"],
                    "personal_stats": {"current_vibe": "New Friend", "top_topic": "Unknown"}
                }

            # Step B: Determine the time range (Oldest Memory Start -> Now)
            # We look for 'exchange_start' (start of convo) or fallback to 'timestamp'
            timestamps = [m.exchange_start or m.timestamp for m in memories]
            cutoff_time = min(timestamps) if timestamps else None
            
            if not cutoff_time:
                # Should not happen given "if not memories" check, but safe fallback
                cutoff_time = datetime.utcnow() - timedelta(days=7)

            # Step C: Fetch ALL USER messages since that cutoff
            # We only want ROLE='user' to save tokens and find "unhinged" user quotes
            raw_conversations = await self.memory.db.get_conversations_after(
                user_id=user_id,
                after=cutoff_time,
                limit=500 # Safe upper limit to prevent overflow, though 10 memories shouldn't exceed this
            )
            user_messages = [c for c in raw_conversations if c.role == "user"]
            
            # Step D: Group Memories with their Context
            # We will format this as a timeline for the LLM
            formatted_context = []
            
            # Sort memories oldest to newest
            memories.sort(key=lambda m: m.timestamp)
            
            # Helper to find messages "belonging" to a memory
            # A message belongs if it matches the memory's exchange_start/end window
            # or if it effectively falls in the gap before the next memory
            
            used_msg_ids = set()
            
            for i, memory in enumerate(memories):
                mem_start = memory.exchange_start or memory.timestamp
                mem_end = memory.exchange_end or memory.timestamp
                
                # Loose matching: Find user msgs that are >= start - 10min AND <= end + 10min
                # Or simply assign unassigned messages that occurred before this memory
                
                matched_msgs = []
                for msg in user_messages:
                    if msg.id in used_msg_ids:
                        continue
                    
                    # If message is before this memory's end (plus buffer), we assign it here
                    # This effectively sweeps up "preceding" context into the current memory block
                    if msg.timestamp <= (mem_end + timedelta(minutes=30)):
                        matched_msgs.append(f"- \"{msg.message}\"")
                        used_msg_ids.add(msg.id)
                
                # Add to formatted block
                title = memory.title or "Conversation"
                block = f"## MEMORY: {title}\n(Summary: {memory.content})\n"
                if matched_msgs:
                    block += "RAW USER QUOTES:\n" + "\n".join(matched_msgs)
                else:
                    block += "(No direct exact quotes found for this range)"
                
                formatted_context.append(block)
            
            # Catch failures or leftover recent messages
            leftovers = [m for m in user_messages if m.id not in used_msg_ids]
            if leftovers:
                formatted_context.append("## RECENT UNPROCESSED CONTEXT\nRAW USER QUOTES:\n" + "\n".join([f"- \"{m.message}\"" for m in leftovers]))
            
            final_context_text = "\n\n".join(formatted_context)
            
            # 3. Generate via LLM
            # Note: We removed 'recent_history' from prompt as we are now feeding custom 'context'
            prompt = PERSONALIZED_INSIGHTS_PROMPT.format(
                user_name=user_name,
                context=final_context_text,
            )
            
            logger.info("Generating personalized insights", user_id=user_id, model=settings.MODEL_INSIGHTS)
            
            response = await llm_client.chat(
                model=settings.MODEL_INSIGHTS,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.8,
                max_tokens=1000,
            )
            
            content = response.content if hasattr(response, 'content') else str(response)
            
            # Parse JSON
            try:
                # Find JSON block if it's wrapped in backticks
                json_match = re.search(r'(\{.*\})', content, re.DOTALL)
                if json_match:
                    content_json = json_match.group(1)
                else:
                    content_json = content
                
                data = json.loads(content_json)
                
                # 4. Store if requested
                if store:
                    await self.memory.add_diary_entry(
                        user_id=user_id,
                        entry_type="personalized_insights",
                        title="Personalized Fun Sheet",
                        content=content_json, # Store raw JSON string
                        importance=8
                    )
                    logger.info("Stored fresh personalized insights", user_id=user_id)
                
                return data
            except json.JSONDecodeError:
                logger.error("Failed to parse personalized insights JSON", user_id=user_id, raw=content)
                return {
                    "unhinged_quotes": [],
                    "aki_observations": [{"title": "Observation failed", "description": "I'm still thinking about you...", "emoji": "🤔"}],
                    "fun_questions": ["What's on your mind today?"],
                    "personal_stats": {"current_vibe": "Thinking", "top_topic": "You"}
                }
                
        except Exception as e:
            logger.error("Failed to generate personalized insights", user_id=user_id, error=str(e))
            return {"error": str(e)}

    async def generate_daily_soundtrack(self, user_id: int) -> Dict:
        """
        Generates a personalized song recommendation based on user mood and music taste.
        """
        try:
            # 1. Get user and validate Spotify connection
            user = await self.memory.get_user_by_id(user_id)
            if not user or not user.spotify_refresh_token:
                return {"connected": False}

            access_token = await spotify_manager.get_valid_token(user)
            if not access_token:
                return {"connected": False}

            # 2. Gather Context
            # Step A: Get music context
            top_tracks = await spotify_manager.get_top_tracks(access_token, limit=5)
            recent_tracks = await spotify_manager.get_recently_played(access_token, limit=5)
            
            top_tracks_text = "\n".join([f"- {t['name']} by {t['artists'][0]['name']}" for t in top_tracks])
            recent_tracks_text = "\n".join([f"- {t['track']['name']} by {t['track']['artists'][0]['name']}" for t in recent_tracks])

            # Step B: Get conversational context (using smart slicing/deduplication)
            # Fetch more history to allow slicing
            full_history = await self.memory.db.get_recent_conversations(user_id, limit=30)
            context_text, history_text = await self._build_conversation_context(user_id, full_history, user)

            # 3. Ask Aki to pick a vibe/song
            prompt = SPOTIFY_DJ_PROMPT.format(
                user_name=user.name or "friend",
                context=context_text or "No specific milestones recently.",
                recent_history=history_text or "We haven't talked much lately.",
                top_tracks=top_tracks_text or "Taste not yet known.",
                recently_played=recent_tracks_text or "No recent history."
            )

            response = await llm_client.chat(
                model=settings.MODEL_INSIGHTS, # Use Sonnet for better taste
                messages=[{"role": "user", "content": prompt}],
                temperature=0.8,
                max_tokens=600,
            )
            
            content = response.content if hasattr(response, 'content') else str(response)
            
            # Parse JSON
            json_match = re.search(r'(\{.*\})', content, re.DOTALL)
            dj_data = json.loads(json_match.group(1)) if json_match else {}
            
            if not dj_data:
                return {"error": "Failed to generate DJ data"}

            # 4. Find the song on Spotify (or get recommendations based on the vibe)
            search_query = dj_data.get("search_query")
            sp = spotify_manager.get_client(access_token)
            
            # Try to find the specific song Aki recommended
            search_results = sp.search(q=search_query, limit=1, type='track')
            tracks = search_results.get('tracks', {}).get('items', [])
            
            if not tracks:
                # If Aki's specific pick isn't found, use Spotify Recommendations as fallback
                # with Aki's target params
                params = dj_data.get("target_params", {})
                seed_artists = [t['id'] for t in top_tracks[:2]] if top_tracks else []
                
                rec_tracks = sp.recommendations(
                    seed_artists=seed_artists,
                    limit=1,
                    target_energy=params.get("energy", 0.5),
                    target_valence=params.get("valence", 0.5)
                ).get('tracks', [])
                
                if rec_tracks:
                    tracks = rec_tracks

            if not tracks:
                return {"error": "Could not find a matching track on Spotify"}

            track = tracks[0]
            
            return {
                "connected": True,
                "vibe": dj_data.get("vibe_description"),
                "explanation": dj_data.get("explanation"),
                "track": {
                    "name": track["name"],
                    "artist": track["artists"][0]["name"],
                    "album_art": track["album"]["images"][0]["url"] if track["album"]["images"] else None,
                    "spotify_url": track["external_urls"]["spotify"],
                    "uri": track["uri"],
                    "preview_url": track.get("preview_url")
                }
            }

        except Exception as e:
            logger.error("Failed to generate daily soundtrack", user_id=user_id, error=str(e))
            return {"error": str(e)}

# Singleton instance
soul_agent = SoulAgent()
