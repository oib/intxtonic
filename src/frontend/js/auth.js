// Simple auth helper: stores JWT, wraps fetch with Authorization
export const AUTH_TOKEN_KEY = "auth_token";

export function saveToken(token){
  try{ localStorage.setItem(AUTH_TOKEN_KEY, token); }catch(e){}
}
export function getToken(){
  try{ return localStorage.getItem(AUTH_TOKEN_KEY) || ""; }catch(e){ return ""; }
}
export function clearToken(){
  try{ localStorage.removeItem(AUTH_TOKEN_KEY); }catch(e){}
}

function getCookie(name){
  try{
    const v = document.cookie.split('; ').find(row => row.startsWith(name + '='));
    return v ? decodeURIComponent(v.split('=')[1]) : '';
  }catch(e){ return ''; }
}

export function authHeaders(){
  const t = getToken();
  const headers = {};
  if (t) headers.Authorization = `Bearer ${t}`;
  const csrf = getCookie('csrf_token');
  if (csrf) headers['X-CSRF-Token'] = csrf;
  return headers;
}

export async function login(handleOrEmail, password){
  const res = await fetch('/auth/login',{
    method:'POST', headers:{ 'Content-Type':'application/json' },
    body: JSON.stringify({ handle_or_email: handleOrEmail, password })
  });
  if(!res.ok) throw new Error(await res.text());
  const data = await res.json();
  if(data?.access_token) saveToken(data.access_token);
  return data;
}

export async function register(handle, email, password){
  const res = await fetch('/auth/register',{
    method:'POST', headers:{ 'Content-Type':'application/json' },
    body: JSON.stringify({ handle, email, password })
  });
  if(!res.ok) throw new Error(await res.text());
  const data = await res.json();
  if(data?.access_token) saveToken(data.access_token);
  return data;
}

export async function confirmEmail(token){
  const res = await fetch('/auth/confirm-email', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token })
  });
  if(!res.ok) throw new Error(await res.text());
  return res.json().catch(() => ({}));
}

export async function resendConfirmation(){
  const res = await fetch('/auth/resend-confirmation', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({})
  });
  if(!res.ok) throw new Error(await res.text());
  return res.json().catch(() => ({}));
}

export async function me(){
  const res = await fetch('/auth/me',{ headers:{ ...authHeaders() } });
  if(!res.ok) throw new Error(await res.text());
  return res.json();
}

// Shared UI helper: show/hide login/logout and set Profile link when logged in
export function refreshAuthUI() {
  const loginLink = document.getElementById('login-link');
  const logoutBtn = document.getElementById('logout-btn');
  const profileLink = document.getElementById('profile-link');
  const settingsLink = document.getElementById('settings-link');
  const newPostLink = document.getElementById('newpost-link');
  const profileSettingsBtn = document.getElementById('profile-settings-btn');
  const profileHandle = document.body?.dataset?.profileHandle;
  const has = !!getToken();
  if (loginLink) loginLink.style.display = has ? 'none' : 'inline-flex';
  if (logoutBtn) logoutBtn.style.display = has ? 'inline-flex' : 'none';
  if (newPostLink) newPostLink.style.display = has ? 'inline-flex' : 'none';
  if (profileLink) {
    const defaultLabel = profileLink.dataset.defaultLabel || profileLink.textContent || 'Profile';
    profileLink.dataset.defaultLabel = defaultLabel;
    profileLink.style.display = 'none';
    profileLink.textContent = defaultLabel;
    if (has) {
      fetch('/auth/me', { headers: { ...authHeaders() } })
        .then(r => r.ok ? r.json() : null)
        .then(u => {
          if (u && u.handle) {
            profileLink.href = `/user/${encodeURIComponent(u.handle)}`;
            const label = (u.display_name || u.handle || '').trim();
            if (label) profileLink.textContent = label;
            profileLink.style.display = 'inline-flex';
            if (settingsLink) {
              settingsLink.style.display = profileHandle && profileHandle === u.handle ? 'inline-flex' : 'none';
            }
            if (profileSettingsBtn) {
              profileSettingsBtn.style.display = profileHandle && profileHandle === u.handle ? 'inline-flex' : 'none';
            }
          }
        })
        .catch(() => {});
    } else if (settingsLink) {
      settingsLink.style.display = 'none';
    }
    if (!has && profileSettingsBtn) {
      profileSettingsBtn.style.display = 'none';
    }
  } else if (settingsLink) {
    settingsLink.style.display = has ? 'inline-flex' : 'none';
    if (profileSettingsBtn) {
      profileSettingsBtn.style.display = has ? 'inline-flex' : 'none';
    }
  }
}
