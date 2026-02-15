# Aki - AI Companion Bot

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

A sophisticated AI companion bot for Telegram that builds genuine, long-term relationships through advanced memory management and context-aware conversations.

## 🌟 Key Innovations

### 1. **Dual-Layer Memory Architecture**
- **Structured Storage**: PostgreSQL for reliable, queryable conversation history and user profiles
- **Semantic Search**: Pinecone vector store for context-aware memory retrieval
- **Graceful Degradation**: System continues functioning even if vector store is unavailable

### 2. **Time-Windowed Compact Summarization**
Novel approach to conversation compression that:
- Automatically creates summaries of conversation exchanges with precise timestamps
- Prevents context duplication by tracking exchange boundaries
- Enables efficient long-term memory without token bloat
- Maintains temporal awareness across conversations

### 3. **Soul Agent System**
Unique multi-stage processing pipeline:
- **Thinking Layer**: Internal reasoning before responding (never shown to user)
- **Observation Agent**: Extracts significant facts and schedules follow-ups
- **Reflection System**: Generates proactive check-ins based on user patterns
- **Emoji Reactions**: Context-aware emotional responses

### 4. **Swappable Persona Framework**
Modular personality system that separates:
- **System Frame**: Structural scaffolding for prompts
- **Persona Modules**: Pluggable personality definitions
- **Context Assembly**: Dynamic integration of user history, time, and observations

### 5. **Intelligent Message Splitting**
Advanced text processing that:
- Supports `[BREAK]` markers for natural multi-message responses
- Auto-splits long responses at sentence boundaries
- Maintains conversational flow across multiple messages

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Telegram Bot Layer                       │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│                  Agent Orchestrator                          │
│  • Routes messages                                           │
│  • Manages conversation flow                                 │
│  • Coordinates memory operations                             │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│                     Soul Agent                               │
│  • Thinking/reasoning layer                                  │
│  • Context-aware response generation                         │
│  • Observation extraction                                    │
│  • Compact summarization                                     │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│                  Memory Manager                              │
│  ┌──────────────────┐         ┌──────────────────┐          │
│  │   PostgreSQL     │         │  Pinecone Vector │          │
│  │   (Structured)   │◄───────►│  Store (Semantic)│          │
│  └──────────────────┘         └──────────────────┘          │
│  • User profiles              • Semantic search             │
│  • Conversations              • Memory retrieval            │
│  • Timeline events            • Context ranking             │
│  • Diary entries                                            │
│  • Scheduled messages                                       │
└─────────────────────────────────────────────────────────────┘
```

## 🚀 Features

- **Long-term Memory**: Remembers conversations, facts, and context across sessions
- **Proactive Engagement**: Reaches out based on user patterns and scheduled follow-ups
- **Time-Aware**: Understands temporal context and schedules future interactions
- **Personality System**: Swappable personas for different interaction styles
- **Observation Tracking**: Automatically extracts and stores significant information
- **Compact Summaries**: Efficient conversation compression with timestamp tracking
- **Emoji Reactions**: Context-aware emotional responses to messages
- **Multi-Message Responses**: Natural conversation flow with intelligent message splitting

## 📋 Technical Stack

- **Language**: Python 3.11+
- **Bot Framework**: python-telegram-bot (async)
- **Database**: PostgreSQL with async SQLAlchemy
- **Vector Store**: Pinecone (optional)
- **LLM**: OpenAI GPT-4 / Anthropic Claude
- **Deployment**: Railway / Docker
- **Package Manager**: uv

## 🛠️ Core Components

### Memory System
- `memory/database_async.py` - Async PostgreSQL operations
- `memory/memory_manager_async.py` - Unified memory interface
- `memory/vector_store.py` - Semantic search with Pinecone
- `memory/models.py` - SQLAlchemy ORM models

### Agent System
- `agents/orchestrator.py` - Message routing and coordination
- `agents/soul_agent.py` - Core conversational AI with thinking layer

### Prompts
- `prompts/system_frame.py` - Structural prompt scaffolding
- `prompts/personas/` - Swappable personality modules
- `prompts/compact.py` - Conversation summarization
- `prompts/observation.py` - Fact extraction
- `prompts/reach_out.py` - Proactive messaging

## 🕹️ Bot Commands

For a full list of available commands and instructions on how to add new ones, see the [Telegram Commands Guide](docs/TELEGRAM_COMMANDS.md).

## 📊 Data Models

### User Profile
- Basic info (name, username, telegram_id)
- Reach-out configuration
- Last interaction timestamps

### Conversations
- Role-based messages (user/assistant)
- Thinking layer (internal reasoning)
- Timestamps and metadata

### Profile Facts
- Categorized observations
- Confidence scores
- Timestamp tracking

### Diary Entries
- Milestone moments
- Compact summaries with exchange timestamps
- Importance ratings

### Scheduled Messages
- Follow-up reminders
- Proactive check-ins
- Context-aware timing

## 🔒 Security & Privacy

- Environment-based configuration (`.env`)
- Secure credential management
- User data isolation
- Optional vector store (can run without)

## 📈 Performance

- Async/await throughout for high concurrency
- Efficient database queries with proper indexing
- Graceful degradation when services unavailable
- Smart context windowing to manage token usage

## 🎯 Use Cases

- **Personal Companion**: Long-term relationship building
- **Mental Health Support**: Empathetic listening and check-ins
- **Goal Tracking**: Follow-ups on user objectives
- **Memory Assistant**: Remembering important details and events

## 📝 License

Copyright 2026 Simon Ryu

Licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE) for details.

This project implements proprietary algorithms and architectural patterns. While the code is open source, the underlying concepts represent significant intellectual property.

## 🙏 Acknowledgments

Built with inspiration from:
- Soul Engine's approach to AI consciousness
- Long-term memory systems in cognitive science
- Natural conversation patterns in human relationships

---

**Note**: This is a portfolio project demonstrating advanced AI engineering, memory systems, and conversational design. The innovations in memory architecture, compact summarization, and persona frameworks represent novel approaches to building long-term AI companions.