import logging
from datetime import datetime, timedelta
import pytz
from typing import List, Dict, Any, Optional
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from utils.google_client import google_client

logger = logging.getLogger(__name__)

async def get_calendar_service(user):
    """Utility to build the calendar v3 service."""
    return await google_client.build_service(user, 'calendar', 'v3')

async def list_events(user, calendar_id: str = "primary", max_results: int = 10, days_ahead: int = 1) -> List[Dict[str, Any]]:
    """Get list of events for the next N days."""
    service = await get_calendar_service(user)
    if not service:
        return []
    
    now = datetime.utcnow().isoformat() + 'Z' # 'Z' indicates UTC time
    end = (datetime.utcnow() + timedelta(days=days_ahead)).isoformat() + 'Z'
    
    try:
        events_result = service.events().list(
            calendarId=calendar_id, 
            timeMin=now,
            timeMax=end,
            maxResults=max_results, 
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        return events_result.get('items', [])
    except Exception as e:
        logger.error(f"Failed to list calendar events: {e}")
        return []

async def create_event(
    user, 
    summary: str, 
    start_time: str, 
    end_time: str, 
    description: str = "", 
    location: str = "",
    calendar_id: str = "primary"
) -> Dict[str, Any]:
    """Create a new calendar event."""
    service = await get_calendar_service(user)
    if not service:
        return {"success": False, "error": "Google account not connected"}
    
    event = {
        'summary': summary,
        'location': location,
        'description': description,
        'start': {
            'dateTime': start_time,
            'timeZone': user.timezone,
        },
        'end': {
            'dateTime': end_time,
            'timeZone': user.timezone,
        }
    }
    
    try:
        event = service.events().insert(calendarId=calendar_id, body=event).execute()
        return {"success": True, "event_id": event.get('id'), "link": event.get('htmlLink')}
    except Exception as e:
        logger.error(f"Failed to create calendar event: {e}")
        return {"success": False, "error": str(e)}

async def update_event(
    user, 
    event_id: str,
    summary: Optional[str] = None, 
    start_time: Optional[str] = None, 
    end_time: Optional[str] = None, 
    description: Optional[str] = None, 
    location: Optional[str] = None,
    calendar_id: str = "primary"
) -> Dict[str, Any]:
    """Update an existing calendar event."""
    service = await get_calendar_service(user)
    if not service:
        return {"success": False, "error": "Google account not connected"}
    
    try:
        # Get existing event first to maintain existing fields
        event = service.events().get(calendarId=calendar_id, eventId=event_id).execute()
        
        if summary: event['summary'] = summary
        if location: event['location'] = location
        if description: event['description'] = description
        if start_time: 
            event['start']['dateTime'] = start_time
            event['start']['timeZone'] = user.timezone
        if end_time: 
            event['end']['dateTime'] = end_time
            event['end']['timeZone'] = user.timezone
            
        updated_event = service.events().update(calendarId=calendar_id, eventId=event_id, body=event).execute()
        return {"success": True, "event_id": updated_event.get('id'), "link": updated_event.get('htmlLink')}
    except Exception as e:
        logger.error(f"Failed to update calendar event: {e}")
        return {"success": False, "error": str(e)}

async def delete_event(user, event_id: str, calendar_id: str = "primary") -> Dict[str, Any]:
    """Remove a calendar event."""
    service = await get_calendar_service(user)
    if not service:
        return {"success": False, "error": "Google account not connected"}
    
    try:
        service.events().delete(calendarId=calendar_id, eventId=event_id).execute()
        return {"success": True}
    except Exception as e:
        logger.error(f"Failed to delete calendar event: {e}")
        return {"success": False, "error": str(e)}
