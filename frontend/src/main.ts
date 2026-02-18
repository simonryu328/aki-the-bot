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
  openLink: (url: string) => void;
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
  close: () => void;
}

declare global {
  interface Window {
    Telegram?: {
      WebApp: TelegramWebApp;
    };
    confetti?: any;
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

interface PersonalizedInsights {
  unhinged_quotes: {
    quote: string;
    context: string;
    emoji: string;
  }[];
  aki_observations: {
    title: string;
    description: string;
    emoji: string;
  }[];
  fun_questions: string[];
  personal_stats: {
    current_vibe: string;
    vibe_description: string;
    top_topic: string;
    topic_description: string;
  };
}

interface FutureEntry {
  id: number;
  entry_type: string;
  title: string;
  content?: string;
  start_time?: string;
  end_time?: string;
  is_all_day: boolean;
  is_completed: boolean;
  source: string;
  created_at: string;
}

interface DashboardData {
  profile: UserProfile;
  memories: JournalEntry[];
  daily_message: {
    content: string;
    timestamp: string;
    is_fallback: boolean;
  };
  soundtrack: DailySoundtrack;
  insights: PersonalizedInsights;
  horizons: FutureEntry[];
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
let lastSeenMomentId: string | null = null;
let isPolling = false;
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
const emptyState = document.getElementById('emptyState') as HTMLElement;
const splashScreen = document.getElementById('splashScreen') as HTMLElement;

const welcomeOverlay = document.getElementById('welcomeOverlay') as HTMLElement;
const welcomeSlides = document.getElementById('welcomeSlides') as HTMLElement;
const welcomeDots = document.querySelectorAll('.welcome-dot') as NodeListOf<HTMLSpanElement>;
const welcomeFinishBtn = document.getElementById('welcomeFinishBtn') as HTMLButtonElement;
const welcomeTzValue = document.getElementById('welcomeTzValue') as HTMLElement;
const welcomeTzTime = document.getElementById('welcomeTzTime') as HTMLElement;
const welcomeNameInput = document.getElementById('welcomeNameInput') as HTMLInputElement;
const welcomeNameContinue = document.getElementById('welcomeNameContinue') as HTMLButtonElement;

// ── Soundtrack Refs ────────────────────────────────
const soundtrackContainer = document.getElementById('soundtrackContainer') as HTMLElement;
const soundtrackLoading = document.getElementById('soundtrackLoading') as HTMLElement;
const soundtrackConnect = document.getElementById('soundtrackConnect') as HTMLElement;
const soundtrackCard = document.getElementById('soundtrackCard') as HTMLElement;
const connectSpotifyBtn = document.getElementById('connectSpotifyBtn') as HTMLButtonElement;
const trackArt = document.getElementById('trackArt') as HTMLImageElement;
const trackVibe = document.getElementById('trackVibe') as HTMLElement;
const trackName = document.getElementById('trackName') as HTMLElement;
const trackArtist = document.getElementById('trackArtist') as HTMLElement;
const trackExplanation = document.getElementById('trackExplanation') as HTMLElement;
const playSpotifyBtn = document.getElementById('playSpotifyBtn') as HTMLAnchorElement;

interface DailySoundtrack {
  connected: boolean;
  vibe?: string;
  explanation?: string;
  track?: {
    name: string;
    artist: string;
    album_art: string;
    spotify_url: string;
    uri: string;
    preview_url?: string;
  };
  error?: string;
}

// Personalized Insights References
const personalizedInsightsContainer = document.getElementById('personalizedInsights') as HTMLElement;
const statVibe = document.getElementById('statVibe') as HTMLElement;
const statVibeDesc = document.getElementById('statVibeDesc') as HTMLElement;
const statTopic = document.getElementById('statTopic') as HTMLElement;
const statTopicDesc = document.getElementById('statTopicDesc') as HTMLElement;
const unhingedList = document.getElementById('unhingedList') as HTMLElement;
const observationsList = document.getElementById('observationsList') as HTMLElement;
const questionsList = document.getElementById('questionsList') as HTMLElement;
const todayComingSoon = document.getElementById('todayComingSoon') as HTMLElement;

// Notification & Overlay Refs
const reflectionOverlay = document.getElementById('reflectionOverlay') as HTMLElement;
const reflectionTitle = document.getElementById('reflectionTitle') as HTMLElement;
const reflectionPeek = document.getElementById('reflectionPeek') as HTMLElement;
const reflectionBtn = document.getElementById('reflectionBtn') as HTMLButtonElement;
const reflectionCloseBtn = document.getElementById('reflectionCloseBtn') as HTMLButtonElement;
const horizonsList = document.getElementById('horizonsList') as HTMLElement;

// ── Horizons Logic ──────────────────────────────────

function renderHorizons(entries: FutureEntry[]) {
  if (!horizonsList) return;

  if (entries.length === 0) {
    horizonsList.innerHTML = `
      <div class="coming-soon">
        <div class="coming-soon-icon">🌅</div>
        <p class="coming-soon-text">Your horizons are expanding.</p>
        <p class="coming-soon-hint">This is where Aki holds your plans, goals, and the things you're looking forward to.</p>
      </div>
    `;
    return;
  }

  horizonsList.innerHTML = '';
  entries.forEach(entry => {
    const card = document.createElement('div');
    card.className = 'horizon-card';

    const dateStr = entry.start_time ? new Date(entry.start_time).toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }) : 'Plan';

    card.innerHTML = `
      <div class="horizon-type">
        ${entry.entry_type === 'plan' ? '📅 Plan' : '✍️ Note'}
      </div>
      <div class="horizon-title">${escapeHtml(entry.title)}</div>
      ${entry.content ? `<div class="horizon-content">${escapeHtml(truncateText(entry.content, 100))}</div>` : ''}
      <div class="horizon-footer">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
        </svg>
        ${dateStr}
      </div>
    `;
    horizonsList.appendChild(card);
  });
}

// ── Soundtrack Logic ────────────────────────────────

const disconnectSpotifyBtn = document.getElementById('disconnectSpotifyBtn') as HTMLButtonElement;

async function fetchDailySoundtrack() {
  const userId = getUserId();
  if (!userId || !soundtrackContainer) return;

  // Show loading state while fetching
  soundtrackLoading?.classList.remove('hidden');
  soundtrackConnect?.classList.add('hidden');
  soundtrackCard?.classList.add('hidden');

  try {
    const res = await fetch(`/api/spotify/daily-soundtrack/${userId}?t=${Date.now()}`);
    if (!res.ok) throw new Error('Failed to fetch soundtrack');
    const data: DailySoundtrack = await res.json();

    renderSoundtrack(data);
  } catch (err) {
    console.error('Soundtrack fetch failed:', err);
    soundtrackLoading?.classList.add('hidden');
  }
}

function renderSoundtrack(data: DailySoundtrack) {
  if (!soundtrackContainer) return;
  soundtrackContainer.classList.remove('hidden');

  soundtrackLoading?.classList.add('hidden');
  soundtrackConnect?.classList.add('hidden');
  soundtrackCard?.classList.add('hidden');

  // Handle Error State
  if (data.error) {
    soundtrackLoading?.classList.remove('hidden');
    const p = soundtrackLoading.querySelector('p');

    if (data.error === 'unregistered') {
      if (p) p.innerHTML = 'Aki doesn\'t recognize you as a beta tester yet. <br><small>Ask Simon to add your email to the Spotify Dashboard.</small>';
      return; // STOP RETRYING
    }

    if (p) p.textContent = 'Aki is still thinking about your music. One sec...';

    // Auto-retry once after 3 seconds if it's a "still thinking" state
    setTimeout(fetchDailySoundtrack, 3000);
    return;
  }

  if (!data.connected) {
    soundtrackConnect?.classList.remove('hidden');
    return;
  }

  if (data.track) {
    if (trackArt) trackArt.src = data.track.album_art;
    if (trackVibe) trackVibe.textContent = data.vibe || 'Today\'s Vibe';
    if (trackName) trackName.textContent = data.track.name;
    if (trackArtist) trackArtist.textContent = data.track.artist;
    if (trackExplanation) trackExplanation.textContent = data.explanation || '';
    if (playSpotifyBtn) playSpotifyBtn.href = data.track.spotify_url;

    soundtrackCard?.classList.remove('hidden');
  } else if (data.connected) {
    // We are connected but don't have a track yet (Generation in progress)
    soundtrackLoading?.classList.remove('hidden');
    const p = soundtrackLoading.querySelector('p');
    if (p) p.textContent = 'Aki is choosing your song...';
    setTimeout(fetchDailySoundtrack, 3000);
  }
}

// Refresh soundtrack when coming back to the app
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'visible') {
    fetchDailySoundtrack();
  }
});

