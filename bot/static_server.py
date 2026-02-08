"""Simple static file server for Telegram mini apps."""
import os
from aiohttp import web
import logging

logger = logging.getLogger(__name__)

async def serve_static(request):
    """Serve static files from the static/ directory."""
    # Get the requested path (e.g., "settings/index.html")
    path = request.match_info.get('path', 'index.html')
    
    # Build full file path
    static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static')
    file_path = os.path.join(static_dir, path)
    
    # Security: prevent directory traversal
    if not os.path.abspath(file_path).startswith(os.path.abspath(static_dir)):
        return web.Response(status=403, text="Forbidden")
    
    # Check if file exists
    if not os.path.exists(file_path):
        logger.warning(f"File not found: {file_path}")
        return web.Response(status=404, text="Not Found")
    
    # Serve the file with appropriate content type
    content_type = 'text/html'
    if file_path.endswith('.js'):
        content_type = 'application/javascript'
    elif file_path.endswith('.css'):
        content_type = 'text/css'
    elif file_path.endswith('.json'):
        content_type = 'application/json'
    
    return web.FileResponse(file_path, headers={'Content-Type': content_type})

def create_app():
    """Create and configure the aiohttp application."""
    app = web.Application()
    
    # Add route for static files
    app.router.add_get('/static/{path:.*}', serve_static)
    
    # Health check endpoint (useful for Railway)
    async def health(request):
        return web.Response(text="OK")
    
    app.router.add_get('/health', health)
    app.router.add_get('/', health)  # Root also returns OK
    
    logger.info("Static file server configured")
    return app

# Made with Bob
