"""
Start the Telegram bot.
Used for Railway deployment to run the service.
"""
import sys
import logging
import signal

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def run_bot():
    """Run the Telegram bot"""
    try:
        logger.info("🤖 Starting Telegram bot...")
        from main import main
        main()
    except Exception as e:
        logger.error(f"❌ Bot crashed: {e}", exc_info=True)
        sys.exit(1)


def signal_handler(signum, frame):
    """Handle shutdown signals"""
    logger.info("🛑 Received shutdown signal, cleaning up...")
    sys.exit(0)


if __name__ == "__main__":
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    logger.info("🚀 Starting Aki Bot...")
    logger.info("=" * 50)
    
    run_bot()
