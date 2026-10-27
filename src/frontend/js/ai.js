// ai.js - Functions for interacting with AI endpoints for translation and summarization

import { authHeaders, getToken } from './auth.js';
import { showToast } from './toast.js';

const JOB_POLL_INTERVAL_MS = 2000;
const JOB_POLL_TIMEOUT_MS = 120000;

function escapeHTML(s) {
  return String(s ?? '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

// The API answers errors as {"error":{"message":…}} (older routes: {"detail":…}).
// Fall back to a short status line instead of dumping raw JSON or an HTML error page.
async function readError(res) {
  const txt = await res.text().catch(() => '');
  let msg = '';
  try {
    const j = JSON.parse(txt);
    msg = j?.error?.message || (typeof j?.detail === 'string' ? j.detail : '');
  } catch { /* not JSON */ }
  msg = String(msg || '').trim();
  return msg ? msg.slice(0, 200) : `HTTP ${res.status}`;
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function normalizeStatus(status) {
  return (status || '').toString().trim().toLowerCase();
}

function setButtonLoading(btn, label){
  if (!btn) return;
  if (!btn.dataset.originalLabel){
    btn.dataset.originalLabel = btn.textContent || '';
  }
  btn.disabled = true;
  btn.textContent = label;
  btn.setAttribute('aria-busy', 'true');
}

function resetButtonLoading(btn){
  if (!btn) return;
  btn.disabled = false;
  if (btn.dataset.originalLabel !== undefined){
    btn.textContent = btn.dataset.originalLabel;
    delete btn.dataset.originalLabel;
  }
  btn.removeAttribute('aria-busy');
}

async function pollJob(jobId) {
  const deadline = Date.now() + JOB_POLL_TIMEOUT_MS;
  while (Date.now() < deadline) {
    try {
      const res = await fetch(`/api/jobs/${encodeURIComponent(jobId)}`, {
        headers: { ...authHeaders() }
      });
      if (res.status === 404) {
        return { status: 'not_found' };
      }
      if (!res.ok) {
        return { status: 'failed', error: await readError(res) };
      }
      const data = await res.json().catch(() => ({}));
      const status = normalizeStatus(data.status);
      if (status === 'completed' || status === 'failed') {
        data.status = status;
        return data;
      }
    } catch (err) {
      // swallow errors during polling and retry
    }
    await sleep(JOB_POLL_INTERVAL_MS);
  }
  return { status: 'timeout' };
}

async function fetchCachedTranslation(postId) {
  const res = await fetch(`/api/posts/${postId}/translate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({})
  });
  if (!res.ok) {
    return null;
  }
  if (res.status === 202) {
    return null;
  }
  return res.json().catch(() => null);
}

async function fetchCachedSummary(postId, payload = {}) {
  const res = await fetch(`/api/posts/${postId}/summarize`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(payload)
  });
  if (!res.ok) {
    return null;
  }
  if (res.status === 202) {
    return null;
  }
  return res.json().catch(() => null);
}

// Function to request translation of a post
export async function translatePost(postId) {
  if (!getToken()) {
    showToast('Login to translate posts', 'warn');
    return null;
  }
  try {
    const response = await fetch(`/api/posts/${postId}/translate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({})
    });
    if (response.status === 202) {
      const queued = await response.json().catch(() => ({}));
      const jobId = queued?.job_id;
      if (!jobId) {
        throw new Error('Translation queued but job id missing');
      }
      showToast('Translation queued. We will notify you when it finishes.', 'info');
      const job = await pollJob(jobId);
      if (job.status === 'completed') {
        const translated = job.body_trans_md || job.translated_text || job.result;
        if (translated) {
          showToast('Post translated', 'ok');
          return { translated_text: translated };
        }
        const cached = await fetchCachedTranslation(postId);
        if (cached && cached.translated_text) {
          showToast('Post translated', 'ok');
          return cached;
        }
        throw new Error('Translation completed but result unavailable');
      }
      if (job.status === 'failed') {
        throw new Error(job.error || 'Translation job failed');
      }
      if (job.status === 'timeout') {
        throw new Error('Translation is taking longer than expected');
      }
      if (job.status === 'not_found') {
        throw new Error('Translation job not found');
      }
      throw new Error('Translation job ended unexpectedly');
    }
    if (!response.ok) {
      throw new Error(await readError(response));
    }
    const data = await response.json();
    showToast('Post translated', 'ok');
    return data;
  } catch (error) {
    showToast('Translation failed: ' + error.message, 'err');
    return null;
  }
}

// Function to request summarization of a post
export async function summarizePost(postId, opts = {}) {
  if (!getToken()) {
    showToast('Login to summarize posts', 'warn');
    return null;
  }
  try {
    const payload = { ...opts };
    const response = await fetch(`/api/posts/${postId}/summarize`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify(payload)
    });
    if (response.status === 202) {
      const queued = await response.json().catch(() => ({}));
      const jobId = queued?.job_id;
      if (!jobId) {
        throw new Error('Summarization queued but job id missing');
      }
      showToast('Summarization queued. Waiting for completion…', 'info');
      const job = await pollJob(jobId);
      if (job.status === 'completed') {
        const summary = job.summary_md || job.summary || job.result;
        if (summary) {
          showToast('Post summarized', 'ok');
          return { summary };
        }
        const cached = await fetchCachedSummary(postId, payload);
        if (cached && cached.summary) {
          showToast('Post summarized', 'ok');
          return cached;
        }
        throw new Error('Summarization completed but result unavailable');
      }
      if (job.status === 'failed') {
        throw new Error(job.error || 'Summarization job failed');
      }
      if (job.status === 'timeout') {
        throw new Error('Summarization is taking longer than expected');
      }
      if (job.status === 'not_found') {
        throw new Error('Summarization job not found');
      }
      throw new Error('Summarization job ended unexpectedly');
    }
    if (!response.ok) {
      throw new Error(await readError(response));
    }
    const data = await response.json();
    showToast('Post summarized', 'ok');
    return data;
  } catch (error) {
    showToast('Summarization failed: ' + error.message, 'err');
    return null;
  }
}

