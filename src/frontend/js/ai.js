// ai.js - Functions for interacting with AI endpoints for translation and summarization

import { authHeaders, getToken } from './auth.js';
import { showToast } from './toast.js';

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
    if (!response.ok) {
      throw new Error(await response.text());
    }
    showToast('Post translated', 'ok');
    return await response.json();
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
    if (!response.ok) {
      throw new Error(await response.text());
    }
    showToast('Post summarized', 'ok');
    return await response.json();
  } catch (error) {
    showToast('Summarization failed: ' + error.message, 'err');
    return null;
  }
}

// Function to bind translation and summarization actions to buttons
export function bindAIActions(container) {
  // Bind translate buttons
  container.querySelectorAll('button.translate[data-id]').forEach(btn => {
    btn.addEventListener('click', async () => {
      const postId = btn.getAttribute('data-id');
      btn.disabled = true;
      const result = await translatePost(postId);
      btn.disabled = false;
      if (result && result.translated_text) {
        // Display translated text (this could be improved with a better UI)
        const postElement = container.querySelector(`article.post[data-id="${postId}"]`);
        if (postElement) {
          const p = postElement.querySelector('p');
          if (p) {
            p.innerHTML += `<br><strong>Translated:</strong> ${result.translated_text}`;
          }
        }
      }
    });
  });

  // Bind summarize buttons
  container.querySelectorAll('button.summarize[data-id]').forEach(btn => {
    btn.addEventListener('click', async () => {
      const postId = btn.getAttribute('data-id');
      btn.disabled = true;
      const result = await summarizePost(postId);
      btn.disabled = false;
      if (result && result.summary) {
        // Display summary (this could be improved with a better UI)
        const postElement = container.querySelector(`article.post[data-id="${postId}"]`);
        if (postElement) {
          const p = postElement.querySelector('p');
          if (p) {
            p.innerHTML += `<br><strong>Summary:</strong> ${result.summary}`;
          }
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
  let lastTranslation = null;

  if (translateBtn) {
    translateBtn.addEventListener('click', async () => {
      translateBtn.disabled = true;
      const result = await translatePost(postId);
      lastTranslation = result?.translated_text || null;
      translateBtn.disabled = false;
      if (result && result.translated_text && bodyEl) {
        const withBreaks = result.translated_text
          .replace(/\r\n/g, '\n')
          .split('\n')
          .map(line => line.trim().length ? line : '')
          .map(line => line ? line : '<br>')
          .join('<br>');
        bodyEl.innerHTML += `<br><strong>Translated:</strong><br>${withBreaks}`;
      }
    });
  }

  if (summarizeBtn) {
    summarizeBtn.addEventListener('click', async () => {
      summarizeBtn.disabled = true;
      const result = await summarizePost(postId, lastTranslation ? { source_text: lastTranslation } : {});
      summarizeBtn.disabled = false;
      if (result && result.summary && bodyEl) {
        bodyEl.innerHTML += `<br><br><strong>Summary:</strong> ${result.summary}`;
      }
    });
  }
}
