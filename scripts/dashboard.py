"""
Streamlit dashboard for monitoring beta testers.

Usage:
    uv run streamlit run scripts/dashboard.py
"""

import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytz
import streamlit as st
from sqlalchemy import create_engine, select, desc, func
from sqlalchemy.orm import Session, sessionmaker

from memory.models import Base, User, ProfileFact, Conversation, ScheduledMessage, TimelineEvent, DiaryEntry
from config.settings import settings

TZ = pytz.timezone(settings.TIMEZONE)


def fmt(dt_obj):
    if dt_obj is None:
        return "N/A"
    utc_time = dt_obj.replace(tzinfo=pytz.utc)
    local_time = utc_time.astimezone(TZ)
    return local_time.strftime("%Y-%m-%d %H:%M")


def fmt_time(dt_obj):
    if dt_obj is None:
        return ""
    utc_time = dt_obj.replace(tzinfo=pytz.utc)
    local_time = utc_time.astimezone(TZ)
    return local_time.strftime("%H:%M")


@st.cache_resource
def get_engine():
    db_url = settings.DATABASE_URL
    return create_engine(db_url, pool_pre_ping=True)


def get_session():
    engine = get_engine()
    return sessionmaker(bind=engine)()


# ---- Data loading ----

@st.cache_data(ttl=30)
def load_users():
    session = get_session()
    try:
        users = session.execute(select(User).order_by(User.id)).scalars().all()
        result = []
        for u in users:
            msg_count = session.execute(
                select(func.count()).select_from(Conversation).where(Conversation.user_id == u.id)
            ).scalar()
            result.append({
                "id": u.id,
                "name": u.name or f"User {u.id}",
                "username": u.username,
                "telegram_id": u.telegram_id,
                "created_at": u.created_at,
                "last_interaction": u.last_interaction,
                "msg_count": msg_count,
            })
        return result
    finally:
        session.close()


@st.cache_data(ttl=30)
def load_profile(user_id: int):
    session = get_session()
    try:
        facts = session.execute(
            select(ProfileFact)
            .where(ProfileFact.user_id == user_id)
            .order_by(ProfileFact.category, ProfileFact.observed_at.desc())
        ).scalars().all()

        grouped = defaultdict(list)
        for f in facts:
            grouped[f.category].append({
                "key": f.key,
                "value": f.value,
                "observed_at": f.observed_at,
                "updated_at": f.updated_at,
                "confidence": f.confidence,
            })
        return dict(grouped)
    finally:
        session.close()


@st.cache_data(ttl=30)
def load_conversations(user_id: int, limit: int = 50):
    session = get_session()
    try:
        total = session.execute(
            select(func.count()).select_from(Conversation).where(Conversation.user_id == user_id)
        ).scalar()

        convs = session.execute(
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(desc(Conversation.id))
            .limit(limit)
        ).scalars().all()

        messages = []
        for c in reversed(convs):
            messages.append({
                "role": c.role,
                "message": c.message,
                "thinking": c.thinking,
                "timestamp": c.timestamp,
            })
        return messages, total
    finally:
        session.close()


@st.cache_data(ttl=30)
def load_scheduled(user_id: int):
    session = get_session()
    try:
        scheduled = session.execute(
            select(ScheduledMessage)
            .where(ScheduledMessage.user_id == user_id, ScheduledMessage.executed == False)
            .order_by(ScheduledMessage.scheduled_time)
        ).scalars().all()

        events = session.execute(
            select(TimelineEvent)
            .where(TimelineEvent.user_id == user_id)
            .order_by(TimelineEvent.datetime.desc())
            .limit(20)
        ).scalars().all()

        return (
            [{"time": s.scheduled_time, "type": s.message_type, "context": s.context} for s in scheduled],
            [{"time": e.datetime, "type": e.event_type, "title": e.title, "desc": e.description, "reminded": e.reminded} for e in events],
        )
    finally:
        session.close()


