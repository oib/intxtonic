import { t } from './i18n-runtime.js';

const TOAST_DEFAULTS = {
  'toast.signed_out': 'Signed out',
  'toast.login_to_vote': 'Login to vote',
  'toast.already_voted': 'You have already voted on this post',
  'toast.vote_recorded': 'Vote recorded',
  'toast.vote_failed': 'Vote failed',
  'toast.shared_success': 'Shared successfully',
  'toast.share_failed': 'Share failed',
  'toast.share_unsupported': 'Sharing not supported on this browser',
  'toast.copy_success': 'Link copied to clipboard',
  'toast.copy_failed': 'Copy failed',
  'toast.write_something': 'Write something',
  'toast.reply_posted': 'Reply posted',
  'toast.reply_failed': 'Reply failed',
  'toast.load_failed': 'Failed to load',
  'toast.saved': 'Saved',
  'toast.error': 'Error',
  'toast.tag_banned': 'Tag banned',
  'toast.tag_unbanned': 'Tag unbanned',
  'toast.import_failed': 'Import failed',
  'toast.translate_failed': 'Translate failed',
  'toast.nothing_to_translate': 'Nothing to translate'
};

export function showToast(msg, type = "ok", ms = 3500) {
  if (typeof msg === 'string' && msg.startsWith('toast.')) {
    const translated = t(msg);
    msg = translated !== msg ? translated : (TOAST_DEFAULTS[msg] || msg);
  }

  const root = document.getElementById("toast-root") || (() => {
    const r = document.createElement("div");
    r.id = "toast-root";
    document.body.appendChild(r);
    return r;
  })();

  const el = document.createElement("div");
  el.className = `toast toast--${type}`;
  el.role = "status";
  el.textContent = msg;
  root.appendChild(el);

  const timeoutId = setTimeout(() => el.remove(), ms);
  el.addEventListener("mouseenter", () => clearTimeout(timeoutId));
  el.addEventListener("click", () => el.remove());
}
