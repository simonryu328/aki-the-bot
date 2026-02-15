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
    }

    // ── State ──
    let currentPanel = 0; // Start on Journal
    const totalPanels = 3;
    let allEntries = [];   // Full dataset for search

    // ── DOM References ──
    const container = document.getElementById('panelsContainer');
    const navTabs = document.querySelectorAll('.nav-tab');
    const dots = document.querySelectorAll('.dot');
    const todayDate = document.getElementById('todayDate');
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
            if (index !== 0) {
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
            goToPanel(0); // Always go back to Journal
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

    function formatDate(isoStr) {
        const d = new Date(isoStr);
        return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
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
            if (entry.type) {
                const label = entry.type.replace(/_/g, ' ');
                tags.push(label);
            }
            if (entry.importance && entry.importance >= 7) {
                tags.push('important');
            }

            card.innerHTML = `
        <div class="journal-card-date">${formatDate(entry.created_at)}</div>
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

    // ── Init ──
    fetchEntries();

})();