// AI output is untrusted text: escape it first, then turn newlines into <br>.
// (Inserting it unescaped let a translation or summary containing markup run
// script or break the page.)
function formatWithLineBreaks(text) {
  return String(text ?? '')
    .replace(/\r\n/g, '\n')
    .split('\n')
    .map(line => line.trim().length ? escapeHTML(line) : '')
    .map(line => (line ? line : '<br>'))
    .join('<br>');
}

function setButtonEnabled(btn, enabled) {
  if (!btn) return;
  btn.disabled = !enabled;
  btn.setAttribute('aria-disabled', enabled ? 'false' : 'true');
}

function extractPlainText(el) {
  if (!el) return '';
  const text = el.textContent || '';
  return text.trim();
}

// Function to bind translation and summarization actions to buttons
export function bindAIActions(container) {
  // Bind translate buttons
  container.querySelectorAll('button.translate[data-id]').forEach(btn => {
    btn.addEventListener('click', async () => {
      const postId = btn.getAttribute('data-id');
      setButtonLoading(btn, 'Translating…');
      let result = null;
      try {
        result = await translatePost(postId);
      } finally {
        resetButtonLoading(btn);
      }
      if (result && result.translated_text) {
        // Display translated text (this could be improved with a better UI)
        const postElement = container.querySelector(`article.post[data-id="${postId}"]`);
        if (postElement) {
          let translatedBlock = postElement.querySelector('.translated-text');
          if (!translatedBlock) {
            translatedBlock = document.createElement('div');
            translatedBlock.className = 'translated-text';
            translatedBlock.style.marginTop = '8px';
            postElement.appendChild(translatedBlock);
          }
          const withBreaks = formatWithLineBreaks(result.translated_text);
          translatedBlock.innerHTML = `<strong>Translated:</strong><br>${withBreaks}`;
        }
      }
    });
  });

  // Bind summarize buttons
  container.querySelectorAll('button.summarize[data-id]').forEach(btn => {
    btn.addEventListener('click', async () => {
      const postId = btn.getAttribute('data-id');
      setButtonLoading(btn, 'Summarizing…');
      let result = null;
      try {
        result = await summarizePost(postId);
      } finally {
        resetButtonLoading(btn);
      }
      if (result && result.summary) {
        // Display summary (this could be improved with a better UI)
        const postElement = container.querySelector(`article.post[data-id="${postId}"]`);
        if (postElement) {
          let summaryBlock = postElement.querySelector('.summary-text');
          if (!summaryBlock) {
            summaryBlock = document.createElement('div');
            summaryBlock.className = 'summary-text';
            summaryBlock.style.marginTop = '8px';
            postElement.appendChild(summaryBlock);
          }
          const formattedSummary = formatWithLineBreaks(result.summary);
          summaryBlock.innerHTML = `<h2>Summary</h2><div>${formattedSummary}</div>`;
        }
      }
    });
  });
}

