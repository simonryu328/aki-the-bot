/* ═══════════════════════════════════════════════════════
   Aki — Telegram Mini App Logic
   ═══════════════════════════════════════════════════════ */

(function () {
    'use strict';

    // ── Telegram SDK Init ──
    const tg = window.Telegram?.WebApp;
    if (tg) {
        tg.ready();
        tg.expand();
        tg.disableVerticalSwipes();

        // Ensure header and background colors match the theme
        tg.setHeaderColor(tg.themeParams.header_bg_color || '#ffffff');
        tg.setBackgroundColor(tg.themeParams.bg_color || '#ffffff');
    }

    // ── State ──
    let currentPanel = 1; // Start on Today
    const totalPanels = 3;
    let allEntries = [];   // Full dataset for search

    // ── DOM References ──
    const container = document.getElementById('panelsContainer');
    const navTabs = document.querySelectorAll('.nav-tab');
    const dots = document.querySelectorAll('.dot');
    const todayDate = document.getElementById('todayDate');
    const dailyQuoteText = document.getElementById('dailyQuoteText');
    const dailyCard = document.getElementById('dailyCard');
    const journalList = document.getElementById('journalList');
    const searchInput = document.getElementById('searchInput');
    const searchBar = document.getElementById('searchBar');
    const loadingState = document.getElementById('loadingState');
    const errorState = document.getElementById('errorState');
    const errorText = document.getElementById('errorText');
    const emptyState = document.getElementById('emptyState');

    // ── Navigation ──────────────────────────────────────

    function goToPanel(index) {
        if (index < 0 || index >= totalPanels) return;
        currentPanel = index;
        const offset = -(index * 33.3333);
        container.style.transform = `translateX(${offset}%)`;

        // Update tabs
        navTabs.forEach((tab, i) => {
            tab.classList.toggle('active', i === index);
        });

        // Update dots
        dots.forEach((dot, i) => {
            dot.classList.toggle('active', i === index);
        });

        // Telegram back button — show on non-home panels
        if (tg) {
            if (index !== 1) {
                tg.BackButton.show();
            } else {
                tg.BackButton.hide();
            }
        }
    }

    // Tab clicks
    navTabs.forEach(tab => {
        tab.addEventListener('click', () => {
            goToPanel(parseInt(tab.dataset.panel));
        });
    });

    // Dot clicks
    dots.forEach(dot => {
        dot.addEventListener('click', () => {
            goToPanel(parseInt(dot.dataset.panel));
        });
    });

    // Back button handler
    if (tg) {
        tg.onEvent('backButtonClicked', () => {
            goToPanel(1); // Always go back to Today
        });
    }

    // ── Touch Swipe ─────────────────────────────────────

    let touchStartX = 0;
    let touchStartY = 0;
    let isSwiping = false;

    container.addEventListener('touchstart', (e) => {
        touchStartX = e.touches[0].clientX;
        touchStartY = e.touches[0].clientY;
        isSwiping = false;
    }, { passive: true });

    container.addEventListener('touchmove', (e) => {
        const dx = e.touches[0].clientX - touchStartX;
        const dy = e.touches[0].clientY - touchStartY;

        if (Math.abs(dx) > Math.abs(dy) && Math.abs(dx) > 10) {
            isSwiping = true;
        }
    }, { passive: true });

    container.addEventListener('touchend', (e) => {
        if (!isSwiping) return;
        const dx = e.changedTouches[0].clientX - touchStartX;

        if (Math.abs(dx) > 50) {
            if (dx < 0 && currentPanel < totalPanels - 1) {
                goToPanel(currentPanel + 1);
            } else if (dx > 0 && currentPanel > 0) {
                goToPanel(currentPanel - 1);
            }
        }
    }, { passive: true });

    // ── Keyboard Navigation ──
    document.addEventListener('keydown', (e) => {
        if (e.key === 'ArrowLeft') goToPanel(currentPanel - 1);
        if (e.key === 'ArrowRight') goToPanel(currentPanel + 1);
    });

    // ── Theme Change Listener ──
    if (tg) {
        tg.onEvent('themeChanged', () => {
            document.body.style.display = 'none';
            document.body.offsetHeight; // trigger reflow
            document.body.style.display = '';
        });
    }

    // ── Today's Date ──
    const now = new Date();
    const dateOptions = { weekday: 'long', month: 'long', day: 'numeric' };
    todayDate.textContent = now.toLocaleDateString('en-US', dateOptions);

    // ═══════════════════════════════════════════════════════
    // JOURNAL: Fetch & Render
    // ═══════════════════════════════════════════════════════

    function getUserId() {
        // Try URL param first (for dev), then Telegram SDK
        const urlParams = new URLSearchParams(window.location.search);
        return urlParams.get('user_id') || tg?.initDataUnsafe?.user?.id;
    }

    function formatDate(isoStr, includeTime = false) {
        if (!isoStr) return '';
        const d = new Date(isoStr);
        if (isNaN(d.getTime())) return '';

        const datePart = d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
        if (!includeTime) return datePart;

        const timePart = d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
        return `${datePart} ${timePart}`;
    }

    function formatRange(startIso, endIso, timestampIso) {
        if (!startIso || !endIso) return formatDate(timestampIso);

        const start = new Date(startIso);
        const end = new Date(endIso);

        if (isNaN(start.getTime()) || isNaN(end.getTime())) return formatDate(timestampIso);

        const isSameDay = start.getFullYear() === end.getFullYear() &&
            start.getMonth() === end.getMonth() &&
            start.getDate() === end.getDate();

        if (isSameDay) {
            const dateStr = start.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
            const startTime = start.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
            const endTime = end.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
            return `${dateStr} • ${startTime} – ${endTime}`;
        } else {
            const startStr = start.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
            const endStr = end.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
            return `${startStr} – ${endStr}`;
        }
    }

    function truncateText(text, maxLen) {
        if (!text || text.length <= maxLen) return text || '';
        return text.substring(0, maxLen).trim() + '…';
    }

    function renderEntries(entries) {
        journalList.innerHTML = '';

        if (entries.length === 0) {
            emptyState.classList.remove('hidden');
            searchBar.classList.add('hidden');
            return;
        }

        emptyState.classList.add('hidden');
        searchBar.classList.remove('hidden');

        entries.forEach((entry) => {
            const card = document.createElement('div');
            card.className = 'journal-card';

            // Build tags from entry type
            const tags = [];
            if (entry.entry_type) {
                const label = entry.entry_type.replace(/_/g, ' ');
                tags.push(label);
            }
            if (entry.importance && entry.importance >= 7) {
                tags.push('important');
            }

            card.innerHTML = `
        <div class="journal-card-date">${formatRange(entry.exchange_start, entry.exchange_end, entry.timestamp)}</div>
        <div class="journal-card-title">${escapeHtml(entry.title || 'Untitled')}</div>
        <div class="journal-card-preview">${escapeHtml(truncateText(entry.content, 300))}</div>
        ${tags.length ? `<div class="journal-card-tags">${tags.map(t => `<span class="journal-tag">${escapeHtml(t)}</span>`).join('')}</div>` : ''}
      `;

            // Toggle expand on click
            card.addEventListener('click', () => {
                const wasExpanded = card.classList.contains('expanded');
                card.classList.toggle('expanded');
                if (!wasExpanded) {
                    // Show full content when expanded
                    card.querySelector('.journal-card-preview').textContent = entry.content || '';
                } else {
                    card.querySelector('.journal-card-preview').textContent = truncateText(entry.content, 300);
                }
                if (tg) tg.HapticFeedback.impactOccurred('light');
            });

            journalList.appendChild(card);
        });
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    async function fetchEntries() {
        const userId = getUserId();

        if (!userId) {
            loadingState.classList.add('hidden');
            errorState.classList.remove('hidden');
            errorText.textContent = 'Could not identify user. Please open from Telegram.';
            return;
        }

        try {
            const res = await fetch(`/api/memories/${userId}`);
            if (!res.ok) throw new Error(`Server error (${res.status})`);

            const data = await res.json();
            allEntries = data;

            loadingState.classList.add('hidden');
            renderEntries(allEntries);
        } catch (err) {
            console.error('Fetch failed:', err);
            loadingState.classList.add('hidden');
            errorState.classList.remove('hidden');
            errorText.textContent = err.message || 'Failed to load entries.';
        }
    }

    // ── Search ──────────────────────────────────────────

    searchInput.addEventListener('input', () => {
        const query = searchInput.value.toLowerCase().trim();
        if (!query) {
            renderEntries(allEntries);
            return;
        }

        const filtered = allEntries.filter(e =>
            (e.title && e.title.toLowerCase().includes(query)) ||
            (e.content && e.content.toLowerCase().includes(query))
        );
        renderEntries(filtered);
    });

    // ── Daily Message ─────────────────────────────────────
    async function fetchDailyMessage() {
        const userId = getUserId();
        if (!userId || !dailyQuoteText) return;

        try {
            const res = await fetch(`/api/daily-message/${userId}`);
            if (!res.ok) throw new Error('Failed to fetch daily message');

            const data = await res.json();
            dailyQuoteText.textContent = data.content;
            dailyCard.classList.remove('loading');
        } catch (err) {
            console.error('Daily message fetch failed:', err);
            if (dailyQuoteText) {
                dailyQuoteText.textContent = "Every day is a fresh start. Aki is here to witness your journey.";
                dailyCard.classList.remove('loading');
            }
        }
    }

    // ── Welcome Flow ──────────────────────────────────────

    const welcomeOverlay = document.getElementById('welcomeOverlay');
    const welcomeSlides = document.getElementById('welcomeSlides');
    const welcomeDots = document.querySelectorAll('.welcome-dot');
    const welcomeFinishBtn = document.getElementById('welcomeFinishBtn');
    const welcomeTzValue = document.getElementById('welcomeTzValue');
    const welcomeTzTime = document.getElementById('welcomeTzTime');

    let welcomeSlide = 0;
    const totalWelcomeSlides = 3;
    let detectedTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';

    function goToWelcomeSlide(index) {
        if (index < 0 || index >= totalWelcomeSlides) return;
        welcomeSlide = index;
        const offset = -(index * 33.3333);
        welcomeSlides.style.transform = `translateX(${offset}%)`;

        welcomeDots.forEach((dot, i) => {
            dot.classList.toggle('active', i === index);
        });

        // Haptic feedback
        if (tg) tg.HapticFeedback.impactOccurred('light');
    }

    // Welcome dot clicks
    welcomeDots.forEach(dot => {
        dot.addEventListener('click', () => {
            goToWelcomeSlide(parseInt(dot.dataset.slide));
        });
    });

    // Welcome swipe
    let wTouchStartX = 0;
    let wTouchStartY = 0;
    let wIsSwiping = false;

    if (welcomeOverlay) {
        welcomeOverlay.addEventListener('touchstart', (e) => {
            wTouchStartX = e.touches[0].clientX;
            wTouchStartY = e.touches[0].clientY;
            wIsSwiping = false;
        }, { passive: true });

        welcomeOverlay.addEventListener('touchmove', (e) => {
            const dx = e.touches[0].clientX - wTouchStartX;
            const dy = e.touches[0].clientY - wTouchStartY;
            if (Math.abs(dx) > Math.abs(dy) && Math.abs(dx) > 10) {
                wIsSwiping = true;
            }
        }, { passive: true });

        welcomeOverlay.addEventListener('touchend', (e) => {
            if (!wIsSwiping) return;
            const dx = e.changedTouches[0].clientX - wTouchStartX;
            if (Math.abs(dx) > 50) {
                if (dx < 0 && welcomeSlide < totalWelcomeSlides - 1) {
                    goToWelcomeSlide(welcomeSlide + 1);
                } else if (dx > 0 && welcomeSlide > 0) {
                    goToWelcomeSlide(welcomeSlide - 1);
                }
            }
        }, { passive: true });
    }

    // Keyboard navigation for welcome slides
    document.addEventListener('keydown', (e) => {
        if (welcomeOverlay && !welcomeOverlay.classList.contains('hidden')) {
            if (e.key === 'ArrowLeft') goToWelcomeSlide(welcomeSlide - 1);
            if (e.key === 'ArrowRight') goToWelcomeSlide(welcomeSlide + 1);
        }
    });

    function showDetectedTimezone() {
        // Display auto-detected timezone on slide 3
        if (welcomeTzValue) {
            welcomeTzValue.textContent = detectedTimezone.replace(/_/g, ' ');
        }
        if (welcomeTzTime) {
            const now = new Date();
            const timeStr = now.toLocaleTimeString('en-US', {
                hour: 'numeric',
                minute: '2-digit',
                timeZone: detectedTimezone,
            });
            welcomeTzTime.textContent = timeStr + ' right now';
        }
    }

    async function completeSetup() {
        const userId = getUserId();
        if (!userId) return;

        welcomeFinishBtn.disabled = true;
        welcomeFinishBtn.querySelector('span').textContent = 'Setting up...';

        try {
            const res = await fetch(`/api/user/${userId}/setup`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ timezone: detectedTimezone }),
            });

            if (!res.ok) throw new Error(`Setup failed (${res.status})`);

            // Smooth exit
            if (tg) tg.HapticFeedback.notificationOccurred('success');
            welcomeOverlay.classList.add('exiting');
            setTimeout(() => {
                welcomeOverlay.classList.add('hidden');
                welcomeOverlay.classList.remove('exiting');
            }, 500);

        } catch (err) {
            console.error('Setup error:', err);
            welcomeFinishBtn.disabled = false;
            welcomeFinishBtn.querySelector('span').textContent = 'Get Started';
            // Still dismiss — don't trap them in the overlay
            welcomeOverlay.classList.add('hidden');
        }
    }

    if (welcomeFinishBtn) {
        welcomeFinishBtn.addEventListener('click', completeSetup);
    }

    // ── Init ──────────────────────────────────────────────

    async function init() {
        const userId = getUserId();

        if (userId) {
            try {
                // Check user profile for onboarding state
                const res = await fetch(`/api/user/${userId}`);
                if (res.ok) {
                    const profile = await res.json();

                    if (profile.onboarding_state !== null && profile.onboarding_state !== undefined) {
                        // User hasn't completed onboarding — show welcome flow
                        showDetectedTimezone();
                        welcomeOverlay.classList.remove('hidden');
                    } else {
                        // Also silently update timezone if it's still the default
                        // and the detected one is different
                        if (profile.timezone === 'America/Toronto' && detectedTimezone !== 'America/Toronto') {
                            fetch(`/api/user/${userId}/setup`, {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ timezone: detectedTimezone }),
                            }).catch(() => { }); // Silent, non-blocking
                        }
                    }
                }
            } catch (err) {
                console.error('Failed to check user profile:', err);
            }
        }

        // Load data regardless of onboarding state
        fetchEntries();
        fetchDailyMessage();
        goToPanel(1); // Initialize UI to Today
    }

    init();

})();
