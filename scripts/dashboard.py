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

import pandas as pd
import pytz
import streamlit as st
import sqlalchemy
from sqlalchemy import create_engine, select, desc, func
from sqlalchemy.orm import Session, sessionmaker

import importlib
import memory.models
import config.settings
importlib.reload(memory.models)
importlib.reload(config.settings)

from memory.models import Base, User, Conversation, DiaryEntry, TokenUsage
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


@st.cache_data(ttl=30)
def load_token_usage(user_id: int):
    session = get_session()
    try:
        # Get usage grouped by date and model
        usage = session.execute(
            select(
                func.cast(TokenUsage.timestamp, sqlalchemy.Date).label("date"),
                TokenUsage.model,
                func.sum(TokenUsage.input_tokens).label("input"),
                func.sum(TokenUsage.output_tokens).label("output"),
                func.sum(TokenUsage.total_tokens).label("total"),
                func.sum(getattr(TokenUsage, "cache_read_tokens", 0)).label("cache_read"),
                func.sum(getattr(TokenUsage, "cache_creation_tokens", 0)).label("cache_creation")
            )
            .where(TokenUsage.user_id == user_id)
            .group_by(func.cast(TokenUsage.timestamp, sqlalchemy.Date), TokenUsage.model)
            .order_by(desc("date"))
        ).all()

        # Get usage breakdown by call_type
        by_type = session.execute(
            select(TokenUsage.call_type, func.sum(TokenUsage.total_tokens))
            .where(TokenUsage.user_id == user_id)
            .group_by(TokenUsage.call_type)
        ).all()

        return usage, {t: count for t, count in by_type}
    finally:
        session.close()


# ---- Page config ----

st.set_page_config(page_title="Companion Dashboard", page_icon="👁", layout="centered")

# ---- Session State Initialization ----

# Initialize session state for persistent widget values
if "msg_limit" not in st.session_state:
    st.session_state.msg_limit = 50

if "entry_limit" not in st.session_state:
    st.session_state.entry_limit = 20

if "selected_diary_type" not in st.session_state:
    st.session_state.selected_diary_type = "All"

if "selected_observation_cats" not in st.session_state:
    st.session_state.selected_observation_cats = None

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

if st.sidebar.button("Refresh Data", key="refresh_button"):
    st.cache_data.clear()
    st.rerun()

# ---- Tabs ----

tab_overview, tab_conversations, tab_diary, tab_usage, tab_database, tab_settings = st.tabs(
    ["Overview", "Conversations", "Diary", "Usage", "Database", "Settings"]
)

# ---- Tab: Overview ----

with tab_overview:
    @st.fragment
    def overview_fragment(user_id):
        user = next(u for u in users if u["id"] == user_id)
        
        st.header(f"{user['name']}")

        # Quick stats
        st.subheader("Stats")
        col1, col2 = st.columns(2)
        col1.metric("Messages", user["msg_count"])
        
        # Load memory count
        session = get_session()
        try:
            memory_count = session.execute(
                select(func.count()).select_from(DiaryEntry).where(DiaryEntry.user_id == user_id)
            ).scalar()
            col2.metric("Memories & Summaries", memory_count)
        finally:
            session.close()

    overview_fragment(selected_user_id)


# ---- Tab: Conversations ----

with tab_conversations:
    @st.fragment
    def conversations_fragment(user_id):
        msg_limit = st.slider(
            "Messages to load",
            10, 500,
            value=st.session_state.msg_limit,
            step=10,
            key="msg_limit"
        )
        messages, total = load_conversations(user_id, limit=msg_limit)
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

    conversations_fragment(selected_user_id)


# Tab: Observations and Scheduled removed during cleanup


# ---- Tab: Diary ----

