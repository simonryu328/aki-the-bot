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

from memory.models import Base, User, ProfileFact, Conversation, ScheduledMessage, TimelineEvent
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
st.sidebar.markdown(f"**Created:** {fmt(selected_user['created_at'])}")
st.sidebar.markdown(f"**Last Active:** {fmt(selected_user['last_interaction'])}")

if st.sidebar.button("Refresh Data"):
    st.cache_data.clear()
    st.rerun()

# ---- Tabs ----

tab_overview, tab_conversations, tab_observations, tab_scheduled = st.tabs(
    ["Overview", "Conversations", "Observations", "Scheduled"]
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
