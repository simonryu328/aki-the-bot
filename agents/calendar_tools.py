CALENDAR_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_calendar_events",
            "description": "List Google Calendar events for a specific time range.",
            "parameters": {
                "type": "object",
                "properties": {
                    "days_ahead": {
                        "type": "integer",
                        "description": "Number of days ahead to list events for. Defaults to 1 (includes today).",
                        "default": 1
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of events to return.",
                        "default": 10
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_calendar_event",
            "description": "Create a new event in the user's Google Calendar. Ask user for confirmation first if they haven't explicitly asked to 'add' something.",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {
                        "type": "string",
                        "description": "The title/subject of the event."
                    },
                    "start_time": {
                        "type": "string",
                        "description": "ISO format start time with timezone (e.g. '2026-03-08T15:00:00-04:00')."
                    },
                    "end_time": {
                        "type": "string",
                        "description": "ISO format end time with timezone (e.g. '2026-03-08T16:00:00-04:00'). If not provided, it will default to 1 hour after start_time."
                    },
                    "description": {
                        "type": "string",
                        "description": "A brief description or notes for the event."
                    },
                    "location": {
                        "type": "string",
                        "description": "Physical location for the event."
                    }
                },
                "required": ["summary", "start_time"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_calendar_event",
            "description": "Update an existing calendar event. Need the eventId from list_calendar_events first.",
            "parameters": {
                "type": "object",
                "properties": {
                    "event_id": {
                        "type": "string",
                        "description": "The unique Google Calendar ID of the event to update."
                    },
                    "summary": {
                        "type": "string",
                        "description": "The updated title."
                    },
                    "start_time": {
                        "type": "string",
                        "description": "The updated ISO format start time."
                    },
                    "end_time": {
                        "type": "string",
                        "description": "The updated ISO format end time."
                    },
                    "description": {
                        "type": "string",
                        "description": "The updated description."
                    },
                    "location": {
                        "type": "string",
                        "description": "The updated location."
                    }
                },
                "required": ["event_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_calendar_event",
            "description": "Remove an event from the user's Google Calendar. Ask for confirmation first.",
            "parameters": {
                "type": "object",
                "properties": {
                    "event_id": {
                        "type": "string",
                        "description": "The unique Google Calendar ID of the event to remove."
                    }
                },
                "required": ["event_id"]
            }
        }
    }
]
