"""
Startup script for the Telegram Mini App API server.
Runs FastAPI with uvicorn.
"""

import logging
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.logging_config import setup_logging
from config.settings import settings

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)


def main():
    """Start the FastAPI server"""
    import uvicorn
    
    # Determine host and port
    host = "0.0.0.0"
    port = settings.MINIAPP_PORT if hasattr(settings, 'MINIAPP_PORT') else 8000
    
    logger.info(f"Starting Telegram Mini App API server on {host}:{port}")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    
    # Run the server
    uvicorn.run(
        "miniapp.api:app",
        host=host,
        port=port,
        reload=settings.is_development,
        log_level=settings.LOG_LEVEL.lower(),
        access_log=True
    )


if __name__ == "__main__":
    main()

# Made with Bob
