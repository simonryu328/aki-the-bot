"""
AI Companion - Personal AI agent that cares deeply about the user.
Main entry point for the application.
"""

import os
import logging
import asyncio
from aiohttp import web
from bot.telegram_handler import bot
from bot.static_server import create_app

logger = logging.getLogger(__name__)


async def start_web_server():
    """Start the web server for static files."""
    app = create_app()
    port = int(os.getenv('PORT', 8080))
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    
    logger.info(f"Web server started on port {port}")
    logger.info(f"Static files available at http://0.0.0.0:{port}/static/")
    
    return runner


def main():
    """Start the AI Companion bot and web server."""
    try:
        logger.info("=" * 50)
        logger.info("AI Companion Starting...")
        logger.info("=" * 50)

        # Create event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Start web server
        runner = loop.run_until_complete(start_web_server())
        
        try:
            # Start the Telegram bot (blocking call)
            bot.run()
        finally:
            # Cleanup web server
            loop.run_until_complete(runner.cleanup())

    except KeyboardInterrupt:
        logger.info("\nShutting down gracefully...")
    except Exception as e:
        logger.error(f"Error starting bot: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
