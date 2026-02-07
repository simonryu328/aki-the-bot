"""
Telegram bot handler for receiving and sending messages.
Handles text messages, images, and commands.
Also runs the proactive messaging scheduler.
"""

import asyncio
import logging
from typing import Optional, Dict, List
from datetime import datetime, timedelta
import pytz
from telegram import Update
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
from prompts import PROACTIVE_MESSAGE_PROMPT

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=getattr(logging, settings.LOG_LEVEL)
)
logger = logging.getLogger(__name__)


class TelegramBot:
    """Telegram bot handler for the AI Companion."""

    DEBOUNCE_SECONDS = 3  # Wait this long for more messages before processing

    def __init__(self):
        """Initialize the Telegram bot."""
        self.application: Optional[Application] = None
        # Debounce: buffer messages per chat_id, process after silence
        self._message_buffers: Dict[int, List[str]] = {}
        self._debounce_tasks: Dict[int, asyncio.Task] = {}
        self._debounce_metadata: Dict[int, dict] = {}  # Store user info per chat

    async def _send_long_message(self, chat_id: int, text: str, chunk_size: int = 4000) -> None:
        """Send a long message split across multiple Telegram messages."""
        for i in range(0, len(text), chunk_size):
            await self.application.bot.send_message(chat_id=chat_id, text=text[i:i + chunk_size])

    async def _send_with_typing(self, chat_id: int, text: str) -> None:
        """
        Send a message with a typing indicator beforehand.
        Typing duration scales with message length for realism.
        """
        import asyncio

        await self.application.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        # Typing duration: 0.5s base + scales with length, capped at 2.5s
        typing_duration = min(0.5 + len(text) * 0.02, 2.5)
        await asyncio.sleep(typing_duration)
        await self.application.bot.send_message(chat_id=chat_id, text=text)

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Handle the /start command.
        Kicks off the onboarding conversation for new users.
        """
        user = update.effective_user
        telegram_id = user.id
        name = user.first_name or user.username or "there"
        username = user.username

        logger.info(f"User {telegram_id} ({username}) started the bot")

        try:
            # Process /start as a greeting through orchestrator
            messages = await orchestrator.process_message(
                telegram_id=telegram_id,
                message="Hello, I just started the bot.",
                name=name,
                username=username,
            )
        except Exception as e:
            logger.error(f"Error in start command: {e}")
            messages = [
                f"Hi {name}! I'm your AI companion. "
                "I'm having a small hiccup right now, but try sending me a message!"
            ]

        # Send each message with typing indicator
        chat_id = update.effective_chat.id
        for msg in messages:
            await self._send_with_typing(chat_id, msg)

    async def handle_text_message(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        Handle incoming text messages from users.
        Buffers rapid messages and processes them together after a quiet period.
        """
        user = update.effective_user
        chat_id = update.effective_chat.id
        message_text = update.message.text

        logger.info(f"Received message from {user.id} ({user.username}): {message_text[:50]}...")

        # Buffer the message
        if chat_id not in self._message_buffers:
            self._message_buffers[chat_id] = []
        self._message_buffers[chat_id].append(message_text)

        # Store user metadata (overwrite is fine, same user)
        self._debounce_metadata[chat_id] = {
            "telegram_id": user.id,
            "name": user.first_name or user.username,
            "username": user.username,
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
        await asyncio.sleep(self.DEBOUNCE_SECONDS)

        # Grab and clear the buffer
        buffered = self._message_buffers.pop(chat_id, [])
        metadata = self._debounce_metadata.pop(chat_id, {})
        self._debounce_tasks.pop(chat_id, None)

        if not buffered or not metadata:
            return

        # Combine into a single message
        combined = "\n".join(buffered)
        if len(buffered) > 1:
            logger.info(f"Debounced {len(buffered)} messages from {metadata['telegram_id']} into one")

        try:
            messages = await orchestrator.process_message(
                telegram_id=metadata["telegram_id"],
                message=combined,
                name=metadata["name"],
                username=metadata["username"],
            )
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            messages = [
                "I'm having a bit of trouble right now. "
                "Could you try again in a moment?"
            ]

        for msg in messages:
            await self._send_with_typing(chat_id, msg)

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
                from memory.models import (
                    Conversation, ProfileFact, ScheduledMessage,
                    TimelineEvent, DiaryEntry
                )
                from sqlalchemy import delete

                # Delete conversations
                await session.execute(
                    delete(Conversation).where(Conversation.user_id == user_id)
                )
                # Delete profile facts (includes onboarding_complete)
                await session.execute(
                    delete(ProfileFact).where(ProfileFact.user_id == user_id)
                )
                # Delete scheduled messages
                await session.execute(
                    delete(ScheduledMessage).where(ScheduledMessage.user_id == user_id)
                )
                # Delete timeline events
                await session.execute(
                    delete(TimelineEvent).where(TimelineEvent.user_id == user_id)
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
        """
        Handle the /debug command.
        Shows current user state for debugging.
        """
        user = update.effective_user
        telegram_id = user.id

        try:
            db_user = await memory_manager.get_or_create_user(telegram_id)
            user_id = db_user.id

            # Get profile
            profile = await memory_manager.get_user_profile(user_id)

            # Get conversation count
            conversations = await memory_manager.db.get_recent_conversations(user_id, limit=1000)
            conv_count = len(conversations)

            # Check onboarding status
            system = profile.get("system", {})
            onboarded = system.get("onboarding_complete", "false")

            # Count profile facts
            fact_count = sum(len(facts) for cat, facts in profile.items() if cat != "system")

            response = (
                f"🔧 Debug Info\n\n"
                f"User ID: {user_id}\n"
                f"Telegram ID: {telegram_id}\n"
                f"Onboarded: {onboarded}\n"
                f"Conversations: {conv_count}\n"
                f"Profile facts: {fact_count}\n\n"
                f"Use /observations to see what I've learned about you.\n"
                f"Use /scheduled to see pending follow-ups."
            )

            # Telegram has 4096 char limit
            if len(response) > 4000:
                response = response[:4000] + "\n\n... (truncated)"

            await update.message.reply_text(response)

        except Exception as e:
            logger.error(f"Error in debug command: {e}")
            await update.message.reply_text(f"Debug error: {e}")

    async def thinking_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Handle the /thinking command.
        Shows the companion's last internal reflection for debugging.
        """
        user = update.effective_user
        telegram_id = user.id

        try:
            db_user = await memory_manager.get_or_create_user(telegram_id)
            user_id = db_user.id

            thinking = SoulAgent.get_last_thinking(user_id)

            if thinking:
                response = f"🧠 Last internal reflection:\n\n{thinking}"
            else:
                response = "No thinking captured yet. Send a message first."

            await update.message.reply_text(response)

        except Exception as e:
            logger.error(f"Error in thinking command: {e}")
            await update.message.reply_text(f"Error: {e}")

    async def prompt_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Handle the /prompt command.
        Shows the last companion system prompt sent to the LLM.
        """
        user = update.effective_user
        telegram_id = user.id

        try:
            db_user = await memory_manager.get_or_create_user(telegram_id)
            user_id = db_user.id

            prompt = SoulAgent.get_last_system_prompt(user_id)

            if prompt:
                response = f"📋 Last companion prompt:\n\n{prompt}"
            else:
                response = "No prompt captured yet. Send a message first."

            await self._send_long_message(update.effective_chat.id, response)

        except Exception as e:
            logger.error(f"Error in prompt command: {e}")
            await update.message.reply_text(f"Error: {e}")

    async def observationprompt_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Handle the /observationprompt command.
        Shows the last observation prompt sent to the LLM.
        """
        user = update.effective_user
        telegram_id = user.id

        try:
            db_user = await memory_manager.get_or_create_user(telegram_id)
            user_id = db_user.id

            prompt = SoulAgent.get_last_observation_prompt(user_id)

            if prompt:
                response = f"📋 Last observation prompt:\n\n{prompt}"
            else:
                response = "No observation prompt captured yet. Send a message first."

            await self._send_long_message(update.effective_chat.id, response)

        except Exception as e:
            logger.error(f"Error in observationprompt command: {e}")
            await update.message.reply_text(f"Error: {e}")

    async def profile_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Handle the /profile command.
        Shows the profile context string as the LLM sees it.
        """
        user = update.effective_user
        telegram_id = user.id

        try:
            db_user = await memory_manager.get_or_create_user(telegram_id)
            user_id = db_user.id

            profile = SoulAgent.get_last_profile_context(user_id)

            if profile:
                response = f"👤 Profile context (what the LLM sees):\n\n{profile}"
            else:
                response = "No profile context captured yet. Send a message first."

            await self._send_long_message(update.effective_chat.id, response)

        except Exception as e:
            logger.error(f"Error in profile command: {e}")
            await update.message.reply_text(f"Error: {e}")

    async def observations_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Handle the /observations command.
        Shows recent profile observations with timestamps.
        """
        user = update.effective_user
        telegram_id = user.id

        try:
            db_user = await memory_manager.get_or_create_user(telegram_id)
            user_id = db_user.id

            # Get observations with dates
            observations = await memory_manager.get_observations_with_dates(user_id, limit=50)

            if not observations:
                await update.message.reply_text("No observations stored yet.")
                return

            # Group by category for display
            by_category = {}
            for obs in observations:
                # Format: "[2026-02-05] emotions: He's been struggling..."
                parts = obs.split("] ", 1)
                if len(parts) == 2:
                    date_str = parts[0][1:]  # Remove leading [
                    rest = parts[1]
                    cat_parts = rest.split(": ", 1)
                    if len(cat_parts) == 2:
                        category = cat_parts[0]
                        value = cat_parts[1]
                        if category not in by_category:
                            by_category[category] = []
                        by_category[category].append(f"[{date_str}] {value}")

            lines = ["🧠 Observations (with timestamps):\n"]
            for category, items in by_category.items():
                if category == "system":
                    continue
                lines.append(f"\n**{category}**:")
                for item in items[-10:]:  # Last 10 per category
                    display_val = item[:200] + "..." if len(item) > 200 else item
                    lines.append(f"  • {display_val}")

            response = "\n".join(lines)
            if len(response) > 4000:
                response = response[:4000] + "\n\n... (truncated)"

            await update.message.reply_text(response)

        except Exception as e:
            logger.error(f"Error in observations command: {e}")
            await update.message.reply_text(f"Error: {e}")

    async def scheduled_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Handle the /scheduled command.
        Shows all scheduled messages (including future ones) for debugging.
        """
        user = update.effective_user
        telegram_id = user.id

        try:
            db_user = await memory_manager.get_or_create_user(telegram_id)
            user_id = db_user.id

            # Get ALL scheduled messages for this user (not just due ones)
            user_scheduled = await memory_manager.get_user_scheduled_messages(user_id)

            if not user_scheduled:
                await update.message.reply_text("No scheduled messages for you.")
                return

            tz = pytz.timezone(settings.TIMEZONE)
            now = datetime.now(tz)

            lines = ["📅 Scheduled messages:\n"]
            for msg in user_scheduled:
                # Make scheduled_time timezone-aware if it isn't
                scheduled = msg.scheduled_time
                if scheduled.tzinfo is None:
                    scheduled = tz.localize(scheduled)

                time_str = scheduled.strftime("%b %d, %I:%M %p")
                # Show if it's due or upcoming
                if scheduled <= now:
                    status = "⏰ DUE"
                else:
                    status = "⏳"

                # Show context and raw observation output if available
                context_str = msg.context or msg.message_type
                lines.append(f"{status} {time_str}: {context_str}")

                # Show raw observation output for debugging
                if msg.message:
                    lines.append(f"   └─ Raw: {msg.message}")

            await update.message.reply_text("\n".join(lines))

        except Exception as e:
            logger.error(f"Error in scheduled command: {e}")
            await update.message.reply_text(f"Error: {e}")

    async def clearscheduled_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Handle the /clearscheduled command.
        Clears all pending scheduled messages for the user (debugging).
        """
        user = update.effective_user
        telegram_id = user.id

        try:
            db_user = await memory_manager.get_or_create_user(telegram_id)
            user_id = db_user.id

            count = await memory_manager.clear_scheduled_messages(user_id)
            await update.message.reply_text(f"🗑️ Cleared {count} scheduled message(s).")

        except Exception as e:
            logger.error(f"Error in clearscheduled command: {e}")
            await update.message.reply_text(f"Error: {e}")

    async def reflect_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Handle the /reflect command.
        Generates a fresh thoughtful message based on recent conversations and observations.
        """
        user = update.effective_user
        telegram_id = user.id

        try:
            db_user = await memory_manager.get_or_create_user(telegram_id)
            user_id = db_user.id
            user_name = db_user.name or user.first_name or "friend"

            # Show thinking indicator
            await update.message.reply_text("💭")

            # Get recent conversations
            recent_convos = await memory_manager.db.get_recent_conversations(user_id, limit=30)

            # Format conversations with timestamps (convert UTC to local)
            tz = pytz.timezone(settings.TIMEZONE)
            convo_lines = []
            for conv in recent_convos:
                role = "Them" if conv.role == "user" else "You"
                if conv.timestamp:
                    utc_time = conv.timestamp.replace(tzinfo=pytz.utc)
                    local_time = utc_time.astimezone(tz)
                    ts = local_time.strftime("%H:%M")
                else:
                    ts = ""
                convo_lines.append(f"[{ts}] {role}: {conv.message}")
            conversations_text = "\n".join(convo_lines) if convo_lines else "(No recent conversations)"

            # Get recent observations
            observations = await memory_manager.get_observations_with_dates(user_id, limit=50)

            if not observations and not convo_lines:
                await update.message.reply_text(
                    "we haven't talked enough yet for me to have something to say here. let's chat more first"
                )
                return

            # Generate fresh reflection
            from agents.soul_agent import soul_agent
            reflection_content = await soul_agent.generate_reflection(
                user_id=user_id,
                user_name=user_name,
                recent_observations=observations[-15:],  # Last 15 observations
                recent_conversations=conversations_text,
            )

            if reflection_content:
                await update.message.reply_text(reflection_content)
            else:
                await update.message.reply_text(
                    "hmm, couldn't quite gather my thoughts. try again?"
                )

        except Exception as e:
            logger.error(f"Error in reflect command: {e}")
            await update.message.reply_text(f"Error: {e}")
    async def compact_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Handle the /compact command.
        Manually triggers compact summarization and shows the full raw output.
        """
        user = update.effective_user
        telegram_id = user.id

        try:
            db_user = await memory_manager.get_or_create_user(telegram_id)
            user_id = db_user.id

            # Show thinking indicator
            await update.message.reply_text("📝 Creating compact summary...")

            # Get user context
            user_context = await memory_manager.get_user_context(user_id)
            
            # Build profile context (same as respond() does)
            from agents.soul_agent import soul_agent
            profile_context = soul_agent._build_profile_context(user_context)

            # Get recent conversations to check if there's anything to summarize
            recent_convos = await memory_manager.db.get_recent_conversations(user_id, limit=20)
            
            if not recent_convos:
                await update.message.reply_text("No recent conversations to summarize.")
                return

            # Run compact summarization
            await soul_agent._create_compact_summary(
                user_id=user_id,
                profile_context=profile_context,
            )

            # Get the compact prompt that was used
            compact_prompt = soul_agent._last_compact_prompt.get(user_id, "")

            # Get the most recent diary entry (should be the compact summary)
            diary_entries = await memory_manager.get_diary_entries(user_id, limit=5)
            
            compact_summary = None
            for entry in diary_entries:
                if entry.entry_type == "compact_summary":
                    compact_summary = entry
                    break

            if compact_summary:
                # Send the full raw output (non-truncated)
                response_parts = [
                    "✅ Compact Summary Generated\n",
                    "=" * 40,
                    "\nRAW OUTPUT:",
                    compact_summary.content,
                    "\n" + "=" * 40,
                    f"\nCreated: {compact_summary.timestamp.strftime('%Y-%m-%d %H:%M')}",
                    f"Stored as diary entry ID: {compact_summary.id}",
                ]
                
                response = "\n".join(response_parts)
                
                # Send using long message handler (splits if needed)
                await self._send_long_message(update.effective_chat.id, response)
                
                # Optionally show the prompt used (for debugging)
                if compact_prompt:
                    prompt_preview = f"\n📋 Prompt used (first 500 chars):\n{compact_prompt[:500]}..."
                    await update.message.reply_text(prompt_preview)
            else:
                await update.message.reply_text("⚠️ Compact summary was created but not found in diary entries.")

        except Exception as e:
            logger.error(f"Error in compact command: {e}")
            await update.message.reply_text(f"Error: {e}")


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

    async def _generate_proactive_message(
        self,
        user_id: int,
        context: str,
    ) -> str:
        """
        Generate a natural proactive message using the companion's voice.

        Args:
            user_id: Internal user ID
            context: What we're checking in about

        Returns:
            The generated message
        """
        try:
            # Get user context
            user_context = await memory_manager.get_user_context(user_id)

            # Build profile context
            profile_parts = []
            if user_context.user_info.name:
                profile_parts.append(f"Their name is {user_context.user_info.name}.")
            if user_context.profile:
                for category, facts in user_context.profile.items():
                    if category == "system":
                        continue
                    for value in facts.values():
                        profile_parts.append(f"- {value}")
            profile_context = "\n".join(profile_parts) if profile_parts else "(You're still getting to know them)"

            # Get recent conversation for tone matching
            tz = pytz.timezone(settings.TIMEZONE)
            conversations = await memory_manager.db.get_recent_conversations(user_id, limit=10)
            if conversations:
                history_lines = []
                for conv in conversations[-5:]:
                    role = "Them" if conv.role == "user" else "You"
                    if conv.timestamp:
                        utc_time = conv.timestamp.replace(tzinfo=pytz.utc)
                        local_time = utc_time.astimezone(tz)
                        ts = local_time.strftime("%H:%M")
                    else:
                        ts = ""
                    history_lines.append(f"[{ts}] {role}: {conv.message}")
                recent_history = "\n".join(history_lines)
            else:
                recent_history = "(No recent conversation)"

            # Generate the message
            prompt = PROACTIVE_MESSAGE_PROMPT.format(
                profile_context=profile_context,
                context=context,
                recent_history=recent_history,
            )

            message = await llm_client.chat(
                model=settings.MODEL_PROACTIVE,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=100,
            )

            message = message.strip()

            # LLM decided this check-in isn't appropriate right now
            if message.upper() == "SKIP":
                logger.info(f"Skipping proactive message - LLM determined not appropriate")
                return None

            return message

        except Exception as e:
            logger.error(f"Failed to generate proactive message: {e}")
            return None

    async def _process_scheduled_messages(self, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Check for and process any pending scheduled messages.
        This runs periodically via JobQueue.
        """
        try:
            pending = await memory_manager.get_pending_scheduled_messages()

            if not pending:
                return

            logger.info(f"Processing {len(pending)} pending scheduled messages")

            tz = pytz.timezone(settings.TIMEZONE)
            now = datetime.now(tz)
            stale_threshold = timedelta(hours=1)  # Skip messages more than 1 hour old
            sent_to_users = set()  # Rate limit: max 1 message per user per cycle

            for scheduled_msg in pending:
                try:
                    # Check if message is stale (more than 1 hour past scheduled time)
                    scheduled_time = scheduled_msg.scheduled_time
                    if scheduled_time.tzinfo is None:
                        scheduled_time = tz.localize(scheduled_time)

                    if now - scheduled_time > stale_threshold:
                        logger.info(f"Skipping stale message {scheduled_msg.id} (scheduled for {scheduled_time})")
                        await memory_manager.mark_message_executed(scheduled_msg.id)
                        continue

                    # Rate limit: only send one message per user per cycle
                    if scheduled_msg.user_id in sent_to_users:
                        logger.debug(f"Rate limiting: already sent to user {scheduled_msg.user_id} this cycle")
                        continue  # Don't mark as executed - try again next cycle

                    # Get user's telegram_id
                    user = await memory_manager.get_user_by_id(scheduled_msg.user_id)
                    if not user:
                        logger.warning(f"User {scheduled_msg.user_id} not found, skipping")
                        await memory_manager.mark_message_executed(scheduled_msg.id)
                        continue

                    # Generate the message
                    message_text = await self._generate_proactive_message(
                        user_id=scheduled_msg.user_id,
                        context=scheduled_msg.context or "general check-in",
                    )

                    if message_text:
                        # Send the message
                        await self.send_message(user.telegram_id, message_text)
                        sent_to_users.add(scheduled_msg.user_id)

                        # Store in conversation history
                        await memory_manager.add_conversation(
                            user_id=scheduled_msg.user_id,
                            role="assistant",
                            message=message_text,
                            store_in_vector=False,
                        )

                        logger.info(
                            f"Sent scheduled message to user {scheduled_msg.user_id}: {message_text[:50]}..."
                        )

                    # Mark as executed
                    await memory_manager.mark_message_executed(scheduled_msg.id)

                except Exception as e:
                    logger.error(f"Failed to process scheduled message {scheduled_msg.id}: {e}")
                    # Still mark as executed to avoid infinite retry
                    await memory_manager.mark_message_executed(scheduled_msg.id)

        except Exception as e:
            logger.error(f"Error in scheduled message processor: {e}")

    def setup_handlers(self) -> None:
        """Set up message and command handlers."""
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
            CommandHandler("observationprompt", self.observationprompt_command)
        )
        self.application.add_handler(
            CommandHandler("profile", self.profile_command)
        )
        self.application.add_handler(
            CommandHandler("observations", self.observations_command)
        )
        self.application.add_handler(
            CommandHandler("scheduled", self.scheduled_command)
        )
        self.application.add_handler(
            CommandHandler("clearscheduled", self.clearscheduled_command)
        )
        self.application.add_handler(
            CommandHandler("reflect", self.reflect_command)
        )
        self.application.add_handler(
            CommandHandler("compact", self.compact_command)
        )

        # Message handlers
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text_message)
        )
        self.application.add_handler(
            MessageHandler(filters.PHOTO, self.handle_photo_message)
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

        # Set up the proactive messaging scheduler
        # Check for pending scheduled messages every 5 minutes
        job_queue = self.application.job_queue
        job_queue.run_repeating(
            self._process_scheduled_messages,
            interval=300,  # 5 minutes
            first=60,  # Start after 1 minute
            name="scheduled_message_processor",
        )
        logger.info("Proactive messaging scheduler configured (every 5 minutes)")

        # Start the bot
        logger.info("Starting Telegram bot...")
        self.application.run_polling(allowed_updates=Update.ALL_TYPES)


# Singleton instance
bot = TelegramBot()
