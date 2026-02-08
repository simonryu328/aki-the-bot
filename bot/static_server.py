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

async def get_user_settings(request):
    """Get user settings from database."""
    try:
        import json
        from memory.database_async import db
        
        # Get telegram_id from query params
        telegram_id = request.query.get('telegram_id')
        if not telegram_id:
            return web.Response(status=400, text="Missing telegram_id")
        
        telegram_id = int(telegram_id)
        
        # Get user from database
        user = await db.get_user_by_telegram_id(telegram_id)
        if not user:
            return web.Response(status=404, text="User not found")
        
        # Return settings as JSON
        settings = {
            'timezone': user.timezone,
            'location_latitude': user.location_latitude,
            'location_longitude': user.location_longitude,
            'location_name': user.location_name,
            'reach_out_enabled': user.reach_out_enabled
        }
        
        return web.json_response(settings)
        
    except Exception as e:
        logger.error(f"Error fetching user settings: {e}")
        return web.Response(status=500, text=str(e))

def create_app():
    """Create and configure the aiohttp application."""
    app = web.Application()
    
    # Add route for static files
    app.router.add_get('/static/{path:.*}', serve_static)
    
    # API endpoint for user settings
    app.router.add_get('/api/settings', get_user_settings)
    
    # Health check endpoint (useful for Railway)
    async def health(request):
        return web.Response(text="OK")
    
    app.router.add_get('/health', health)
    app.router.add_get('/', health)  # Root also returns OK
    
    logger.info("Static file server configured")
    return app

# Made with Bob
