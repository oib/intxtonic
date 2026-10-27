import { authHeaders, getToken, clearToken } from '/src/frontend/js/auth.js';
import { showToast } from '/src/frontend/js/toast.js';
import { t } from '/src/frontend/js/i18n-runtime.js';
import preloader from '/src/frontend/js/preloader.js';

// Initialize preloader
preloader.init();

const logoutBtn = document.getElementById('logout-btn');
const profileLink = document.getElementById('profile-link');
const adminLink = document.getElementById('admin-link');
const newPostLink = document.getElementById('newpost-link');
const welcomeHeading = document.getElementById('welcome-heading');
const welcomeSubheading = document.getElementById('welcome-subheading');
const latestPosts = document.getElementById('auth-latest-posts');

if (profileLink) {
  const defaultLabel = profileLink.dataset.defaultLabel || profileLink.textContent || 'Profile';
  profileLink.dataset.defaultLabel = defaultLabel;
  profileLink.textContent = defaultLabel;
  profileLink.style.display = 'none';
}

logoutBtn.addEventListener('click', async () => {
  try {
    await fetch('/auth/logout', { method: 'POST', headers: { ...authHeaders() } });
  } catch {}
  clearToken();
  showToast(t('toast.signed_out'), 'ok');
  window.location.href = '/';
});

function renderPostsSkeleton(){
  latestPosts.innerHTML = '<div class="skeleton"></div>'.repeat(3);
}

const sanitisePreview = (md = '') => {
  return md
    .replace(/!\[[^\]]*\]\([^)]*\)/g, '')
    .replace(/<img[^>]*>/gi, '')
    .replace(/\s+/g, ' ')
    .trim();
};

async function loadLatestForUser(){
  renderPostsSkeleton();
  try {
    const params = new URLSearchParams({ sort: 'newest', limit: '6' });
    const res = await fetch(`/posts?${params.toString()}`, { headers: { ...authHeaders() } });
    if (res.status === 401){
      clearToken();
      window.location.href = '/login/';
      return;
    }
    if (!res.ok) throw new Error('Failed');
    const data = await res.json();
    const items = Array.isArray(data.items) ? data.items.slice(0,6) : [];
    if (!items.length){
      latestPosts.innerHTML = '<div class="badge">No posts yet. Start by creating your first one!</div>';
      return;
    }
    latestPosts.innerHTML = items.map(item => {
      const previewSrc = sanitisePreview(item.body_md || '');
      const preview = previewSrc.slice(0, 200);
      const ellipsis = previewSrc.length > 200 ? '…' : '';
      return `
      <article class="home-post" role="listitem">
        <a class="home-post__title" href="/post/${item.id}">${item.title}</a>
        <div class="home-post__meta">${item.author ? `by ${item.author}` : 'by someone'}${item.created_at ? ` · ${new Date(item.created_at).toLocaleDateString()}` : ''}</div>
        <p class="home-post__excerpt">${preview}${ellipsis}</p>
        <div class="home-post__tags">
          ${(Array.isArray(item.tags) ? item.tags : []).filter(t => !t.is_restricted).slice(0,3).map(tag => `<a href="/tags/${encodeURIComponent(tag.slug)}" class="badge badge--link">#${tag.slug}</a>`).join('')}
        </div>
      </article>
    `}).join('');
  } catch (err){
    latestPosts.innerHTML = '<div class="badge badge--err">Unable to load personalised posts right now.</div>';
  }
}

async function init(){
  const token = getToken();
  if (!token){
    window.location.href = '/login/';
    return;
  }
  try {
    const res = await fetch('/auth/me', { headers: { ...authHeaders() } });
    if (res.status === 401){
      clearToken();
      window.location.href = '/login/';
      return;
    }
    if (!res.ok) throw new Error('Failed to load profile');
    const user = await res.json();
    newPostLink.style.display = 'inline-flex';
    if (profileLink) {
      profileLink.style.display = 'inline-flex';
      profileLink.href = `/user/${encodeURIComponent(user.handle)}`;
      const label = (user.display_name || user.handle || '').trim();
      const defaultLabel = profileLink.dataset.defaultLabel || 'Profile';
      profileLink.textContent = label || defaultLabel;
    }
    const displayName = (user.display_name || '').trim();
    const handle = (user.handle || '').trim();
    const greetingName = displayName || handle || t('nav.profile');
    const subheadingHandle = handle || greetingName;
    welcomeHeading.textContent = t('home.welcome_back_user', { name: greetingName });
    welcomeSubheading.textContent = t('home.welcome_subheading_user', { handle: subheadingHandle });
    if (adminLink) {
      const isAdmin = user.is_admin || (Array.isArray(user.roles) && user.roles.includes('admin'));
      adminLink.style.display = isAdmin ? 'inline-flex' : 'none';
      adminLink.parentElement.style.justifyContent = isAdmin ? 'center' : '';
      adminLink.parentElement.style.gap = isAdmin ? '12px' : '8px';
    }
  } catch (err){
    clearToken();
    window.location.href = '/login/';
    return;
  }
  await loadLatestForUser();
}

init();