connectSpotifyBtn?.addEventListener('click', () => {
  const userId = getUserId();
  if (userId) {
    if (tg) tg.HapticFeedback.impactOccurred('medium');

    fetch(`/api/spotify/login/${userId}`)
      .then(res => res.json())
      .then(data => {
        if (data.url) {
          // IMPORTANT: openLink is required for Desktop Web to avoid iframe blocks
          if (tg) {
            tg.openLink(data.url);
          } else {
            window.location.href = data.url;
          }
        }
      })
      .catch(err => {
        console.error('Spotify login failed:', err);
        alert("Couldn't start Spotify connection. Please check your network.");
      });
  }
});

disconnectSpotifyBtn?.addEventListener('click', async () => {
  const userId = getUserId();
  if (!userId) return;

  if (!confirm('Disconnect your Spotify account from Aki?')) return;

  try {
    const res = await fetch(`/api/spotify/disconnect/${userId}`, { method: 'POST' });
    if (res.ok) {
      if (tg) tg.HapticFeedback.notificationOccurred('success');
      // Update UI state immediately
      renderSoundtrack({ connected: false });
    }
  } catch (err) {
    console.error('Failed to disconnect Spotify:', err);
  }
});

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

// ── Rendering Logic ──────────────────────────────────

function renderAll(data: DashboardData) {
  // 1. Profile / Onboarding logic
  if (data.profile.onboarding_state !== null && data.profile.onboarding_state !== undefined) {
    if (data.profile.name && welcomeNameInput) {
      welcomeNameInput.value = data.profile.name;
      if (welcomeNameContinue) welcomeNameContinue.disabled = false;
    }
    showDetectedTimezone();
    welcomeOverlay?.classList.remove('hidden');
  }

  // 2. Journal
  allEntries = data.memories;
  renderEntries(allEntries);

  // 3. Daily Message
  if (dailyQuoteText) {
    dailyQuoteText.textContent = data.daily_message.content;
    dailyCard?.classList.remove('loading');
  }

  // 4. Soundtrack
  renderSoundtrack(data.soundtrack);

  // 5. Insights
  renderPersonalizedInsights(data.insights);

  // 6. Horizons
  renderHorizons(data.horizons);
}


