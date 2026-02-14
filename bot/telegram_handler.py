"""
Telegram bot handler for receiving and sending messages.
Handles text messages, images, and commands.
Also runs the proactive messaging scheduler.
"""

import asyncio
import json
import logging
import random
from pathlib import Path
from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta
from collections import deque
import pytz
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

from config.settings import settings
from agents import orchestrator
from agents.soul_agent import SoulAgent
from memory.memory_manager_async import memory_manager
from utils.llm_client import llm_client
from prompts import REACH_OUT_PROMPT

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=getattr(logging, settings.LOG_LEVEL)
)
logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Sliding-window rate limiter for per-user message throttling.
    
    Prevents spam and runaway LLM costs by limiting messages per time window.
    Uses in-memory storage (no Redis needed at this scale).
    """
    
    def __init__(self, max_messages: int, window_seconds: int):
        """
        Initialize rate limiter.
        
        Args:
            max_messages: Maximum messages allowed per window
            window_seconds: Time window in seconds
        """
        self.max_messages = max_messages
        self.window_seconds = window_seconds
        self.disabled = max_messages == 0
        
        # Store timestamps per user_id using deque for efficient sliding window
        self._timestamps: Dict[int, deque] = {}
        
        logger.info(
            f"Rate limiter initialized: {max_messages} messages per {window_seconds}s "
            f"({'disabled' if self.disabled else 'enabled'})"
        )
    
    def check_rate_limit(self, user_id: int) -> tuple[bool, int]:
        """
        Check if user has exceeded rate limit.
        
        Args:
            user_id: User ID to check
            
        Returns:
            Tuple of (is_allowed, remaining_messages)
            - is_allowed: True if user can send message, False if rate limited
            - remaining_messages: Number of messages remaining in current window
        """
        if self.disabled:
            return True, self.max_messages
        
        now = datetime.now().timestamp()
        cutoff = now - self.window_seconds
        
        # Initialize or get user's timestamp queue
        if user_id not in self._timestamps:
            self._timestamps[user_id] = deque()
        
        timestamps = self._timestamps[user_id]
        
        # Remove timestamps outside the window (sliding window)
        while timestamps and timestamps[0] < cutoff:
            timestamps.popleft()
        
        # Check if under limit
        current_count = len(timestamps)
        remaining = max(0, self.max_messages - current_count)
        
        if current_count >= self.max_messages:
            logger.warning(
                f"Rate limit exceeded for user {user_id}: "
                f"{current_count}/{self.max_messages} messages in {self.window_seconds}s"
            )
            return False, 0
        
        # Add current timestamp
        timestamps.append(now)
        
        return True, remaining - 1  # -1 because we just added one
    
    def reset_user(self, user_id: int) -> None:
        """Reset rate limit for a specific user."""
        if user_id in self._timestamps:
            self._timestamps[user_id].clear()
            logger.info(f"Rate limit reset for user {user_id}")


class TelegramBot:
    """Telegram bot handler for the AI Companion."""

    def __init__(self):
        """Initialize the Telegram bot."""
        self.application: Optional[Application] = None
        # Debounce: buffer messages per chat_id, process after silence
        self._message_buffers: Dict[int, List[str]] = {}
        self._debounce_tasks: Dict[int, asyncio.Task] = {}
        self._debounce_metadata: Dict[int, dict] = {}  # Store user info per chat
        
        # Rate limiter: prevent spam and runaway costs
        self.rate_limiter = RateLimiter(
            max_messages=settings.USER_RATE_LIMIT_MESSAGES,
            window_seconds=settings.USER_RATE_LIMIT_WINDOW_SECONDS,
        )
        
        # Reaction counter: track messages until next reaction per user
        self._reaction_counter: Dict[int, int] = {}
        
        # Sticker counter: track messages until next sticker per user
        self._sticker_counter: Dict[int, int] = {}
        
        # Load stickers registry
        self.stickers = self._load_stickers()
        
        # Telegram reaction emojis (for checking if emoji should be a reaction)
        self.telegram_reactions = {
            '👍', '👎', '❤️', '🔥', '🥰', '👏', '😁', '🤔', '🤯', '😱',
            '😢', '🎉', '🤩', '🤮', '💩', '🙏', '👌', '🕊', '🤡', '🥱',
            '🥴', '😍', '🐳', '❤️‍🔥', '🌚', '🌭', '💯', '🤣', '⚡️', '🍌',
            '🏆', '💔', '🤨', '😐', '🍓', '🍾', '💋', '🖕', '😈', '😴',
            '😭', '🤓', '👻', '👨‍💻', '👀', '🎃', '🙈', '😇', '😨', '🤝',
            '✍️', '🤗', '🫡', '🎅', '🎄', '☃️', '💅', '🤪', '🗿', '🆒',
            '💘', '🙉', '🦄', '😘', '💊', '🙊', '😎', '👾', '🤷‍♂️', '🤷',
            '🤷‍♀️', '😡'
        }
    
    def _load_stickers(self) -> Dict[str, List[Dict[str, str]]]:
        """Load stickers from stickers.json."""
        stickers_file = Path(__file__).parent.parent / "config" / "stickers.json"
        try:
            with open(stickers_file, 'r', encoding='utf-8') as f:
                stickers = json.load(f)
            logger.info(f"Loaded {len(stickers)} emoji groups with stickers")
            return stickers
        except Exception as e:
            logger.warning(f"Failed to load stickers.json: {e}")
            return {}
    
    def _should_send_reaction(self, user_id: int) -> bool:
        """Determine if we should send a reaction for this message.
        
        Uses a counter that decrements each message. When counter reaches 0,
        trigger reaction and reset to a random value between MIN and MAX.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            True if reaction should be sent, False otherwise
        """
        import random
        
        # Initialize counter if not exists
        if user_id not in self._reaction_counter:
            # Set initial target (random between min and max)
            target = random.randint(
                settings.REACTION_MIN_MESSAGES,
                settings.REACTION_MAX_MESSAGES
            )
            self._reaction_counter[user_id] = target
            logger.debug(f"Initialized reaction counter for user {user_id}: {target} messages")
        
        # Decrement counter
        self._reaction_counter[user_id] -= 1
        logger.debug(f"Reaction counter for user {user_id}: {self._reaction_counter[user_id]}")
        
        # Check if we should trigger
        if self._reaction_counter[user_id] <= 0:
            # Reset with new random target
            target = random.randint(
                settings.REACTION_MIN_MESSAGES,
                settings.REACTION_MAX_MESSAGES
            )
            self._reaction_counter[user_id] = target
            logger.info(f"Reaction triggered for user {user_id}, reset counter to {target}")
            return True
        
        return False
    
    def _should_send_sticker(self, user_id: int) -> bool:
        """Determine if we should send a sticker for this message.
        
        Uses a counter that decrements each message. When counter reaches 0,
        trigger sticker and reset to a random value between MIN and MAX.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            True if sticker should be sent, False otherwise
        """
        import random
        
        # Initialize counter if not exists
        if user_id not in self._sticker_counter:
            # Set initial target (random between min and max)
            target = random.randint(
                settings.STICKER_MIN_MESSAGES,
                settings.STICKER_MAX_MESSAGES
            )
            self._sticker_counter[user_id] = target
            logger.debug(f"Initialized sticker counter for user {user_id}: {target} messages")
        
        # Decrement counter
        self._sticker_counter[user_id] -= 1
        logger.debug(f"Sticker counter for user {user_id}: {self._sticker_counter[user_id]}")
        
        # Check if we should trigger
        if self._sticker_counter[user_id] <= 0:
            # Reset with new random target
            target = random.randint(
                settings.STICKER_MIN_MESSAGES,
                settings.STICKER_MAX_MESSAGES
            )
            self._sticker_counter[user_id] = target
            logger.info(f"Sticker triggered for user {user_id}, reset counter to {target}")
            return True
        
        return False

    async def _send_long_message(self, chat_id: int, text: str, chunk_size: int = 4000) -> None:
        """Send a long message split across multiple Telegram messages."""
        for i in range(0, len(text), chunk_size):
            await self.application.bot.send_message(chat_id=chat_id, text=text[i:i + chunk_size])

    async def _send_with_typing(self, chat_id: int, text: Optional[str] = None, sticker: Optional[str] = None) -> None:
        """
        Send a message with a typing indicator beforehand.
        Alternately, send a sticker without typing delay if specified.
        """
        from telegram.error import TimedOut, NetworkError
        import httpx

        # If it's a sticker, send it directly (stickers don't usually have typing delays)
        if sticker:
            try:
                await self.application.bot.send_sticker(chat_id=chat_id, sticker=sticker)
                logger.info(f"Sent sticker {sticker} to {chat_id}")
            except Exception as e:
                logger.error(f"Failed to send sticker: {e}")
            
            # If there's also text, continue to send it with typing
            if not text:
                return

        # Typing duration: 0.5s base + scales with length, capped at 30s
        typing_duration = min(0.4 + len(text) * 0.01, 30.0)
        
        # Keep typing indicator active throughout delay
        # Telegram typing indicator expires after ~5 seconds, so refresh every 4 seconds
        elapsed = 0.0
        typing_interval = 4.0
        
        while elapsed < typing_duration:
            try:
                await self.application.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
            except (TimedOut, NetworkError, httpx.ReadError) as e:
                logger.warning(f"Typing indicator failed (timeout/network): {e}. Continuing.")
            
            # Sleep for the shorter of: remaining time or typing_interval
            sleep_time = min(typing_interval, typing_duration - elapsed)
            await asyncio.sleep(sleep_time)
            elapsed += sleep_time
        
        try:
            await self.application.bot.send_message(chat_id=chat_id, text=text)
        except (TimedOut, NetworkError, httpx.ReadError) as e:
            logger.error(f"Failed to send message due to timeout/network error: {e}")
            # Retry once after a brief delay
            await asyncio.sleep(1)
            try:
                await self.application.bot.send_message(chat_id=chat_id, text=text)
                logger.info("Message sent successfully on retry")
            except Exception as retry_error:
                logger.error(f"Retry also failed: {retry_error}")
                raise

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Handle the /start command.
        Neutral system setup for new users, or welcome back for existing users.
        """
        user = update.effective_user
        telegram_id = user.id
        first_name = user.first_name or "there"
        username = user.username
        chat_id = update.effective_chat.id

        logger.info(f"User {telegram_id} ({username}) started the bot")

        try:
            # Check if user already exists
            existing_user = await memory_manager.db.get_user_by_telegram_id(telegram_id)
            
            if existing_user:
                # Existing user - welcome them back through Aki
                logger.info(f"Existing user {telegram_id} restarted the bot")
                messages, _ = await orchestrator.process_message(
                    telegram_id=telegram_id,
                    message="Hello, I just started the bot.",
                    name=existing_user.name,
                    username=username,
                )
                for msg in messages:
                    await self._send_with_typing(chat_id, msg)
            else:
                # New user - neutral system setup (NOT Aki speaking)
                logger.info(f"New user {telegram_id} starting onboarding")
                
                # Create user with onboarding state
                await memory_manager.db.create_user_with_state(
                    telegram_id=telegram_id,
                    name=None,  # Will be set after user chooses
                    username=username,
                    onboarding_state="awaiting_name"
                )
                
                # System message: neutral setup tone
                setup_msg = "Before you meet Aki, there's one small thing to set up.\n\n"
                setup_msg += "What should Aki call you?"
                
                # Build reply keyboard with name options
                keyboard_buttons = []
                if first_name and first_name != "there":
                    keyboard_buttons.append([first_name])
                if username:
                    keyboard_buttons.append([username])
                keyboard_buttons.append(["Type a different name"])
                
                reply_markup = ReplyKeyboardMarkup(
                    keyboard_buttons,
                    one_time_keyboard=True,
                    resize_keyboard=True,
                    input_field_placeholder="Choose or type your name"
                )
                
                await update.message.reply_text(
                    setup_msg,
                    reply_markup=reply_markup
                )
                
        except Exception as e:
            logger.error(f"Error in start command: {e}")
            await update.message.reply_text(
                "Something went wrong. Please try /start again."
            )

    async def handle_text_message(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        Handle incoming text messages from users.
        Handles onboarding name selection or buffers messages for normal conversation.
        """
        user = update.effective_user
        chat_id = update.effective_chat.id
        message_text = update.message.text
        telegram_id = user.id
        first_name = user.first_name or "there"
        username = user.username

        logger.info(f"Received message from {telegram_id} ({username}): {message_text[:50]}...")

        # Check if user is in onboarding
        try:
            existing_user = await memory_manager.db.get_user_by_telegram_id(telegram_id)
            
            if existing_user and existing_user.onboarding_state == "awaiting_name":
                # User is in name selection phase (system setup, not Aki)
                logger.info(f"User {telegram_id} responding to name selection")
                
                # Parse the response - handle keyboard buttons or typed name
                chosen_name = None
                
                # Check if they selected from keyboard or typed custom name
                if message_text == first_name and first_name != "there":
                    chosen_name = first_name
                elif message_text == username:
                    chosen_name = username
                elif message_text == "Type a different name":
                    # They want to type a custom name
                    await update.message.reply_text(
                        "Please type the name you'd like Aki to call you:",
                        reply_markup=ReplyKeyboardRemove()
                    )
                    return
                else:
                    # They typed a custom name directly
                    chosen_name = message_text.strip()
                
                if chosen_name and len(chosen_name) > 0:
                    # Update user with chosen name and complete onboarding
                    await memory_manager.db.get_or_create_user(
                        telegram_id=telegram_id,
                        name=chosen_name,
                        username=username
                    )
                    await memory_manager.db.update_user_onboarding_state(
                        telegram_id=telegram_id,
                        onboarding_state=None  # Onboarding complete
                    )
                    
                    # System completion message (neutral, not Aki)
                    completion_msg = "Setup is complete! You can say hi to Aki when you're ready."
                    
                    await update.message.reply_text(
                        completion_msg,
                        reply_markup=ReplyKeyboardRemove()
                    )
                    logger.info(f"User {telegram_id} completed onboarding as '{chosen_name}'")
                else:
                    # Invalid name, ask again
                    await update.message.reply_text(
                        "Please enter a valid name:",
                        reply_markup=ReplyKeyboardRemove()
                    )
                return
                
        except Exception as e:
            logger.error(f"Error checking onboarding state: {e}")
            # Continue with normal message processing

        # Normal message processing (for users who completed onboarding)
        # Buffer the message
        if chat_id not in self._message_buffers:
            self._message_buffers[chat_id] = []
        self._message_buffers[chat_id].append(message_text)

        # Store user metadata and the last message object for reactions
        self._debounce_metadata[chat_id] = {
            "telegram_id": telegram_id,
            "name": first_name or username,
            "username": username,
            "last_message": update.message,  # Store for reaction
        }

        # Cancel any existing debounce timer for this chat
        if chat_id in self._debounce_tasks:
            self._debounce_tasks[chat_id].cancel()

        # Start a new debounce timer
        self._debounce_tasks[chat_id] = asyncio.create_task(
            self._process_buffered_messages(chat_id)
        )

    async def _process_buffered_messages(self, chat_id: int) -> None:
        """Wait for the debounce period, then process all buffered messages as one."""
        await asyncio.sleep(settings.DEBOUNCE_SECONDS)

        # Grab and clear the buffer
        buffered = self._message_buffers.pop(chat_id, [])
        metadata = self._debounce_metadata.pop(chat_id, {})
        self._debounce_tasks.pop(chat_id, None)

        if not buffered or not metadata:
            return

        telegram_id = metadata["telegram_id"]
        
        # Check rate limit before processing
        is_allowed, remaining = self.rate_limiter.check_rate_limit(telegram_id)
        
        if not is_allowed:
            # Rate limit exceeded - send friendly message without LLM call
            logger.warning(f"Rate limit exceeded for user {telegram_id}")
            rate_limit_msg = (
                "Hey, I need a moment to catch up! 😅\n\n"
                "You're sending messages faster than I can thoughtfully respond. "
                "Give me a few seconds to process everything, and then we can continue our conversation."
            )
            await self._send_with_typing(chat_id, rate_limit_msg)
            return

        # Combine into a single message
        combined = "\n".join(buffered)
        if len(buffered) > 1:
            logger.info(f"Debounced {len(buffered)} messages from {telegram_id} into one")
        
        # Log remaining messages in rate limit window
        if remaining <= 5 and not self.rate_limiter.disabled:
            logger.info(f"User {telegram_id} has {remaining} messages remaining in rate limit window")

        try:
            messages, emoji = await orchestrator.process_message(
                telegram_id=telegram_id,
                message=combined,
                name=metadata["name"],
                username=metadata["username"],
            )

            # Send reaction if emoji was generated and it's a valid Telegram reaction
            if emoji and "last_message" in metadata:
                # Check if we should send a reaction this time (counter-based)
                if self._should_send_reaction(telegram_id):
                    # Send reaction if it's in the Telegram reactions set
                    if emoji in self.telegram_reactions:
                        try:
                            await metadata["last_message"].set_reaction(emoji)
                            logger.info(f"Sent reaction {emoji} to user {metadata['telegram_id']}")
                        except Exception as e:
                            logger.warning(f"Failed to send reaction: {e}")
                    else:
                        logger.debug(f"Emoji '{emoji}' not in Telegram reactions set, skipping reaction")
                else:
                    logger.debug(f"Reaction counter not triggered for user {telegram_id}, skipping reaction")
                    
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            messages = [
                "I'm having a bit of trouble right now. "
                "Could you try again in a moment?"
            ]
            emoji = None  # Clear emoji on error

        # Send sticker BEFORE text messages if emoji was generated and has stickers available
        if emoji:
            logger.info(f"Emoji generated: '{emoji}' (type: {type(emoji).__name__}, repr: {repr(emoji)})")
            
            # Check if we should send a sticker this time (counter-based)
            if self._should_send_sticker(telegram_id):
                logger.info(f"Available sticker emojis: {list(self.stickers.keys())[:10]}...")  # Show first 10
                
                # Try exact match first
                sticker_options = None
                matched_emoji = None
                
                if emoji in self.stickers:
                    sticker_options = self.stickers[emoji]
                    matched_emoji = emoji
                    logger.info(f"Found exact match for emoji '{emoji}'")
                else:
                    # Try without variation selector
                    emoji_stripped = emoji.rstrip('\ufe0f')  # Remove variation selector
                    if emoji_stripped in self.stickers:
                        sticker_options = self.stickers[emoji_stripped]
                        matched_emoji = emoji_stripped
                        logger.info(f"Found match without variation selector: '{emoji_stripped}'")
                    else:
                        logger.warning(f"No sticker mapping found for emoji '{emoji}' (tried with and without variation selector)")
                
                # Send sticker if we found a match
                if sticker_options and matched_emoji:
                    logger.info(f"Found {len(sticker_options)} sticker options for emoji '{matched_emoji}'")
                    
                    if sticker_options:
                        # Randomly pick one sticker for this emoji
                        chosen_sticker = random.choice(sticker_options)
                        file_id = chosen_sticker["file_id"]
                        logger.info(f"Attempting to send sticker {file_id} for emoji '{matched_emoji}' to chat {chat_id}")
                        
                        try:
                            await self._send_with_typing(chat_id, sticker=file_id)
                            logger.info(f"Successfully sent sticker {file_id} ({matched_emoji}) to user {metadata['telegram_id']}")
                        except Exception as e:
                            logger.error(f"Failed to send sticker {file_id}: {e}", exc_info=True)
                    else:
                        logger.warning(f"Sticker options list is empty for emoji '{matched_emoji}'")
            else:
                logger.debug(f"Sticker counter not triggered for user {telegram_id}, skipping sticker")
        
        # Send text messages after sticker
        for msg in messages:
            await self._send_with_typing(chat_id, msg)
        else:
            logger.debug("No emoji generated for this message")

    async def handle_photo_message(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        Handle incoming photo messages from users.
        This will be connected to the vision processor in Phase 4.
        """
        user = update.effective_user
        telegram_id = user.id
        username = user.username or user.first_name

        # Get the largest photo (best quality)
        photo = update.message.photo[-1]
        photo_id = photo.file_id

        # Get caption if provided
        caption = update.message.caption or ""

        logger.info(
            f"Received photo from {telegram_id} ({username}), "
            f"file_id: {photo_id}, caption: {caption[:50] if caption else 'none'}"
        )

        # For now, just acknowledge - will be replaced with vision processor
        response = (
            "I see you've shared a photo! 📸\n\n"
            "The vision processor will be connected in Phase 4 to understand "
            "and remember this image. For now, I'm acknowledging receipt."
        )

        if caption:
            response += f"\n\nYour caption: '{caption}'"

        await update.message.reply_text(response)

    async def handle_sticker_message(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        Handle incoming sticker messages from users.
        Logs the sticker file_id for discovery.
        """
        sticker = update.message.sticker
        file_id = sticker.file_id
        emoji = sticker.emoji
        set_name = sticker.set_name
        
        logger.info(f"Sticker Discovery: file_id='{file_id}', emoji='{emoji}', set_name='{set_name}'")
        
        response = (
            f"I see that sticker! 📝\n\n"
            f"**File ID:** `{file_id}`\n"
            f"**Emoji:** {emoji or 'None'}\n"
            f"**Pack:** `{set_name or 'None'}`\n\n"
            f"If you want me to use this, tell me what 'vibe' it has!"
        )
        await update.message.reply_text(response, parse_mode='Markdown')

    async def reset_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Handle the /reset command.
        Clears user's conversation history and profile, allowing fresh start.
        """
        user = update.effective_user
        telegram_id = user.id

        logger.info(f"User {telegram_id} requested reset")

        try:
            # Get user
            db_user = await memory_manager.get_or_create_user(telegram_id)
            user_id = db_user.id

            # Clear all user data
            async with memory_manager.db.get_session() as session:
                from memory.models import Conversation, DiaryEntry
                from sqlalchemy import delete

                # Delete conversations
                await session.execute(
                    delete(Conversation).where(Conversation.user_id == user_id)
                )
                # Delete diary entries
                await session.execute(
                    delete(DiaryEntry).where(DiaryEntry.user_id == user_id)
                )
                await session.commit()

            logger.info(f"Reset complete for user {user_id}")
            await update.message.reply_text(
                "All your data has been reset. Send /start to begin fresh."
            )

        except Exception as e:
            logger.error(f"Error resetting user: {e}")
            await update.message.reply_text("Failed to reset. Please try again.")

    async def debug_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle the /debug command. Shows current user state."""
        user = update.effective_user
        telegram_id = user.id
        try:
            db_user = await memory_manager.get_or_create_user(telegram_id)
            user_id = db_user.id
            conv_count = await memory_manager.db.get_conversation_count(user_id)
            diary_count = await memory_manager.db.get_diary_count(user_id)
            
            response = (
                f"🔧 Debug Info\n\n"
                f"User ID: {user_id}\n"
                f"Telegram ID: {telegram_id}\n"
                f"Conversations: {conv_count}\n"
                f"Diary entries: {diary_count}\n"
            )
            await update.message.reply_text(response)
        except Exception as e:
            logger.error(f"Error in debug command: {e}")
            await update.message.reply_text(f"Debug error: {e}")

    async def thinking_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Shows the companion's last internal reflection for debugging."""
        user = update.effective_user
        telegram_id = user.id
        try:
            db_user = await memory_manager.get_or_create_user(telegram_id)
            user_id = db_user.id
            thinking = SoulAgent.get_last_thinking(user_id)
            response = f"🧠 Last internal reflection:\n\n{thinking}" if thinking else "No thinking captured yet."
            await update.message.reply_text(response)
        except Exception as e:
            logger.error(f"Error in thinking command: {e}")
            await update.message.reply_text(f"Error: {e}")

    async def prompt_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Shows the last companion system prompt sent to the LLM."""
        user = update.effective_user
        telegram_id = user.id
        try:
            db_user = await memory_manager.get_or_create_user(telegram_id)
            user_id = db_user.id
            prompt = SoulAgent.get_last_system_prompt(user_id)
            response = f"📋 Last companion prompt:\n\n{prompt}" if prompt else "No prompt captured yet."
            await self._send_long_message(update.effective_chat.id, response)
        except Exception as e:
            logger.error(f"Error in prompt command: {e}")
            await update.message.reply_text(f"Error: {e}")

    async def raw_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Shows the last raw LLM response before parsing."""
        user = update.effective_user
        telegram_id = user.id
        try:
            db_user = await memory_manager.get_or_create_user(telegram_id)
            user_id = db_user.id
            raw_response = SoulAgent.get_last_raw_response(user_id)
            response = f"🔍 Last raw response:\n\n{raw_response}" if raw_response else "No raw response captured yet."
            await self._send_long_message(update.effective_chat.id, response)
        except Exception as e:
            logger.error(f"Error in raw command: {e}")
            await update.message.reply_text(f"Error: {e}")

    async def reachout_settings_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Shows current reach-out configuration for the user."""
        user = update.effective_user
        telegram_id = user.id
        try:
            db_user = await memory_manager.get_or_create_user(telegram_id)
            enabled = "✅ Enabled" if db_user.reach_out_enabled else "❌ Disabled"
            min_hours = db_user.reach_out_min_silence_hours or settings.DEFAULT_REACH_OUT_MIN_SILENCE_HOURS
            max_days = db_user.reach_out_max_silence_days or settings.DEFAULT_REACH_OUT_MAX_SILENCE_DAYS
            response = (
                f"🔔 Reach-Out Settings\n\n"
                f"Status: {enabled}\n"
                f"Min silence: {min_hours} hours\n"
                f"Max silence: {max_days} days\n\n"
                f"Commands:\n"
                f"/reachout_enable - Enable reach-outs\n"
                f"/reachout_disable - Disable reach-outs\n"
                f"/reachout_min <hours> - Set min silence hours\n"
                f"/reachout_max <days> - Set max silence days"
            )
            await update.message.reply_text(response)
        except Exception as e:
            logger.error(f"Error in reachout_settings: {e}")

    async def reachout_enable_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Enables reach-out messages."""
        user = update.effective_user
        telegram_id = user.id
        try:
            db_user = await memory_manager.get_or_create_user(telegram_id)
            await memory_manager.update_user_reach_out_config(db_user.id, enabled=True)
            await update.message.reply_text("✅ Reach-outs enabled!")
        except Exception as e:
            logger.error(f"Error enabling reach-out: {e}")

    async def reachout_disable_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Disables reach-out messages."""
        user = update.effective_user
        telegram_id = user.id
        try:
            db_user = await memory_manager.get_or_create_user(telegram_id)
            await memory_manager.update_user_reach_out_config(db_user.id, enabled=False)
            await update.message.reply_text("❌ Reach-outs disabled.")
        except Exception as e:
            logger.error(f"Error disabling reach-out: {e}")

    async def reachout_min_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Sets minimum silence hours."""
        user = update.effective_user
        telegram_id = user.id
        try:
            if not context.args or len(context.args) != 1:
                await update.message.reply_text("Usage: /reachout_min <hours>")
                return
            hours = int(context.args[0])
            db_user = await memory_manager.get_or_create_user(telegram_id)
            await memory_manager.update_user_reach_out_config(db_user.id, min_silence_hours=hours)
            await update.message.reply_text(f"✅ Min silence set to {hours}h.")
        except Exception as e:
            logger.error(f"Error in reachout_min: {e}")

    async def reachout_max_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Sets maximum silence days."""
        user = update.effective_user
        telegram_id = user.id
        try:
            if not context.args or len(context.args) != 1:
                await update.message.reply_text("Usage: /reachout_max <days>")
                return
            days = int(context.args[0])
            db_user = await memory_manager.get_or_create_user(telegram_id)
            await memory_manager.update_user_reach_out_config(db_user.id, max_silence_days=days)
            await update.message.reply_text(f"✅ Max silence set to {days}d.")
        except Exception as e:
            logger.error(f"Error in reachout_max command: {e}", exc_info=True)
            await update.message.reply_text("❌ Error setting max silence days.")

    async def memories_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Open the Memory Viewer mini app"""
        try:
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
            
            user = update.effective_user
            telegram_id = user.id
            
            # Check if mini app URL is configured
            miniapp_url = settings.MINIAPP_URL if hasattr(settings, 'MINIAPP_URL') and settings.MINIAPP_URL else None
            
            if not miniapp_url:
                await update.message.reply_text(
                    "❌ Memory Viewer is not configured yet. Please contact the administrator."
                )
                return
            
            # Create inline keyboard with web app button
            keyboard = [[
                InlineKeyboardButton(
                    "🌟 View Your Memories",
                    web_app=WebAppInfo(url=miniapp_url)
                )
            ]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "✨ *Your Memory Viewer*\n\n"
                "Click the button below to explore:\n"
                "• 💭 Conversation memories\n"
                "• 💬 Full chat history\n"
                "• 📔 Diary entries\n"
                "• 📊 Activity timeline\n\n"
                "All your memories in one beautiful interface!",
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
            
            logger.info(f"Memories command used by user {telegram_id}")
            
        except Exception as e:
            logger.error(f"Error in memories command: {e}", exc_info=True)
            await update.message.reply_text(
                "❌ Sorry, there was an error opening the Memory Viewer. Please try again later."
            )

    async def memory_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Handle the /memory command.
        Shows the latest untruncated conversation_memory entry for the user.
        """
        user = update.effective_user
        telegram_id = user.id
        
        logger.info(f"User {telegram_id} requested their latest memory")
        
        try:
            # Get user from DB
            db_user = await memory_manager.get_or_create_user(telegram_id)
            user_id = db_user.id
            
            # Fetch latest conversation_memory entry
            entries = await memory_manager.get_diary_entries(
                user_id=user_id,
                limit=1,
                entry_type="conversation_memory"
            )
            
            if not entries:
                await update.message.reply_text("I don't have any formal memories of our conversations yet. We should talk more! 😊")
                return
            
            memory = entries[0]
            
            # Format the output
            tz = pytz.timezone(settings.TIMEZONE)
            utc_time = memory.timestamp.replace(tzinfo=pytz.utc)
            local_time = utc_time.astimezone(tz)
            ts_str = local_time.strftime("%A, %B %d at %I:%M %p")
            
            response = f"📔 *Latest Conversation Memory*\n_{ts_str}_\n\n{memory.content}"
            
            # Send using _send_long_message to handle Telegram's 4096 char limit
            await self._send_long_message(chat_id=update.effective_chat.id, text=response)
            
        except Exception as e:
            logger.error(f"Error in memory command: {e}", exc_info=True)
            await update.message.reply_text("❌ Sorry, I had trouble retrieving your memories right now.")
    async def send_message(self, telegram_id: int, message: str) -> None:
        """
        Send a message to a user.
        Used by the proactive agent to initiate conversations.

        Args:
            telegram_id: The Telegram user ID
            message: The message text to send
        """
        try:
            await self._send_with_typing(chat_id=telegram_id, text=message)
            logger.info(f"Sent proactive message to {telegram_id}")
        except Exception as e:
            logger.error(f"Failed to send message to {telegram_id}: {e}")

    async def _generate_reach_out_message(
        self,
        user_id: int,
        hours_since_last_message: int,
    ) -> Optional[Dict[str, Any]]:
        """
        Generate a natural reach-out message based on user inactivity.

        Args:
            user_id: Internal user ID
            hours_since_last_message: Hours since user's last message

        Returns:
            The generated message or None if reach-out not appropriate
        """
        try:
            # Get user info
            user = await memory_manager.db.get_user_by_id(user_id)
            if not user:
                return None
            
            user_name = user.name or "friend"

            # Get timezone
            tz = pytz.timezone(settings.TIMEZONE)
            now = datetime.now(tz)
            current_time = now.strftime("%A, %B %d, %Y at %I:%M %p")

            # Get recent memory entries
            diary_entries = await memory_manager.get_diary_entries(user_id, limit=settings.DIARY_FETCH_LIMIT)
            memory_entries = []
            last_memory_end = None
            
            for entry in diary_entries:
                if entry.entry_type == "conversation_memory":
                    # Format with timestamp
                    if entry.exchange_start and entry.exchange_end:
                        start_time = entry.exchange_start.replace(tzinfo=pytz.utc).astimezone(tz)
                        end_time = entry.exchange_end.replace(tzinfo=pytz.utc).astimezone(tz)
                        memory_entries.append(
                            f"[START: {start_time.strftime('%Y-%m-%d %H:%M')}] "
                            f"[END: {end_time.strftime('%Y-%m-%d %H:%M')}]\n{entry.content}"
                        )
                        # Track the most recent memory's end time
                        if last_memory_end is None or entry.exchange_end > last_memory_end:
                            last_memory_end = entry.exchange_end
                
                # Limit to configured number of memory entries
                memory_entries = memory_entries[:settings.MEMORY_ENTRY_LIMIT]
            
            # Build RECENT EXCHANGES section
            if memory_entries:
                recent_exchanges = "RECENT EXCHANGES:\n" + "\n\n".join(memory_entries)
            else:
                recent_exchanges = ""

            # Get current conversations (only messages AFTER last memory entry)
            if last_memory_end:
                # Query conversations after the last memory entry's end time
                conversations = await memory_manager.db.get_conversations_after(
                    user_id=user_id,
                    after=last_memory_end,
                    limit=settings.CONVERSATION_CONTEXT_LIMIT
                )
            else:
                # No memory entries yet, get recent conversations
                conversations = await memory_manager.db.get_recent_conversations(user_id, limit=settings.CONVERSATION_CONTEXT_LIMIT)

            # Build CURRENT CONVERSATION section
            if conversations:
                history_lines = []
                for conv in conversations:
                    role = user_name if conv.role == "user" else "Aki"
                    if conv.timestamp:
                        utc_time = conv.timestamp.replace(tzinfo=pytz.utc)
                        local_time = utc_time.astimezone(tz)
                        ts = local_time.strftime("%Y-%m-%d %H:%M")
                    else:
                        ts = ""
                    history_lines.append(f"[{ts}] {role}: {conv.message}")
                current_conversation = "CURRENT CONVERSATION:\n" + "\n".join(history_lines)
            else:
                current_conversation = "CURRENT CONVERSATION:\n(No recent messages)"

            # Format time since last message
            if hours_since_last_message < 24:
                time_since = f"{hours_since_last_message} hours"
            else:
                days = hours_since_last_message // 24
                time_since = f"{days} day{'s' if days > 1 else ''}"

            # Get persona from soul_agent instance
            from agents.soul_agent import soul_agent
            persona = soul_agent.persona

            # Generate the message
            prompt = REACH_OUT_PROMPT.format(
                current_time=current_time,
                time_since=time_since,
                persona=persona,
                user_name=user_name,
                recent_exchanges=recent_exchanges,
                current_conversation=current_conversation,
            )

            # Log the full prompt for debugging
            logger.info(f"\n{'='*80}\nREACH-OUT PROMPT FOR USER {user_id} ({user_name}):\n{'='*80}\n{prompt}\n{'='*80}\n")

            message = await llm_client.chat(
                model=settings.MODEL_PROACTIVE,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.9,
                max_tokens=200,
            )

            message = message.strip()

            # Log the LLM response
            logger.info(f"\n{'='*80}\nREACH-OUT RESPONSE FOR USER {user_id} ({user_name}):\n{'='*80}\n{message}\n{'='*80}\n")

            # LLM decided this reach-out isn't appropriate
            if message.upper() == "SKIP":
                logger.info(f"Skipping reach-out - LLM determined not appropriate")
                return None

            # Return both message and prompt for storage in thinking field
            return {"message": message, "prompt": prompt}

        except Exception as e:
            logger.error(f"Failed to generate reach-out message: {e}")
            return None

    async def _check_inactive_users(self, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Check for inactive users and send reach-out messages.
        This runs periodically via JobQueue.
        """
        try:
            # Get only eligible users (filtered in SQL: reach_out_enabled, onboarding complete, not recently reached out)
            eligible_users = await memory_manager.get_users_for_reach_out(
                min_silence_hours=settings.DEFAULT_REACH_OUT_MIN_SILENCE_HOURS
            )
            
            if not eligible_users:
                return

            logger.info(f"Checking {len(eligible_users)} eligible users for inactivity reach-outs")

            tz = pytz.timezone(settings.TIMEZONE)
            now = datetime.now(tz)
            sent_count = 0

            for user in eligible_users:
                try:
                    # Get user's last message
                    last_user_msg = await memory_manager.get_last_user_message(user.id)
                    
                    if not last_user_msg:
                        continue

                    # Calculate hours since last message
                    msg_time = last_user_msg.timestamp
                    if msg_time.tzinfo is None:
                        msg_time = tz.localize(msg_time)
                    
                    hours_since = (now - msg_time).total_seconds() / 3600

                    # Check if within reach-out window
                    min_hours = user.reach_out_min_silence_hours or settings.DEFAULT_REACH_OUT_MIN_SILENCE_HOURS
                    max_days = user.reach_out_max_silence_days or settings.DEFAULT_REACH_OUT_MAX_SILENCE_DAYS
                    max_hours = max_days * 24

                    if hours_since < min_hours or hours_since > max_hours:
                        continue

                    # Generate and send reach-out
                    result = await self._generate_reach_out_message(
                        user_id=user.id,
                        hours_since_last_message=int(hours_since),
                    )

                    if result:
                        # Extract message and prompt
                        message_text = result["message"]
                        prompt_text = result["prompt"]
                        
                        # Parse message for multiple parts (support [BREAK] and |||)
                        messages = []
                        if '[BREAK]' in message_text:
                            messages = [msg.strip() for msg in message_text.split('[BREAK]') if msg.strip()]
                        elif '|||' in message_text:
                            messages = [msg.strip() for msg in message_text.split('|||') if msg.strip()]
                        else:
                            messages = [message_text]
                        
                        # Send each message with delay
                        for i, msg in enumerate(messages):
                            await self.send_message(user.telegram_id, msg)
                            if i < len(messages) - 1:
                                await asyncio.sleep(1.5)  # Delay between messages
                        
                        sent_count += 1

                        # Store full message in conversation history with prompt in thinking field
                        await memory_manager.add_conversation(
                            user_id=user.id,
                            role="assistant",
                            message=message_text,
                            thinking=prompt_text,
                        )

                        # Update last reach-out timestamp
                        await memory_manager.update_user_reach_out_timestamp(user.id, now)

                        logger.info(
                            f"Sent reach-out to user {user.id} (inactive for {int(hours_since)}h, {len(messages)} messages): {message_text[:50]}..."
                        )

                except Exception as e:
                    logger.error(f"Failed to process reach-out for user {user.id}: {e}")

            if sent_count > 0:
                logger.info(f"Sent {sent_count} reach-out message(s)")

        except Exception as e:
            logger.error(f"Error in inactive user checker: {e}")

    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Handle errors caused by updates.
        Logs errors gracefully instead of crashing the application.
        """
        logger.error(
            f"Exception while handling an update",
            exc_info=context.error,
            extra={
                "update": str(update) if update else "No update",
                "error_type": type(context.error).__name__,
            }
        )

    def setup_handlers(self) -> None:
        """Set up message and command handlers."""
        assert self.application is not None, "Application not initialized"
        # Error handler - must be added first to catch all errors
        self.application.add_error_handler(self.error_handler)
        
        # Command handlers
        self.application.add_handler(
            CommandHandler("start", self.start_command)
        )
        self.application.add_handler(
            CommandHandler("reset", self.reset_command)
        )
        self.application.add_handler(
            CommandHandler("debug", self.debug_command)
        )
        self.application.add_handler(
            CommandHandler("thinking", self.thinking_command)
        )
        self.application.add_handler(
            CommandHandler("prompt", self.prompt_command)
        )
        self.application.add_handler(
            CommandHandler("raw", self.raw_command)
        )
        self.application.add_handler(
            CommandHandler("reachout_settings", self.reachout_settings_command)
        )
        self.application.add_handler(
            CommandHandler("reachout_enable", self.reachout_enable_command)
        )
        self.application.add_handler(
            CommandHandler("reachout_disable", self.reachout_disable_command)
        )
        self.application.add_handler(
            CommandHandler("reachout_min", self.reachout_min_command)
        )
        self.application.add_handler(
            CommandHandler("reachout_max", self.reachout_max_command)
        )
        self.application.add_handler(
            CommandHandler("memories", self.memories_command)
        )
        self.application.add_handler(
            CommandHandler("memory", self.memory_command)
        )
        
        # Message handlers
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text_message)
        )
        self.application.add_handler(
            MessageHandler(filters.PHOTO, self.handle_photo_message)
        )
        self.application.add_handler(
            MessageHandler(filters.Sticker.ALL, self.handle_sticker_message)
        )

        logger.info("Telegram bot handlers configured")

    def run(self) -> None:
        """
        Start the Telegram bot.
        This is a blocking call that runs the bot until interrupted.
        """
        # Settings are validated on import (Pydantic v2)

        # Create application
        self.application = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()

        # Set up handlers
        self.setup_handlers()

        # Set up the reach-out checker
        # Check for inactive users based on configured interval
        reach_out_interval = settings.REACH_OUT_CHECK_INTERVAL_MINUTES * 60  # Convert to seconds
        assert self.application.job_queue is not None
        self.application.job_queue.run_repeating(
            self._check_inactive_users,
            interval=reach_out_interval,
            first=120,  # Start after 2 minutes
            name="inactive_user_checker",
        )
        logger.info(f"Reach-out checker configured (every {settings.REACH_OUT_CHECK_INTERVAL_MINUTES} minutes)")

        # Start the bot in webhook or polling mode
        if settings.WEBHOOK_URL:
            # Telegram secret_token only allows A-Za-z0-9_- characters
            import hashlib
            webhook_secret = settings.WEBHOOK_SECRET or hashlib.sha256(settings.TELEGRAM_BOT_TOKEN.encode()).hexdigest()[:32]
            webhook_path = f"/webhook/{webhook_secret}"
            webhook_url = f"{settings.WEBHOOK_URL}{webhook_path}"

            logger.info(f"Starting Telegram bot in WEBHOOK mode on port {settings.PORT}")
            self.application.run_webhook(
                listen="0.0.0.0",
                port=settings.PORT,
                url_path=webhook_path,
                webhook_url=webhook_url,
                secret_token=webhook_secret,
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=True,
            )
        else:
            logger.info("Starting Telegram bot in POLLING mode (no WEBHOOK_URL set)")
            self.application.run_polling(
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=True,
            )


# Singleton instance
bot = TelegramBot()
