import { authHeaders, getToken } from './auth.js';
import { showToast } from './toast.js';

const toggleRegistry = new Map(); // key -> Set<HTMLButtonElement>
const bookmarkState = new Map(); // key -> { bookmarkId, tags, createdAt }
let listenerBound = false;

const KEY_DELIMITER = '::';

function keyFrom(targetType, targetId) {
  return `${targetType}${KEY_DELIMITER}${targetId}`;
}

function ensureListener() {
  if (listenerBound) return;
  document.addEventListener('click', async (event) => {
    const btn = event.target?.closest?.('.bookmark-toggle');
    if (!btn) return;
    const targetType = (btn.dataset.targetType || '').trim().toLowerCase();
    const targetId = (btn.dataset.targetId || '').trim();
    if (!targetType || !targetId) return;
    event.preventDefault();
    if (btn.dataset.loading === 'true') return;

    if (!getToken()) {
      showToast('Login to manage bookmarks', 'warn');
      window.location.href = '/login';
      return;
    }

    const key = btn.dataset.bookmarkKey || keyFrom(targetType, targetId);
    btn.dataset.loading = 'true';

    try {
      if (bookmarkState.has(key)) {
        // Remove bookmark
        const params = new URLSearchParams({
          target_type: targetType,
          target_id: targetId,
        });
        const res = await fetch(`/bookmarks?${params.toString()}`, {
          method: 'DELETE',
          headers: { ...authHeaders() },
        });
        if (res.status === 401) {
          showToast('Session expired. Please sign in again', 'warn');
          window.location.href = '/login';
          return;
        }
        if (!res.ok) {
          const txt = await res.text().catch(() => 'Failed to remove bookmark');
          throw new Error(txt || 'Failed to remove bookmark');
        }
        bookmarkState.delete(key);
        applyStateToToggles(key);
        showToast('Removed from bookmarks', 'ok');
      } else {
        const res = await fetch('/bookmarks', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', ...authHeaders() },
          body: JSON.stringify({ target_type: targetType, target_id: targetId }),
        });
        if (res.status === 401) {
          showToast('Session expired. Please sign in again', 'warn');
          window.location.href = '/login';
          return;
        }
        if (!res.ok) {
          const txt = await res.text().catch(() => 'Failed to bookmark');
          throw new Error(txt || 'Failed to bookmark');
        }
        const data = await res.json().catch(() => null);
        bookmarkState.set(key, {
          bookmarkId: data?.id || '',
          tags: Array.isArray(data?.tags) ? data.tags : [],
          createdAt: data?.created_at || null,
        });
        applyStateToToggles(key);
        showToast('Bookmarked', 'ok');
      }
    } catch (err) {
      console.error('Bookmark toggle failed:', err);
      showToast(err?.message || 'Bookmark action failed', 'err');
    } finally {
      delete btn.dataset.loading;
    }
  });
  listenerBound = true;
}

function registerToggle(btn) {
  const type = (btn.dataset.targetType || '').trim().toLowerCase();
  const id = (btn.dataset.targetId || '').trim();
  if (!type || !id) return null;
  const key = keyFrom(type, id);
  let set = toggleRegistry.get(key);
  if (!set) {
    set = new Set();
    toggleRegistry.set(key, set);
  }
  set.add(btn);
  btn.dataset.bookmarkKey = key;
  btn.setAttribute('aria-pressed', btn.classList.contains('is-active') ? 'true' : 'false');
  return { key, type, id };
}

function applyStateToToggles(key) {
  const info = bookmarkState.get(key);
  const toggles = toggleRegistry.get(key);
  if (!toggles) return;
  const isActive = !!info;
  toggles.forEach((btn) => {
    if (isActive) {
      btn.classList.add('is-active');
      btn.setAttribute('aria-pressed', 'true');
      if (info.bookmarkId) {
        btn.dataset.bookmarkId = info.bookmarkId;
      }
    } else {
      btn.classList.remove('is-active');
      btn.setAttribute('aria-pressed', 'false');
      delete btn.dataset.bookmarkId;
    }
  });
}

async function fetchStateForType(targetType, ids) {
  if (!ids.length) return;
  try {
    const params = new URLSearchParams({
      target_type: targetType,
      target_ids: ids.join(','),
    });
    const res = await fetch(`/bookmarks/lookup?${params.toString()}`, {
      headers: { ...authHeaders() },
    });
    if (res.status === 401) {
      ids.forEach((id) => {
        const key = keyFrom(targetType, id);
        bookmarkState.delete(key);
        applyStateToToggles(key);
      });
      return;
    }
    if (!res.ok) {
      console.warn('Bookmark lookup failed', await res.text().catch(() => res.statusText));
      return;
    }
    const data = await res.json().catch(() => ({ items: [] }));
    const seen = new Set();
    for (const item of data.items || []) {
      const key = keyFrom(targetType, item.target_id);
      bookmarkState.set(key, {
        bookmarkId: item.bookmark_id,
        tags: Array.isArray(item.tags) ? item.tags : [],
        createdAt: item.created_at || null,
      });
      seen.add(key);
      applyStateToToggles(key);
    }
    ids.forEach((id) => {
      const key = keyFrom(targetType, id);
      if (!seen.has(key)) {
        bookmarkState.delete(key);
        applyStateToToggles(key);
      }
    });
  } catch (err) {
    console.error('Bookmark lookup error:', err);
  }
}

export async function initBookmarkToggles(root = document) {
  ensureListener();
  const toggles = Array.from(root.querySelectorAll('.bookmark-toggle'));
  if (!toggles.length) return;

  const grouped = new Map();
  toggles.forEach((btn) => {
    const info = registerToggle(btn);
    if (!info) return;
    applyStateToToggles(info.key);
    if (!grouped.has(info.type)) {
      grouped.set(info.type, new Set());
    }
    grouped.get(info.type).add(info.id);
  });

  if (!getToken()) {
    // Ensure all toggles appear inactive when logged out
    grouped.forEach((ids, type) => {
      ids.forEach((id) => {
        const key = keyFrom(type, id);
        bookmarkState.delete(key);
        applyStateToToggles(key);
      });
    });
    return;
  }

  await Promise.all(
    Array.from(grouped.entries()).map(([type, ids]) =>
      fetchStateForType(type, Array.from(ids))
    )
  );
}