function renderPersonalizedInsights(data: PersonalizedInsights) {
  if (!personalizedInsightsContainer) return;

  // Show container, hide "coming soon"
  personalizedInsightsContainer.classList.remove('hidden');
  todayComingSoon?.classList.add('hidden');

  // Render Stats
  if (statVibe) statVibe.textContent = data.personal_stats.current_vibe;
  if (statVibeDesc) statVibeDesc.textContent = data.personal_stats.vibe_description;
  if (statTopic) statTopic.textContent = data.personal_stats.top_topic;
  if (statTopicDesc) statTopicDesc.textContent = data.personal_stats.topic_description;

  // Render Unhinged Quotes
  if (unhingedList) {
    unhingedList.innerHTML = '';
    data.unhinged_quotes.forEach(item => {
      const card = document.createElement('div');
      card.className = 'insight-card';
      card.innerHTML = `
        <div class="insight-emoji">${item.emoji || '🔥'}</div>
        <div class="insight-content">
          <div class="insight-quote">“${escapeHtml(item.quote)}”</div>
          <div class="insight-desc">${escapeHtml(item.context)}</div>
        </div>
      `;
      unhingedList.appendChild(card);
    });
  }

  // Render Observations
  if (observationsList) {
    observationsList.innerHTML = '';
    data.aki_observations.forEach(item => {
      const card = document.createElement('div');
      card.className = 'insight-card';
      card.innerHTML = `
        <div class="insight-emoji">${item.emoji || '👁️'}</div>
        <div class="insight-content">
          <div class="insight-title">${escapeHtml(item.title)}</div>
          <div class="insight-desc">${escapeHtml(item.description)}</div>
        </div>
      `;
      observationsList.appendChild(card);
    });
  }

  // Render Fun Questions
  if (questionsList) {
    questionsList.innerHTML = '';
    data.fun_questions.forEach(q => {
      const chip = document.createElement('div');
      chip.className = 'question-chip';
      chip.textContent = q;
      chip.addEventListener('click', async () => {
        if (tg) tg.HapticFeedback.impactOccurred('medium');

        const telegramId = tg?.initDataUnsafe?.user?.id || 1; // Fallback for testing

        try {
          // Disable chip during sending
          chip.style.opacity = '0.5';
          chip.style.pointerEvents = 'none';

          const response = await fetch(`/api/ask-question/${telegramId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ question: q })
          });

          if (response.ok) {
            if (tg) {
              tg.HapticFeedback.notificationOccurred('success');
              // Close immediately or with tiny delay
              console.log("Closing WebApp...");
              setTimeout(() => {
                tg.close();
              }, 100);
            }
          } else {
            throw new Error("Failed to send");
          }
        } catch (err) {
          console.error("Failed to send question", err);
          chip.style.opacity = '1';
          chip.style.pointerEvents = 'auto';
          alert("Aki is a bit busy right now. Try again in a second!");
        }
      });
      questionsList.appendChild(chip);
    });
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

// ── Notification & Real-time Logic ──────────────────

function showReflectionOverlay(entry: JournalEntry) {
  if (!reflectionOverlay || !reflectionTitle || !reflectionPeek || !reflectionBtn) return;

  reflectionTitle.textContent = entry.title || 'Recent Reflection';
  // TRUNCATED TEXT: User requested truncation again
  reflectionPeek.textContent = truncateText(entry.content, 180);
  reflectionOverlay.classList.remove('hidden');


  // Minimal delay for transition
  setTimeout(() => reflectionOverlay.classList.add('show'), 50);

  if (tg) tg.HapticFeedback.notificationOccurred('success');

  reflectionBtn.onclick = () => {
    reflectionOverlay.classList.remove('show');
    setTimeout(() => reflectionOverlay.classList.add('hidden'), 500);
    goToPanel(0); // Go to Journal
    if (tg) tg.HapticFeedback.impactOccurred('heavy');
  };

  if (reflectionCloseBtn) {
    reflectionCloseBtn.onclick = () => {
      reflectionOverlay.classList.remove('show');
      setTimeout(() => reflectionOverlay.classList.add('hidden'), 500);
      if (tg) tg.HapticFeedback.impactOccurred('light');
    };
  }
}


async function checkForNewMomories() {
  if (isPolling) return;
  const userId = getUserId();
  if (!userId) return;

  isPolling = true;
  try {
    const res = await fetch(`/api/memories/${userId}?t=${Date.now()}`);
    if (res.ok) {
      const entries: JournalEntry[] = await res.json();
      if (entries.length > 0) {
        const latest = entries[0];

        // If this is our first load, just set the baseline
        if (lastSeenMomentId === null) {
          lastSeenMomentId = latest.id;
          allEntries = entries;
          renderEntries(allEntries);
          return;
        }

        // If we find a newer ID than the one we saw last
        if (latest.id !== lastSeenMomentId) {
          console.log("New moment detected!", latest.title);
          lastSeenMomentId = latest.id;
          allEntries = entries;
          renderEntries(allEntries);

          // Show reflection overlay if we aren't already looking at the journal
          if (currentPanel !== 0) {
            showReflectionOverlay(latest);
          }
        }
      }
    }
  } catch (err) {
    console.error("Polling failed:", err);
  } finally {
    isPolling = false;
  }
}

function startPolling() {
  // Poll every 30 seconds
  setInterval(checkForNewMomories, 30000);
}

// ── Init ──────────────────────────────────────────────

// ── Init ──────────────────────────────────────────────

async function init() {
  // 1. Static UI setup
  if (todayDate) {
    const dateOptions: Intl.DateTimeFormatOptions = { weekday: 'long', month: 'long', day: 'numeric' };
    todayDate.textContent = new Date().toLocaleDateString('en-US', dateOptions);
  }

  const userId = getUserId();
  const urlParams = new URLSearchParams(window.location.search);
  const startPanel = urlParams.get('start_panel');

  // 2. Early Positioning: Default to Today (panel 1) immediately
  if (startPanel !== null) {
    const pIdx = parseInt(startPanel);
    if (!isNaN(pIdx)) goToPanel(pIdx);
  } else {
    goToPanel(1);
  }

  if (!userId) {
    splashScreen?.classList.add('fade-out');
    alert("Please open this app from within Telegram.");
    return;
  }

  // 2. Load from Cache (Instant Load)
  const CACHE_KEY = `aki_dashboard_v1_${userId}`;
  const cachedData = localStorage.getItem(CACHE_KEY);
  if (cachedData) {
    try {
      const parsed = JSON.parse(cachedData) as DashboardData;
      renderAll(parsed);
      // Hide splash early if we have cache
      setTimeout(() => splashScreen?.classList.add('fade-out'), 100);
    } catch (e) {
      console.error("Failed to parse cached dashboard data", e);
    }
  }

  // 3. Fetch Fresh Data (Background Refresh)
  try {
    const res = await fetch(`/api/dashboard/${userId}?t=${Date.now()}`);
    if (res.ok) {
      const freshData: DashboardData = await res.json();
      renderAll(freshData);
      localStorage.setItem(CACHE_KEY, JSON.stringify(freshData));

      // Celebration Flow (Only if landing on main page fresh)
      if (freshData.memories.length > 0) {
        const latest = freshData.memories[0];
        lastSeenMomentId = latest.id;
        const storedLastSeen = localStorage.getItem('aki_last_seen_moment_v6');

        // Only trigger if landing fresh on Today
        const isLandingOnToday = startPanel === null || startPanel === '1';

        if (isLandingOnToday && storedLastSeen !== latest.id) {
          showReflectionOverlay(latest);
          localStorage.setItem('aki_last_seen_moment_v6', latest.id);
        }
      }
    }
  } catch (err) {
    console.error('Failed to fetch dashboard:', err);
  }

  // 5. Start Real-time polling
  startPolling();

  // 6. Final Transition
  setTimeout(() => {
    splashScreen?.classList.add('fade-out');
  }, 500);
}

init();
