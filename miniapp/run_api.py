"""
Startup script for the Telegram Mini App API server.
Runs FastAPI with uvicorn.
"""

import logging
import sys
import os
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Setup basic logging (don't import from core to avoid bot imports)
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def main():
    """Start the FastAPI server"""
    import uvicorn
    
    # Determine host and port from environment
    host = "0.0.0.0"
    port = int(os.environ.get("PORT", os.environ.get("MINIAPP_PORT", "8000")))
    environment = os.environ.get("ENVIRONMENT", "production")
    log_level = os.environ.get("LOG_LEVEL", "INFO").lower()
    
    logger.info(f"Starting Telegram Mini App API server on {host}:{port}")
    logger.info(f"Environment: {environment}")
    
    # Run the server
    uvicorn.run(
        "miniapp.api:app",
        host=host,
        port=port,
        reload=(environment == "development"),
        log_level=log_level,
        access_log=True
    )


if __name__ == "__main__":
    main()

# Made with Bob