@st.cache_data(ttl=30)
def load_diary_entries(user_id: int, limit: int = 10):
    session = get_session()
    try:
        entries = session.execute(
            select(DiaryEntry)
            .where(DiaryEntry.user_id == user_id)
            .order_by(desc(DiaryEntry.timestamp))
            .limit(limit)
        ).scalars().all()
        
        return [{
            "id": e.id,
            "type": e.entry_type,
            "title": e.title,
            "content": e.content,
            "importance": e.importance,
            "timestamp": e.timestamp,
            "exchange_start": getattr(e, 'exchange_start', None),
            "exchange_end": getattr(e, 'exchange_end', None),
            "image_url": e.image_url,
        } for e in entries]
    finally:
        session.close()


@st.cache_data(ttl=30)
def load_diary_stats(user_id: int):
    """Get counts of diary entries by type."""
    session = get_session()
    try:
        result = session.execute(
            select(DiaryEntry.entry_type, func.count(DiaryEntry.id))
            .where(DiaryEntry.user_id == user_id)
            .group_by(DiaryEntry.entry_type)
        ).all()
        
        return {entry_type: count for entry_type, count in result}
    finally:
        session.close()


@st.cache_data(ttl=30)
def load_user_settings(user_id: int):
    session = get_session()
    try:
        user = session.execute(
            select(User).where(User.id == user_id)
        ).scalar_one_or_none()
        
        if not user:
            return None
            
        return {
            "reach_out_enabled": user.reach_out_enabled,
            "reach_out_min_silence_hours": user.reach_out_min_silence_hours,
            "reach_out_max_silence_days": user.reach_out_max_silence_days,
            "last_reach_out_at": user.last_reach_out_at,
        }
    finally:
        session.close()


# ---- Page config ----

st.set_page_config(page_title="Companion Dashboard", page_icon="👁", layout="centered")

st.markdown("""
<style>
    .main .block-container {
        max-width: 800px;
        padding-top: 2rem;
    }
    .stMarkdown, .stWrite, .stText, .stCaption, p, li, span {
        font-size: 1.1rem !important;
    }
    .stChatMessage p {
        font-size: 1.15rem !important;
    }
    h1 { font-size: 2.2rem !important; }
    h2 { font-size: 1.7rem !important; }
    h3 { font-size: 1.4rem !important; }
</style>
""", unsafe_allow_html=True)

st.title("Companion Dashboard")

# ---- Sidebar: user selector ----

users = load_users()
if not users:
    st.warning("No users found in database.")
    st.stop()

user_options = {f"{u['name']} ({u['msg_count']} msgs)": u["id"] for u in users}
selected_label = st.sidebar.selectbox("Select User", list(user_options.keys()))
selected_user_id = user_options[selected_label]
selected_user = next(u for u in users if u["id"] == selected_user_id)

# User info in sidebar
st.sidebar.markdown("---")
st.sidebar.markdown(f"**ID:** {selected_user['id']}")
st.sidebar.markdown(f"**Telegram:** {selected_user['telegram_id']}")
if selected_user.get('username'):
    st.sidebar.markdown(f"**Username:** @{selected_user['username']}")
st.sidebar.markdown(f"**Created:** {fmt(selected_user['created_at'])}")
st.sidebar.markdown(f"**Last Active:** {fmt(selected_user['last_interaction'])}")

# Load additional user details
session = get_session()
try:
    user_full = session.execute(
        select(User).where(User.id == selected_user_id)
    ).scalar_one_or_none()
    if user_full:
        st.sidebar.markdown("---")
        st.sidebar.markdown("**User Details**")
        tz = getattr(user_full, 'timezone', None)
        loc = getattr(user_full, 'location_name', None)
        onb = getattr(user_full, 'onboarding_state', None)
        if tz and tz != "America/Toronto":
            st.sidebar.markdown(f"🌍 Timezone: {tz}")
        if loc:
            st.sidebar.markdown(f"📍 Location: {loc}")
        if onb:
            st.sidebar.markdown(f"⚙️ Onboarding: {onb}")
finally:
    session.close()

