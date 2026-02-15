# Telegram Bot Commands Guide

This document describes the available Telegram commands for the Aki AI Companion and provides a guide for developers on how to register new commands.

## 🕹️ Available Commands

### Core Commands
| Command | Description |
|---------|-------------|
| `/start` | Initialize or restart the relationship with Aki. Triggers onboarding for new users. |
| `/app` | Sets the Telegram Menu Button to open the Aki Mini App dashboard. |
| `/help` | Displays a list of all available commands and their descriptions. |
| `/memory` | Browse conversation memories. Use `/memory list` for a summary or `/memory <n>` for details. |

### User Settings & Data
| Command | Description |
|---------|-------------|
| `/reset` | **CAUTION**: Clears all conversation history and diary entries for a fresh start. |
| `/reachout_settings` | View current proactive reach-out configuration (status, min/max silence). |
| `/reachout_enable` | Enable automatic proactive messages from Aki. |
| `/reachout_disable` | Disable automatic proactive messages. |
| `/reachout_min <hours>` | Set the minimum silence duration before Aki might reach out. |
| `/reachout_max <days>` | Set the maximum days of silence before Aki stops trying to reach out. |

### Technical & Debug
| Command | Description |
|---------|-------------|
| `/debug` | Show technical state info (User ID, message counts, etc.). |
| `/thinking` | View Aki's last internal reflection ("thinking layer") for the most recent message. |
| `/prompt` | View the specific conversation context Aki is currently remembering. |
| `/raw` | View the last raw LLM response before any parsing or formatting. |

---

## 🛠️ Developer Guide: Registering New Commands

Aki uses a consistent pattern for handling Telegram commands within the `bot/telegram_handler.py` module. Follow these steps to add a new command:

### 1. Create the Handler Method
Add an asynchronous method to the `TelegramBot` class in `bot/telegram_handler.py`. Follow the signature:

```python
async def my_new_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Implement your command logic here."""
    user = update.effective_user
    chat_id = update.effective_chat.id
    
    # Example logic
    await update.message.reply_text("Custom command response!")
```

### 2. Register the Handler
In the `setup_handlers` method of `TelegramBot`, add your new command to the `CommandHandler` list. Group it with related commands for better organization:

```python
def setup_handlers(self) -> None:
    # ... existing handlers ...
    
    # New category or existing one
    self.application.add_handler(CommandHandler("mynewcmd", self.my_new_command))
    
    # ...
```

### 3. Update the Help Command
To ensure users can discover your command, add it to the `help_command` list within `bot/telegram_handler.py`:

```python
async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    commands = [
        # ...
        ("mynewcmd", "Brief description of what it does"),
    ]
    # ...
```

### Best Practices
- **Naming**: Use lowercase for command names. Use underscores for multi-word commands (e.g., `/reachout_settings`).
- **Feedback**: Always provide a clear success or error message to the user.
- **Security**: If a command modified sensitive data (like `/reset`), use a confirmation message or clear warnings.
- **Mini App Integration**: For commands that interact with the web UI, ensure you use `settings.WEBHOOK_URL` to point to the correct deployment.
