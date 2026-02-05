"""
Telegram bot handler for receiving and sending messages.
Handles text messages, images, and commands.
Also runs the proactive messaging scheduler.
"""

import logging
from typing import Optional
from datetime import datetime
import pytz
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

from config.settings import settings
from agents import orchestrator
from agents.companion_agent import CompanionAgent
from memory.memory_manager_async import memory_manager
from utils.llm_client import llm_client

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=getattr(logging, settings.LOG_LEVEL)
)
logger = logging.getLogger(__name__)


# Prompt for generating proactive check-in messages
PROACTIVE_MESSAGE_PROMPT = """You're reaching out to someone you care about.

You're not responding to them - you're initiating. This is a natural check-in, like a friend who remembered something they mentioned.

What you know about them:
{profile_context}

What you're checking in about:
{context}

Last few messages (for context on how you two talk):
{recent_history}

---

Write a SHORT, natural message. Like a text from a friend:
- 1-2 sentences max
- Casual, warm
- Don't be formal or overly enthusiastic
- Can use emoji sparingly if natural

Examples of good check-ins:
- "hey how'd the interview go?"
- "did tony ever text back? 👀"
- "thinking about you, hope the visit with your mom went okay"

Just write the message, nothing else.
"""


class TelegramBot:
    """Telegram bot handler for the AI Companion."""

    def __init__(self):
        """Initialize the Telegram bot."""
        self.application: Optional[Application] = None

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Handle the /start command.
        Kicks off the onboarding conversation for new users.
        """
        import asyncio

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

        # Send each message with a small delay
        for i, msg in enumerate(messages):
            if i > 0:
                delay = min(0.5 + len(msg) * 0.01, 1.5)
                await asyncio.sleep(delay)
            await update.message.reply_text(msg)

    async def handle_text_message(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        Handle incoming text messages from users.
        Routes through AgentOrchestrator for processing.
        """
        import asyncio

        user = update.effective_user
        telegram_id = user.id
        name = user.first_name or user.username
        username = user.username
        message_text = update.message.text

        logger.info(f"Received message from {telegram_id} ({username}): {message_text[:50]}...")

        try:
            # Process through orchestrator - returns list of messages
            messages = await orchestrator.process_message(
                telegram_id=telegram_id,
                message=message_text,
                name=name,
                username=username,
            )
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            messages = [
                "I'm having a bit of trouble right now. "
                "Could you try again in a moment?"
            ]

        # Send each message with a small delay for natural feel
        for i, msg in enumerate(messages):
            if i > 0:
                # Small delay between messages (0.5-1.5 seconds based on length)
                delay = min(0.5 + len(msg) * 0.01, 1.5)
                await asyncio.sleep(delay)
            await update.message.reply_text(msg)

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

            # Clear conversations and profile facts
            async with memory_manager.db.get_session() as session:
                from memory.models import Conversation, ProfileFact
                from sqlalchemy import delete

                # Delete conversations
                await session.execute(
                    delete(Conversation).where(Conversation.user_id == user_id)
                )
                # Delete profile facts (includes onboarding_complete)
                await session.execute(
                    delete(ProfileFact).where(ProfileFact.user_id == user_id)
                )
                await session.commit()

            logger.info(f"Reset complete for user {user_id}")
            await update.message.reply_text(
                "Your data has been reset. Send /start to begin fresh onboarding."
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

            thinking = CompanionAgent.get_last_thinking(user_id)

            if thinking:
                response = f"🧠 Last internal reflection:\n\n{thinking}"
            else:
                response = "No thinking captured yet. Send a message first."

            await update.message.reply_text(response)

        except Exception as e:
            logger.error(f"Error in thinking command: {e}")
            await update.message.reply_text(f"Error: {e}")

    async def observations_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Handle the /observations command.
        Shows recent profile observations for debugging.
        """
        user = update.effective_user
        telegram_id = user.id

        try:
            db_user = await memory_manager.get_or_create_user(telegram_id)
            user_id = db_user.id

            # Get all profile facts
            profile = await memory_manager.get_user_profile(user_id)

            if not profile:
                await update.message.reply_text("No observations stored yet.")
                return

            lines = ["🧠 Stored observations:\n"]
            for category, facts in profile.items():
                if category == "system":
                    continue
                if facts:
                    lines.append(f"\n**{category}**:")
                    for value in facts.values():
                        # Show full value, truncate only if very long
                        display_val = value[:200] + "..." if len(value) > 200 else value
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
                lines.append(f"{status} {time_str}: {msg.context or msg.message_type}")

            await update.message.reply_text("\n".join(lines))

        except Exception as e:
            logger.error(f"Error in scheduled command: {e}")
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
            await self.application.bot.send_message(
                chat_id=telegram_id,
                text=message
            )
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
            conversations = await memory_manager.db.get_recent_conversations(user_id, limit=10)
            if conversations:
                history_lines = []
                for conv in conversations[-5:]:
                    role = "Them" if conv.role == "user" else "You"
                    history_lines.append(f"{role}: {conv.message}")
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
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=100,
            )

            return message.strip()

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

            for scheduled_msg in pending:
                try:
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

                        # Store in conversation history
                        await memory_manager.add_conversation(
                            user_id=scheduled_msg.user_id,
                            role="assistant",
                            message=message_text,
                            store_in_vector=True,
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
            CommandHandler("observations", self.observations_command)
        )
        self.application.add_handler(
            CommandHandler("scheduled", self.scheduled_command)
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
