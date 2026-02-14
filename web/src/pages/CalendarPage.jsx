import React, { useState, useEffect, useMemo } from 'react';
import { Block, Preloader, Fab, Sheet, ListInput, List, Button, Toggle } from 'konsta/react';
import axios from 'axios';
import WebApp from '@twa-dev/sdk';

// ── Helpers ────────────────────────────────────────────────

function getUserId() {
    const urlParams = new URLSearchParams(window.location.search);
    return urlParams.get('user_id') || WebApp.initDataUnsafe?.user?.id;
}

function getDaysInMonth(year, month) {
    return new Date(year, month + 1, 0).getDate();
}

function getFirstDayOfWeek(year, month) {
    return new Date(year, month, 1).getDay(); // 0=Sun
}

function formatTime(dateStr) {
    const d = new Date(dateStr);
    return d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
}

function formatDate(dateStr) {
    const d = new Date(dateStr);
    return d.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' });
}

const MONTH_NAMES = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December'
];

const DAY_LABELS = ['S', 'M', 'T', 'W', 'T', 'F', 'S'];

// ── CalendarPage ───────────────────────────────────────────

export default function CalendarPage() {
    const today = new Date();
    const [year, setYear] = useState(today.getFullYear());
    const [month, setMonth] = useState(today.getMonth());
    const [selectedDay, setSelectedDay] = useState(today.getDate());
    const [events, setEvents] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    // Add event sheet
    const [sheetOpen, setSheetOpen] = useState(false);
    const [newTitle, setNewTitle] = useState('');
    const [newDate, setNewDate] = useState('');
    const [newTime, setNewTime] = useState('');
    const [newAllDay, setNewAllDay] = useState(false);
    const [submitting, setSubmitting] = useState(false);

    // ── Fetch events for current month ──

    useEffect(() => {
        fetchEvents();
    }, [year, month]);

    const fetchEvents = async () => {
        const userId = getUserId();
        if (!userId) {
            setError("User ID not found.");
            setLoading(false);
            return;
        }

        try {
            setLoading(true);
            const from = new Date(year, month, 1).toISOString();
            const to = new Date(year, month + 1, 0, 23, 59, 59).toISOString();
            const res = await axios.get(`/api/calendar/${userId}`, {
                params: { from, to }
            });
            setEvents(res.data);
            setError(null);
        } catch (err) {
            console.error(err);
            setError("Failed to load events.");
        } finally {
            setLoading(false);
        }
    };

    // ── Derived data ──

    const eventsByDay = useMemo(() => {
        const map = {};
        events.forEach(ev => {
            const d = new Date(ev.event_start).getDate();
            if (!map[d]) map[d] = [];
            map[d].push(ev);
        });
        return map;
    }, [events]);

    const selectedEvents = eventsByDay[selectedDay] || [];

    // ── Month navigation ──

    const prevMonth = () => {
        if (month === 0) { setMonth(11); setYear(y => y - 1); }
        else setMonth(m => m - 1);
        setSelectedDay(1);
    };

    const nextMonth = () => {
        if (month === 11) { setMonth(0); setYear(y => y + 1); }
        else setMonth(m => m + 1);
        setSelectedDay(1);
    };

    // ── Create event ──

    const handleCreate = async () => {
        const userId = getUserId();
        if (!userId || !newTitle.trim()) return;

        setSubmitting(true);
        try {
            const dateStr = newDate || `${year}-${String(month + 1).padStart(2, '0')}-${String(selectedDay).padStart(2, '0')}`;
            const timeStr = newTime || '09:00';
            const event_start = new Date(`${dateStr}T${timeStr}`).toISOString();

            await axios.post(`/api/calendar/${userId}`, {
                title: newTitle.trim(),
                event_start,
                is_all_day: newAllDay,
            });

            setNewTitle('');
            setNewDate('');
            setNewTime('');
            setNewAllDay(false);
            setSheetOpen(false);
            await fetchEvents();
        } catch (err) {
            console.error('Create failed:', err);
        } finally {
            setSubmitting(false);
        }
    };

    // ── Delete event ──

    const handleDelete = async (eventId) => {
        const userId = getUserId();
        if (!userId) return;

        try {
            await axios.delete(`/api/calendar/${userId}/${eventId}`);
            await fetchEvents();
        } catch (err) {
            console.error('Delete failed:', err);
        }
    };

    // ── Render month grid ──

    const daysInMonth = getDaysInMonth(year, month);
    const firstDay = getFirstDayOfWeek(year, month);
    const isToday = (day) => day === today.getDate() && month === today.getMonth() && year === today.getFullYear();

    const renderGrid = () => {
        const cells = [];
        // Empty cells before first day
        for (let i = 0; i < firstDay; i++) {
            cells.push(<div key={`empty-${i}`} className="h-10" />);
        }
        // Day cells
        for (let day = 1; day <= daysInMonth; day++) {
            const hasEvents = !!eventsByDay[day];
            const selected = day === selectedDay;
            cells.push(
                <button
                    key={day}
                    onClick={() => setSelectedDay(day)}
                    className={`h-10 w-full rounded-lg flex flex-col items-center justify-center text-sm font-medium transition-all relative
                        ${selected ? 'bg-blue-500 text-white' : 'text-gray-300 hover:bg-gray-800'}
                        ${isToday(day) && !selected ? 'ring-1 ring-blue-400' : ''}
                    `}
                >
                    {day}
                    {hasEvents && (
                        <div className={`absolute bottom-1 w-1 h-1 rounded-full ${selected ? 'bg-white' : 'bg-blue-400'}`} />
                    )}
                </button>
            );
        }
        return cells;
    };

    return (
        <div className="pb-24">
            {/* Month header */}
            <div className="flex items-center justify-between px-4 py-3">
                <button onClick={prevMonth} className="text-gray-400 hover:text-white p-2 text-lg">‹</button>
                <h2 className="text-lg font-semibold text-white">{MONTH_NAMES[month]} {year}</h2>
                <button onClick={nextMonth} className="text-gray-400 hover:text-white p-2 text-lg">›</button>
            </div>

            {/* Day labels */}
            <div className="grid grid-cols-7 px-4 mb-1">
                {DAY_LABELS.map((d, i) => (
                    <div key={i} className="text-center text-xs font-medium text-gray-500">{d}</div>
                ))}
            </div>

            {/* Month grid */}
            <div className="grid grid-cols-7 gap-1 px-4 mb-4">
                {renderGrid()}
            </div>

            {/* Selected day events */}
            <div className="px-4">
                <div className="text-sm text-gray-500 mb-2">
                    {MONTH_NAMES[month]} {selectedDay}, {year}
                </div>

                {loading && (
                    <Block className="text-center">
                        <Preloader size="w-6 h-6" />
                    </Block>
                )}

                {!loading && selectedEvents.length === 0 && (
                    <div className="text-center text-gray-600 py-8 text-sm">
                        No events this day
                    </div>
                )}

                {!loading && selectedEvents.map((ev) => (
                    <div
                        key={ev.id}
                        className="bg-space-dark border border-gray-800 rounded-xl p-4 mb-3 relative group"
                    >
                        <div className="flex justify-between items-start">
                            <div className="flex-1">
                                <h3 className="text-white font-medium">{ev.title}</h3>
                                {ev.description && (
                                    <p className="text-gray-400 text-sm mt-1">{ev.description}</p>
                                )}
                                <div className="text-xs text-gray-500 mt-2 font-mono">
                                    {ev.is_all_day ? 'All day' : formatTime(ev.event_start)}
                                    {ev.event_end && !ev.is_all_day && ` → ${formatTime(ev.event_end)}`}
                                </div>
                            </div>
                            <button
                                onClick={() => handleDelete(ev.id)}
                                className="text-gray-600 hover:text-red-400 text-sm ml-3 p-1 transition-colors"
                                title="Delete"
                            >
                                ✕
                            </button>
                        </div>
                        <div className="absolute top-0 left-0 w-1 h-full bg-blue-500 rounded-l-xl" />
                    </div>
                ))}
            </div>

            {/* FAB — Add Event */}
            <Fab
                className="fixed right-4 bottom-20 z-20"
                onClick={() => {
                    setNewDate(`${year}-${String(month + 1).padStart(2, '0')}-${String(selectedDay).padStart(2, '0')}`);
                    setSheetOpen(true);
                }}
                icon={<span className="text-xl">+</span>}
                text=""
            />

            {/* Add Event Sheet */}
            <Sheet
                className="pb-safe"
                opened={sheetOpen}
                onBackdropClick={() => setSheetOpen(false)}
            >
                <div className="bg-space-dark p-6 rounded-t-2xl">
                    <h3 className="text-white font-semibold text-lg mb-4">New Event</h3>
                    <List strongIos insetIos className="mb-4">
                        <ListInput
                            type="text"
                            placeholder="Event title"
                            value={newTitle}
                            onChange={(e) => setNewTitle(e.target.value)}
                        />
                        <ListInput
                            type="date"
                            label="Date"
                            value={newDate}
                            onChange={(e) => setNewDate(e.target.value)}
                        />
                        <ListInput
                            type="time"
                            label="Time"
                            value={newTime}
                            onChange={(e) => setNewTime(e.target.value)}
                            disabled={newAllDay}
                        />
                    </List>
                    <div className="flex items-center justify-between px-4 mb-6">
                        <span className="text-gray-300 text-sm">All day</span>
                        <Toggle
                            checked={newAllDay}
                            onChange={() => setNewAllDay(!newAllDay)}
                        />
                    </div>
                    <Button
                        large
                        onClick={handleCreate}
                        disabled={!newTitle.trim() || submitting}
                        className="mb-2"
                    >
                        {submitting ? 'Creating...' : 'Add Event'}
                    </Button>
                    <Button
                        large
                        outline
                        onClick={() => setSheetOpen(false)}
                    >
                        Cancel
                    </Button>
                </div>
            </Sheet>
        </div>
    );
}
