/* ═══════════════════════════════════════════════════════
   Aki — Telegram Mini App Logic (TypeScript Version)
   ═══════════════════════════════════════════════════════ */

import './style.css';

// ── Types & Interfaces ──────────────────────────────

interface TelegramUser {
  id: number;
  first_name: string;
  last_name?: string;
  username?: string;
  language_code?: string;
}

interface TelegramWebApp {
  ready: () => void;
  expand: () => void;
  disableVerticalSwipes: () => void;
  setHeaderColor: (color: string) => void;
  setBackgroundColor: (color: string) => void;
  HapticFeedback: {
    impactOccurred: (style: 'light' | 'medium' | 'heavy' | 'rigid' | 'soft') => void;
    notificationOccurred: (type: 'error' | 'success' | 'warning') => void;
  };
  BackButton: {
    show: () => void;
    hide: () => void;
    onClick: (cb: () => void) => void;
    offClick: (cb: () => void) => void;
  };
  onEvent: (eventType: string, eventHandler: () => void) => void;
  themeParams: {
    header_bg_color?: string;
    bg_color?: string;
  };
  initDataUnsafe: {
    user?: TelegramUser;
  };
}

declare global {
  interface Window {
    Telegram?: {
      WebApp: TelegramWebApp;
    };
  }
}

interface JournalEntry {
  id: string;
  title: string;
  content: string;
  entry_type: string;
  importance: number;
  timestamp: string;
  exchange_start?: string;
  exchange_end?: string;
}

interface UserProfile {
  telegram_id: number;
  name: string;
  username: string;
  timezone: string;
  onboarding_state: string | null;
}

// ── Initialization ──────────────────────────────────

const tg = window.Telegram?.WebApp;

if (tg) {
  tg.ready();
  tg.expand();
  tg.disableVerticalSwipes();
  tg.setHeaderColor(tg.themeParams.header_bg_color || '#ffffff');
  tg.setBackgroundColor(tg.themeParams.bg_color || '#ffffff');
}

// ── State ──────────────────────────────────────────

let currentPanel = 1; // Start on Today
const totalPanels = 3;
let allEntries: JournalEntry[] = [];
let detectedTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';

// ── DOM References ──────────────────────────────────

const container = document.getElementById('panelsContainer') as HTMLElement;
const navTabs = document.querySelectorAll('.nav-tab') as NodeListOf<HTMLButtonElement>;
const dots = document.querySelectorAll('.dot') as NodeListOf<HTMLSpanElement>;
const todayDate = document.getElementById('todayDate') as HTMLElement;
const dailyQuoteText = document.getElementById('dailyQuoteText') as HTMLElement;
const dailyCard = document.getElementById('dailyCard') as HTMLElement;
const journalList = document.getElementById('journalList') as HTMLElement;
const searchInput = document.getElementById('searchInput') as HTMLInputElement;
const searchBar = document.getElementById('searchBar') as HTMLElement;
const loadingState = document.getElementById('loadingState') as HTMLElement;
const errorState = document.getElementById('errorState') as HTMLElement;
const errorText = document.getElementById('errorText') as HTMLElement;
const emptyState = document.getElementById('emptyState') as HTMLElement;

const welcomeOverlay = document.getElementById('welcomeOverlay') as HTMLElement;
const welcomeSlides = document.getElementById('welcomeSlides') as HTMLElement;
const welcomeDots = document.querySelectorAll('.welcome-dot') as NodeListOf<HTMLSpanElement>;
const welcomeFinishBtn = document.getElementById('welcomeFinishBtn') as HTMLButtonElement;
const welcomeTzValue = document.getElementById('welcomeTzValue') as HTMLElement;
const welcomeTzTime = document.getElementById('welcomeTzTime') as HTMLElement;
const welcomeNameInput = document.getElementById('welcomeNameInput') as HTMLInputElement;
const welcomeNameContinue = document.getElementById('welcomeNameContinue') as HTMLButtonElement;

// ── Navigation ──────────────────────────────────────

function goToPanel(index: number) {
  if (index < 0 || index >= totalPanels) return;
  currentPanel = index;
  const offset = -(index * 33.3333);
  if (container) container.style.transform = `translateX(${offset}%)`;

  navTabs.forEach((tab, i) => {
    tab.classList.toggle('active', i === index);
  });

  dots.forEach((dot, i) => {
    dot.classList.toggle('active', i === index);
  });

  if (tg) {
    if (index !== 1) {
      tg.BackButton.show();
    } else {
      tg.BackButton.hide();
    }
  }
}