if st.sidebar.button("Refresh Data"):
    st.cache_data.clear()
    st.rerun()

# ---- Tabs ----

tab_overview, tab_conversations, tab_observations, tab_scheduled, tab_diary, tab_database, tab_settings = st.tabs(
    ["Overview", "Conversations", "Observations", "Scheduled", "Diary", "Database", "Settings"]
)

profile = load_profile(selected_user_id)

# ---- Tab: Overview ----

with tab_overview:
    st.header(f"{selected_user['name']}")

    # Condensed narratives
    if "condensed" in profile:
        st.subheader("Condensed Narratives")
        for item in profile["condensed"]:
            with st.expander(f"**{item['key']}**", expanded=True):
                st.write(item["value"])
                st.caption(f"Condensed: {fmt(item['updated_at'])}")
    else:
        st.info("No condensed narratives yet. Run `uv run python scripts/run_condensation.py` to generate.")

    # Static facts
    if "static" in profile:
        st.subheader("Static Facts")
        for item in profile["static"]:
            st.markdown(f"- {item['value']}")

    # Quick stats
    st.subheader("Stats")
    raw_categories = [c for c in profile.keys() if c not in ("condensed", "static", "system")]
    raw_count = sum(len(profile[c]) for c in raw_categories)
    col1, col2, col3 = st.columns(3)
    col1.metric("Messages", selected_user["msg_count"])
    col2.metric("Observations", raw_count)
    col3.metric("Categories", len(raw_categories))


# ---- Tab: Conversations ----

with tab_conversations:
    msg_limit = st.slider("Messages to load", 10, 500, 50, step=10)
    messages, total = load_conversations(selected_user_id, limit=msg_limit)
    st.caption(f"Showing {len(messages)} of {total} messages")

    for msg in messages:
        role = msg["role"]
        ts = fmt_time(msg["timestamp"])
        date = fmt(msg["timestamp"])

        with st.chat_message("user" if role == "user" else "assistant"):
            st.caption(date)
            st.write(msg["message"])
            if role == "assistant" and msg["thinking"]:
                with st.expander("thinking"):
                    st.text(msg["thinking"])


# ---- Tab: Observations ----

with tab_observations:
    raw_categories = [c for c in sorted(profile.keys()) if c not in ("condensed", "static", "system")]

    if not raw_categories:
        st.info("No observations yet.")
    else:
        # Category filter
        selected_cats = st.multiselect(
            "Filter by category",
            raw_categories,
            default=raw_categories,
        )

        for category in selected_cats:
            items = profile[category]
            with st.expander(f"**{category}** ({len(items)} observations)", expanded=False):
                for item in items:
                    st.markdown(f"**[{fmt(item['observed_at'])}]** {item['value']}")
                    st.divider()


# ---- Tab: Scheduled ----

with tab_scheduled:
    scheduled_msgs, events = load_scheduled(selected_user_id)

    st.subheader(f"Pending Messages ({len(scheduled_msgs)})")
    if scheduled_msgs:
        for msg in scheduled_msgs:
            st.markdown(f"**[{fmt(msg['time'])}]** `{msg['type']}` — {msg['context'] or 'no context'}")
    else:
        st.caption("No pending messages.")

    st.subheader(f"Timeline Events ({len(events)})")
    if events:
        for event in events:
            reminded = " ✓" if event["reminded"] else ""
            st.markdown(f"**[{fmt(event['time'])}]** `{event['type']}` — {event['title']}{reminded}")
            if event["desc"]:
                st.caption(event["desc"])
    else:
        st.caption("No timeline events.")


# ---- Tab: Diary ----