with tab_diary:
    @st.fragment
    def diary_fragment(user_id):
        st.subheader("Diary Entries")
        
        # Get stats
        diary_stats = load_diary_stats(user_id)
        
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
            selected_type = st.selectbox(
                "Filter by type",
                entry_types,
                index=entry_types.index(st.session_state.selected_diary_type) if st.session_state.selected_diary_type in entry_types else 0,
                key="diary_type_filter"
            )
            
            entry_limit = st.slider(
                "Entries to load",
                5, 100,
                value=st.session_state.entry_limit,
                step=5,
                key="entry_limit"
            )
            diary_entries = load_diary_entries(user_id, limit=entry_limit)
            
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

    diary_fragment(selected_user_id)


# ---- Tab: Database ----

with tab_database:
    @st.fragment
    def database_fragment(user_id):
        user = next(u for u in users if u["id"] == user_id)
        st.subheader("Database Overview")
        st.caption(f"Complete view of all data for {user['name']}")
        
        session = get_session()
        try:
            conv_count = session.execute(
                select(func.count()).select_from(Conversation).where(Conversation.user_id == user_id)
            ).scalar()
            
            diary_count = session.execute(
                select(func.count()).select_from(DiaryEntry).where(DiaryEntry.user_id == user_id)
            ).scalar()
            
            # Display counts
            col1, col2 = st.columns(2)
            with col1:
                st.metric("💬 Conversations", conv_count)
            with col2:
                st.metric("📔 Diary Entries", diary_count)
            
            st.markdown("---")
            
            # Diary Entries breakdown by type
            st.markdown("### Diary Entries by Type")
            diary_by_type = session.execute(
                select(DiaryEntry.entry_type, func.count(DiaryEntry.id))
                .where(DiaryEntry.user_id == user_id)
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
                .where(Conversation.user_id == user_id, Conversation.role == "user")
            ).scalar()
            
            assistant_msg_count = session.execute(
                select(func.count()).select_from(Conversation)
                .where(Conversation.user_id == user_id, Conversation.role == "assistant")
            ).scalar()
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("User Messages", user_msg_count)
            with col2:
                st.metric("Assistant Messages", assistant_msg_count)
            
            # First and last message times
            first_msg = session.execute(
                select(Conversation.timestamp)
                .where(Conversation.user_id == user_id)
                .order_by(Conversation.timestamp)
                .limit(1)
            ).scalar()
            
            last_msg = session.execute(
                select(Conversation.timestamp)
                .where(Conversation.user_id == user_id)
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

    database_fragment(selected_user_id)


# ---- Tab: Usage ----

with tab_usage:
    @st.fragment
    def usage_fragment(user_id):
        st.subheader("Token Usage & Costs")
        
        usage_data, type_breakdown = load_token_usage(user_id)
        
        if not usage_data:
            st.info("No token usage recorded yet.")
            return

        # 1. Top metrics (Latest Day)
        latest_date = usage_data[0].date
        latest_day_totals = [u for u in usage_data if u.date == latest_date]
        day_input = sum(u.input for u in latest_day_totals)
        day_output = sum(u.output for u in latest_day_totals)
        day_total = sum(u.total for u in latest_day_totals)

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Today's Tokens", f"{day_total:,}")
        
        from config.settings import settings
        budget = settings.USER_DAILY_TOKEN_BUDGET
        if budget > 0:
            remaining = max(0, budget - day_total)
            col2.metric("Daily Budget", f"{budget:,}")
            col3.metric("Remaining", f"{remaining:,}", delta=f"-{day_total:,}" if day_total > 0 else None)
            
            # Progress bar
            progress = min(1.0, day_total / budget)
            st.progress(progress, text=f"Daily Budget Consumption: {progress:.1%}")
            if progress >= 1.0:
                st.error("⚠️ User has exceeded their daily token budget.")
            elif progress >= 0.8:
                st.warning("⚠️ User is approaching their daily token budget.")
        else:
            col2.metric("Daily Budget", "Unlimited")
            
        col4.metric("Input / Output", f"{day_input:,} / {day_output:,}")

        # 2. Weekly Trend
        st.subheader("Daily Usage")
        # Format for chart
        chart_data = defaultdict(int)
        for u in usage_data:
            chart_data[u.date.strftime("%Y-%m-%d")] += u.total
        
        # Sort and plot
        sorted_dates = sorted(chart_data.keys())
        st.line_chart([chart_data[d] for d in sorted_dates])

        # 3. Model & Cost Breakdown
        st.subheader("Model Breakdown & Est. Cost")
        # Pricing per 1M tokens (ballpark estimates)
        PRICING = {
            "gpt-4o": {"in": 2.50, "out": 10.00},
            "gpt-4o-mini": {"in": 0.15, "out": 0.60},
            "claude-3-5-sonnet-20240620": {"in": 3.00, "out": 15.00},
            "claude-3-5-sonnet-20241022": {"in": 3.00, "out": 15.00},
            "gemini-1.5-flash": {"in": 0.075, "out": 0.30},
            "gemini-1.5-pro": {"in": 1.25, "out": 5.00},
        }

        cost_rows = []
        total_est_cost = 0
        total_saved = 0
        
        # Anthropic Prompt Caching Pricing (per 1M tokens)
        # Write (Creation): $3.75 (Sonnet) / $0.30 (Haiku) -> ~1.25x base price?
        # Read (Hit): $0.30 (Sonnet) / $0.03 (Haiku) -> ~0.1x base price
        # For simplicity, we compare (Cache Read * Input Price) vs (Cache Read * 0.1 * Input Price)
        
        for u in usage_data:
            # Try to match pricing
            m_name = u.model.split("/")[-1]
            price = PRICING.get(m_name, {"in": 0, "out": 0})
            
            # Base cost of standard tokens
            base_input = u.input - getattr(u, "cache_read", 0) - getattr(u, "cache_creation", 0)
            cost_base = (base_input / 1_000_000 * price["in"]) + (u.output / 1_000_000 * price["out"])
            
            # Cache creation (usually 1.25x price)
            cost_creation = (getattr(u, "cache_creation", 0) / 1_000_000 * price["in"] * 1.25)
            
            # Cache read (usually 0.1x price)
            cost_read = (getattr(u, "cache_read", 0) / 1_000_000 * price["in"] * 0.1)
            
            # Savings: What it WOULD have cost minus what it DID cost
            would_have_cost_read = (getattr(u, "cache_read", 0) / 1_000_000 * price["in"])
            saved = would_have_cost_read - cost_read
            
            day_cost = cost_base + cost_creation + cost_read
            total_est_cost += day_cost
            total_saved += saved
            
            cost_rows.append({
                "Date": u.date,
                "Model": u.model,
                "Total Tokens": u.total,
                "Cache Hits": getattr(u, "cache_read", 0),
                "Est. Cost ($)": f"${day_cost:.4f}"
            })
        
        st.table(cost_rows)
        
        col1, col2 = st.columns(2)
        col1.metric("Total Estimated Cost (Lifetime)", f"${total_est_cost:.2f}")
        col2.metric("Total ⚡ Savings (Prompt Caching)", f"${total_saved:.2f}", delta=f"{total_saved:.4f}", delta_color="normal")
        
        if total_saved > 0:
            st.success(f"🔥 Prompt caching has reduced your input costs by approximately {((total_saved / (total_est_cost + total_saved)) * 100):.1f}%!")

        # 4. Call Type Distribution
        st.subheader("Call Type Distribution")
        if type_breakdown:
            df_type = pd.DataFrame([
                {"Call Type": k, "Tokens": v} for k, v in type_breakdown.items()
            ])
            st.bar_chart(df_type.set_index("Call Type"))

    usage_fragment(selected_user_id)


# ---- Tab: Settings ----

with tab_settings:
    @st.fragment
    def settings_fragment(user_id):
        st.subheader("User Settings")
        
        user_settings = load_user_settings(user_id)
        
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

    settings_fragment(selected_user_id)