navTabs.forEach(tab => {
  tab.addEventListener('click', () => {
    const panel = tab.getAttribute('data-panel');
    if (panel) goToPanel(parseInt(panel));
  });
});

dots.forEach(dot => {
  dot.addEventListener('click', () => {
    const panel = dot.getAttribute('data-panel');
    if (panel) goToPanel(parseInt(panel));
  });
});

if (tg) {
  tg.onEvent('backButtonClicked', () => {
    goToPanel(1); // Always go back to Today
  });
  tg.onEvent('themeChanged', () => {
    document.body.style.display = 'none';
    document.body.offsetHeight; // trigger reflow
    document.body.style.display = '';
  });
}

// ── Touch Swipe ─────────────────────────────────────

let touchStartX = 0;
let touchStartY = 0;
let isSwiping = false;

if (container) {
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
}

// ── Keyboard Navigation ──
document.addEventListener('keydown', (e: KeyboardEvent) => {
  if (e.key === 'ArrowLeft') goToPanel(currentPanel - 1);
  if (e.key === 'ArrowRight') goToPanel(currentPanel + 1);
});

// ── Utils ──────────────────────────────────────────

function getUserId(): string | number | undefined {
  const urlParams = new URLSearchParams(window.location.search);
  return urlParams.get('user_id') || tg?.initDataUnsafe?.user?.id;
}

function formatDate(isoStr?: string): string {
  if (!isoStr) return '';
  const d = new Date(isoStr);
  if (isNaN(d.getTime())) return '';
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function formatRange(startIso?: string, endIso?: string, timestampIso?: string): string {
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

function truncateText(text?: string, maxLen: number = 300): string {
  if (!text || text.length <= maxLen) return text || '';
  return text.substring(0, maxLen).trim() + '…';
}

function escapeHtml(text: string): string {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// ── Journal Logic ──────────────────────────────────

function renderEntries(entries: JournalEntry[]) {
  if (!journalList) return;
  journalList.innerHTML = '';

  if (entries.length === 0) {
    emptyState?.classList.remove('hidden');
    searchBar?.classList.add('hidden');
    return;
  }

  emptyState?.classList.add('hidden');
  searchBar?.classList.remove('hidden');

  entries.forEach((entry) => {
    const card = document.createElement('div');
    card.className = 'journal-card';

    const tags: string[] = [];
    if (entry.entry_type) {
      tags.push(entry.entry_type.replace(/_/g, ' '));
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

    card.addEventListener('click', () => {
      const wasExpanded = card.classList.contains('expanded');
      card.classList.toggle('expanded');
      const preview = card.querySelector('.journal-card-preview');
      if (preview) {
        preview.textContent = wasExpanded ? truncateText(entry.content, 300) : (entry.content || '');
      }
      if (tg) tg.HapticFeedback.impactOccurred('light');
    });

    journalList.appendChild(card);
  });
}

async function fetchEntries() {
  const userId = getUserId();
  if (!userId) {
    loadingState?.classList.add('hidden');
    if (errorState) {
      errorState.classList.remove('hidden');
      errorText.textContent = 'Could not identify user. Please open from Telegram.';
    }
    return;
  }

  try {
    const res = await fetch(`/api/memories/${userId}`);
    if (!res.ok) throw new Error(`Server error (${res.status})`);
    const data: JournalEntry[] = await res.json();
    allEntries = data;
    loadingState?.classList.add('hidden');
    renderEntries(allEntries);
  } catch (err: any) {
    console.error('Fetch failed:', err);
    loadingState?.classList.add('hidden');
    if (errorState) {
      errorState.classList.remove('hidden');
      errorText.textContent = err.message || 'Failed to load entries.';
    }
  }
}

if (searchInput) {
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
}

// ── Daily Message ─────────────────────────────────────

async function fetchDailyMessage() {
  const userId = getUserId();
  if (!userId || !dailyQuoteText) return;

  try {
    const res = await fetch(`/api/daily-message/${userId}`);
    if (!res.ok) throw new Error('Failed to fetch daily message');
    const data = await res.json();
    dailyQuoteText.textContent = data.content;
    dailyCard?.classList.remove('loading');
  } catch (err) {
    console.error('Daily message fetch failed:', err);
    if (dailyQuoteText) {
      dailyQuoteText.textContent = "Every day is a fresh start. Aki is here to witness your journey.";
      dailyCard?.classList.remove('loading');
    }
  }
}

// ── Welcome Flow ──────────────────────────────────────

let welcomeSlideIndex = 0;
const totalWelcomeSlides = 4;

function goToWelcomeSlide(index: number) {
  if (index < 0 || index >= totalWelcomeSlides) return;

  // Prevent swiping past name if name is empty
  if (index > 1 && welcomeSlideIndex === 1 && welcomeNameInput && !welcomeNameInput.value.trim()) {
    welcomeNameInput.focus();
    if (tg) tg.HapticFeedback.notificationOccurred('error');
    return;
  }

  welcomeSlideIndex = index;
  const offset = -(index * 25);
  if (welcomeSlides) welcomeSlides.style.transform = `translateX(${offset}%)`;

  welcomeDots.forEach((dot, i) => {
    dot.classList.toggle('active', i === index);
  });

  if (tg) tg.HapticFeedback.impactOccurred('light');
}

if (welcomeNameInput) {
  welcomeNameInput.addEventListener('input', () => {
    const val = welcomeNameInput.value.trim();
    if (welcomeNameContinue) welcomeNameContinue.disabled = val.length < 2;
  });

  welcomeNameInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter' && welcomeNameContinue && !welcomeNameContinue.disabled) {
      goToWelcomeSlide(2);
    }
  });
}

welcomeNameContinue?.addEventListener('click', () => {
  goToWelcomeSlide(2);
});

welcomeDots.forEach(dot => {
  dot.addEventListener('click', () => {
    const slide = dot.getAttribute('data-slide');
    if (slide) goToWelcomeSlide(parseInt(slide));
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
      if (dx < 0 && welcomeSlideIndex < totalWelcomeSlides - 1) {
        goToWelcomeSlide(welcomeSlideIndex + 1);
      } else if (dx > 0 && welcomeSlideIndex > 0) {
        goToWelcomeSlide(welcomeSlideIndex - 1);
      }
    }
  }, { passive: true });
}

function showDetectedTimezone() {
  if (welcomeTzValue) {
    welcomeTzValue.textContent = detectedTimezone.replace(/_/g, ' ');
  }
  if (welcomeTzTime) {
    const nowStr = new Date().toLocaleTimeString('en-US', {
      hour: 'numeric',
      minute: '2-digit',
      timeZone: detectedTimezone,
    });
    welcomeTzTime.textContent = nowStr + ' right now';
  }
}

async function completeSetup() {
  const userId = getUserId();
  if (!userId) return;

  const chosenName = welcomeNameInput ? welcomeNameInput.value.trim() : null;

  if (welcomeFinishBtn) {
    welcomeFinishBtn.disabled = true;
    const span = welcomeFinishBtn.querySelector('span');
    if (span) span.textContent = 'Setting up...';
  }

  try {
    const res = await fetch(`/api/user/${userId}/setup`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        timezone: detectedTimezone,
        name: chosenName
      }),
    });

    if (!res.ok) throw new Error(`Setup failed (${res.status})`);

    if (tg) tg.HapticFeedback.notificationOccurred('success');
    welcomeOverlay?.classList.add('exiting');
    setTimeout(() => {
      welcomeOverlay?.classList.add('hidden');
      welcomeOverlay?.classList.remove('exiting');
    }, 500);

  } catch (err) {
    console.error('Setup error:', err);
    if (welcomeFinishBtn) {
      welcomeFinishBtn.disabled = false;
      const span = welcomeFinishBtn.querySelector('span');
      if (span) span.textContent = 'Get Started';
    }
    welcomeOverlay?.classList.add('hidden');
  }
}