with tab_diary:
    st.subheader("Diary Entries")
    
    # Get stats
    diary_stats = load_diary_stats(selected_user_id)
    
    if not diary_stats:
        st.info("No diary entries yet.")
    else:
        # Show stats
        st.markdown("**Entry Types:**")
        cols = st.columns(len(diary_stats))
        for idx, (entry_type, count) in enumerate(sorted(diary_stats.items())):
            with cols[idx]:
                # Emoji mapping
                emoji_map = {
                    "compact_summary": "📝",
                    "conversation_memory": "🧠",
                    "achievement": "🏆",
                    "milestone": "⭐",
                    "visual_memory": "📸",
                    "significant_event": "🎯"
                }
                emoji = emoji_map.get(entry_type, "📄")
                st.metric(f"{emoji} {entry_type}", count)
        
        st.markdown("---")
        
        # Entry type filter
        entry_types = ["All"] + sorted(diary_stats.keys())
        selected_type = st.selectbox("Filter by type", entry_types)
        
        entry_limit = st.slider("Entries to load", 5, 100, 20, step=5)
        diary_entries = load_diary_entries(selected_user_id, limit=entry_limit)
        
        # Filter by type if selected
        if selected_type != "All":
            diary_entries = [e for e in diary_entries if e["type"] == selected_type]
        
        if not diary_entries:
            st.info(f"No {selected_type} entries found.")
        else:
            # Group by type for better organization
            entries_by_type = {}
            for entry in diary_entries:
                entry_type = entry["type"]
                if entry_type not in entries_by_type:
                    entries_by_type[entry_type] = []
                entries_by_type[entry_type].append(entry)
            
            # Display entries grouped by type
            for entry_type, entries in sorted(entries_by_type.items()):
                emoji_map = {
                    "compact_summary": "📝",
                    "conversation_memory": "🧠",
                    "achievement": "🏆",
                    "milestone": "⭐",
                    "visual_memory": "📸",
                    "significant_event": "🎯"
                }
                emoji = emoji_map.get(entry_type, "📄")
                
                st.markdown(f"### {emoji} {entry_type.replace('_', ' ').title()} ({len(entries)})")
                
                for entry in entries:
                    timestamp = fmt(entry["timestamp"])
                    importance = entry.get("importance", "N/A")
                    
                    # Format exchange times if available
                    exchange_info = ""
                    if entry["exchange_start"] and entry["exchange_end"]:
                        start = fmt(entry["exchange_start"])
                        end = fmt(entry["exchange_end"])
                        exchange_info = f"\n📅 Exchange: {start} → {end}"
                    
                    # Create title with metadata
                    title = f"**{entry['title']}** — {timestamp}"
                    if importance != "N/A":
                        title += f" (Importance: {importance}/10)"
                    
                    with st.expander(title, expanded=False):
                        st.write(entry["content"])
                        if exchange_info:
                            st.caption(exchange_info)
                        if entry.get("image_url"):
                            st.caption(f"🖼️ Image: {entry['image_url']}")
                
                st.markdown("---")


# ---- Tab: Database ----

