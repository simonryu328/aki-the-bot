"""
Start both the Telegram bot and Mini App API server.
Used for Railway deployment to run both services in a single container.
"""
import multiprocessing
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


def run_miniapp():
    """Run the Mini App API"""
    try:
        logger.info("🌐 Starting Mini App API...")
        import uvicorn
        from miniapp.api import app
        from config.settings import settings
        import os
        
        # Railway sets PORT env var, use it if available
        port = int(os.environ.get("PORT", settings.MINIAPP_PORT if hasattr(settings, 'MINIAPP_PORT') else 8000))
        
        logger.info(f"📡 Mini App API will listen on port {port}")
        
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=port,
            log_level=settings.LOG_LEVEL.lower() if hasattr(settings, 'LOG_LEVEL') else "info",
            access_log=True
        )
    except Exception as e:
        logger.error(f"❌ Mini App API crashed: {e}", exc_info=True)
        sys.exit(1)


def signal_handler(signum, frame):
    """Handle shutdown signals"""
    logger.info("🛑 Received shutdown signal, cleaning up...")
    sys.exit(0)


if __name__ == "__main__":
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    logger.info("🚀 Starting Aki Bot with Mini App API...")
    logger.info("=" * 50)
    
    # Start both processes
    bot_process = multiprocessing.Process(target=run_bot, name="TelegramBot")
    api_process = multiprocessing.Process(target=run_miniapp, name="MiniAppAPI")
    
    bot_process.start()
    api_process.start()
    
    logger.info("✅ Both services started successfully")
    logger.info("=" * 50)
    
    try:
        # Wait for both processes
        bot_process.join()
        api_process.join()
    except KeyboardInterrupt:
        logger.info("🛑 Keyboard interrupt received, shutting down...")
    finally:
        # Ensure both processes are terminated
        if bot_process.is_alive():
            logger.info("Terminating bot process...")
            bot_process.terminate()
            bot_process.join(timeout=5)
            if bot_process.is_alive():
                bot_process.kill()
        
        if api_process.is_alive():
            logger.info("Terminating API process...")
            api_process.terminate()
            api_process.join(timeout=5)
            if api_process.is_alive():
                api_process.kill()
        
        logger.info("👋 Shutdown complete")
        sys.exit(0)

# Made with Bob