// Bind single post page actions
export function bindPostPageAIActions(postId) {
  const translateBtn = document.getElementById('translate-post');
  const summarizeBtn = document.getElementById('summarize-post');
  const bodyEl = document.getElementById('body');
  const translationSection = document.getElementById('post-translation-section');
  const translationContent = document.getElementById('post-translation');
  const summarySection = document.getElementById('post-summary-section');
  const summaryContent = document.getElementById('post-summary');
  let lastTranslation = null;

  // Summarize works on the translation, so it stays disabled until one exists.
  // A disabled button gives no reason by itself, so show one next to it.
  let summarizeHint = null;
  if (summarizeBtn) {
    summarizeHint = document.createElement('span');
    summarizeHint.id = 'summarize-hint';
    summarizeHint.className = 'hint';
    summarizeHint.style.fontSize = '0.85rem';
    summarizeBtn.insertAdjacentElement('afterend', summarizeHint);
    summarizeBtn.setAttribute('aria-describedby', summarizeHint.id);
  }
  function updateSummarizeState(translating = false) {
    const enabled = !translating && !!lastTranslation;
    setButtonEnabled(summarizeBtn, enabled);
    if (!summarizeBtn || !summarizeHint) return;
    const reason = translating
      ? 'Available once the translation is ready.'
      : (enabled ? '' : 'Translate the post first, then summarize the translation.');
    summarizeHint.textContent = reason;
    summarizeHint.hidden = !reason;
    if (reason) summarizeBtn.title = reason; else summarizeBtn.removeAttribute('title');
  }

  const existingTranslation = extractPlainText(translationContent);
  if (existingTranslation) {
    lastTranslation = existingTranslation;
    if (translationSection) translationSection.style.display = 'block';
  }

  updateSummarizeState();

  if (translateBtn) {
    translateBtn.addEventListener('click', async () => {
      setButtonLoading(translateBtn, 'Translating…');
      updateSummarizeState(true);
      let result = null;
      try {
        result = await translatePost(postId);
      } finally {
        resetButtonLoading(translateBtn);
      }
      lastTranslation = result?.translated_text || null;
      if (result && result.translated_text) {
        const withBreaks = formatWithLineBreaks(result.translated_text);
        if (translationSection && translationContent) {
          translationContent.innerHTML = withBreaks;
          translationSection.style.display = 'block';
        } else if (bodyEl) {
          let translatedBlock = bodyEl.querySelector('.translated-text');
          if (!translatedBlock) {
            translatedBlock = document.createElement('div');
            translatedBlock.className = 'translated-text';
            translatedBlock.style.marginTop = '12px';
            bodyEl.appendChild(translatedBlock);
          }
          translatedBlock.innerHTML = `<h2>Translated</h2><div>${withBreaks}</div>`;
        }
      }
      if (!lastTranslation && existingTranslation) {
        lastTranslation = existingTranslation;
      }
      updateSummarizeState();
    });
  }

  if (summarizeBtn) {
    summarizeBtn.addEventListener('click', async () => {
      setButtonLoading(summarizeBtn, 'Summarizing…');
      let result = null;
      try {
        result = await summarizePost(postId, lastTranslation ? { source_text: lastTranslation } : {});
      } finally {
        resetButtonLoading(summarizeBtn);
      }
      if (result && result.summary) {
        const formattedSummary = formatWithLineBreaks(result.summary);
        if (summarySection && summaryContent) {
          summaryContent.innerHTML = formattedSummary;
          summarySection.style.display = 'block';
        } else if (bodyEl) {
          let summaryBlock = bodyEl.querySelector('.summary-text');
          if (!summaryBlock) {
            summaryBlock = document.createElement('div');
            summaryBlock.className = 'summary-text';
            summaryBlock.style.marginTop = '12px';
            bodyEl.appendChild(summaryBlock);
          }
          summaryBlock.innerHTML = `<h2>Summary</h2><div>${formattedSummary}</div>`;
        }
      }
    });
  }
}