with tab_database:
    st.subheader("Database Overview")
    st.caption(f"Complete view of all data for {selected_user['name']}")
    
    session = get_session()
    try:
        # Get counts for all tables
        profile_count = session.execute(
            select(func.count()).select_from(ProfileFact).where(ProfileFact.user_id == selected_user_id)
        ).scalar()
        
        conv_count = session.execute(
            select(func.count()).select_from(Conversation).where(Conversation.user_id == selected_user_id)
        ).scalar()
        
        timeline_count = session.execute(
            select(func.count()).select_from(TimelineEvent).where(TimelineEvent.user_id == selected_user_id)
        ).scalar()
        
        diary_count = session.execute(
            select(func.count()).select_from(DiaryEntry).where(DiaryEntry.user_id == selected_user_id)
        ).scalar()
        
        scheduled_count = session.execute(
            select(func.count()).select_from(ScheduledMessage)
            .where(ScheduledMessage.user_id == selected_user_id, ScheduledMessage.executed == False)
        ).scalar()
        
        # Display counts
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("👤 Profile Facts", profile_count)
            st.metric("💬 Conversations", conv_count)
        with col2:
            st.metric("📅 Timeline Events", timeline_count)
            st.metric("📔 Diary Entries", diary_count)
        with col3:
            st.metric("⏰ Scheduled Messages", scheduled_count)
        
        st.markdown("---")
        
        # Profile Facts breakdown by category
        st.markdown("### Profile Facts by Category")
        profile_by_cat = session.execute(
            select(ProfileFact.category, func.count(ProfileFact.id))
            .where(ProfileFact.user_id == selected_user_id)
            .group_by(ProfileFact.category)
            .order_by(func.count(ProfileFact.id).desc())
        ).all()
        
        if profile_by_cat:
            for category, count in profile_by_cat:
                st.markdown(f"- **{category}**: {count} facts")
        else:
            st.caption("No profile facts yet")
        
        st.markdown("---")
        
        # Diary Entries breakdown by type
        st.markdown("### Diary Entries by Type")
        diary_by_type = session.execute(
            select(DiaryEntry.entry_type, func.count(DiaryEntry.id))
            .where(DiaryEntry.user_id == selected_user_id)
            .group_by(DiaryEntry.entry_type)
            .order_by(func.count(DiaryEntry.id).desc())
        ).all()
        
        if diary_by_type:
            for entry_type, count in diary_by_type:
                emoji_map = {
                    "compact_summary": "📝",
                    "conversation_memory": "🧠",
                    "achievement": "🏆",
                    "milestone": "⭐",
                    "visual_memory": "📸",
                    "significant_event": "🎯"
                }
                emoji = emoji_map.get(entry_type, "📄")
                st.markdown(f"- {emoji} **{entry_type}**: {count} entries")
        else:
            st.caption("No diary entries yet")
        
        st.markdown("---")
        
        # Conversation stats
        st.markdown("### Conversation Statistics")
        user_msg_count = session.execute(
            select(func.count()).select_from(Conversation)
            .where(Conversation.user_id == selected_user_id, Conversation.role == "user")
        ).scalar()
        
        assistant_msg_count = session.execute(
            select(func.count()).select_from(Conversation)
            .where(Conversation.user_id == selected_user_id, Conversation.role == "assistant")
        ).scalar()
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("User Messages", user_msg_count)
        with col2:
            st.metric("Assistant Messages", assistant_msg_count)
        
        # First and last message times
        first_msg = session.execute(
            select(Conversation.timestamp)
            .where(Conversation.user_id == selected_user_id)
            .order_by(Conversation.timestamp)
            .limit(1)
        ).scalar()
        
        last_msg = session.execute(
            select(Conversation.timestamp)
            .where(Conversation.user_id == selected_user_id)
            .order_by(Conversation.timestamp.desc())
            .limit(1)
        ).scalar()
        
        if first_msg and last_msg:
            st.markdown(f"**First message:** {fmt(first_msg)}")
            st.markdown(f"**Last message:** {fmt(last_msg)}")
            
            # Calculate conversation span
            span = last_msg - first_msg
            days = span.days
            st.markdown(f"**Conversation span:** {days} days")
        
    finally:
        session.close()


# ---- Tab: Settings ----

with tab_settings:
    st.subheader("User Settings")
    
    user_settings = load_user_settings(selected_user_id)
    
    if not user_settings:
        st.error("Could not load user settings.")
    else:
        st.markdown("### Reach-Out Configuration")
        
        col1, col2 = st.columns(2)
        
        with col1:
            enabled_status = "✅ Enabled" if user_settings["reach_out_enabled"] else "❌ Disabled"
            st.metric("Status", enabled_status)
            st.metric("Min Silence", f"{user_settings['reach_out_min_silence_hours']} hours")
        
        with col2:
            st.metric("Max Silence", f"{user_settings['reach_out_max_silence_days']} days")
            last_reach_out = fmt(user_settings["last_reach_out_at"]) if user_settings["last_reach_out_at"] else "Never"
            st.metric("Last Reach-Out", last_reach_out)
        
        st.markdown("---")
        st.caption("Users can configure these settings via Telegram commands: /reachout_settings, /reachout_enable, /reachout_disable, /reachout_min, /reachout_max")