welcomeFinishBtn?.addEventListener('click', completeSetup);

// ── Init ──────────────────────────────────────────────

async function init() {
  // Today's Date
  if (todayDate) {
    const dateOptions: Intl.DateTimeFormatOptions = { weekday: 'long', month: 'long', day: 'numeric' };
    todayDate.textContent = new Date().toLocaleDateString('en-US', dateOptions);
  }

  const userId = getUserId();

  if (userId) {
    try {
      const res = await fetch(`/api/user/${userId}`);
      if (res.ok) {
        const profile: UserProfile = await res.json();

        if (profile.onboarding_state !== null && profile.onboarding_state !== undefined) {
          if (profile.name && welcomeNameInput) {
            welcomeNameInput.value = profile.name;
            if (welcomeNameContinue) welcomeNameContinue.disabled = false;
          }
          showDetectedTimezone();
          welcomeOverlay?.classList.remove('hidden');
        } else {
          if (profile.timezone === 'America/Toronto' && detectedTimezone !== 'America/Toronto') {
            fetch(`/api/user/${userId}/setup`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ timezone: detectedTimezone }),
            }).catch(() => { });
          }
        }
      }
    } catch (err) {
      console.error('Failed to check user profile:', err);
    }
  }

  fetchEntries();
  fetchDailyMessage();
  goToPanel(1); // Initialize UI to Today
}

init();
