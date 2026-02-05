"""
Telegram bot handler for receiving and sending messages.
Handles text messages, images, and commands.
"""

import logging
from typing import Optional
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

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=getattr(logging, settings.LOG_LEVEL)
)
logger = logging.getLogger(__name__)


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

            # Format profile for display
            profile_str = ""
            for category, facts in profile.items():
                if category == "system":
                    continue  # Skip system facts in display
                if facts:
                    profile_str += f"\n{category}:\n"
                    for value in facts.values():
                        profile_str += f"  - {value}\n"

            response = (
                f"User ID: {user_id}\n"
                f"Telegram ID: {telegram_id}\n"
                f"Onboarded: {onboarded}\n"
                f"Conversations: {conv_count}\n"
                f"\nProfile:{profile_str if profile_str else ' (empty)'}"
            )

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

        # Start the bot
        logger.info("Starting Telegram bot...")
        self.application.run_polling(allowed_updates=Update.ALL_TYPES)


# Singleton instance
bot = TelegramBot()
