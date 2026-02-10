"""
AI Companion - Personal AI agent that cares deeply about the user.
Main entry point for the application.
"""

import logging
from bot.telegram_handler import bot

logger = logging.getLogger(__name__)


def main():
    """Start the AI Companion bot."""
    try:
        logger.info("=" * 50)
        logger.info("AI Companion Starting...")
        logger.info("=" * 50)

        # Start the Telegram bot (blocking call)
        bot.run()

    except KeyboardInterrupt:
        logger.info("\nShutting down gracefully...")
    except Exception as e:
        logger.error(f"Error starting bot: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
