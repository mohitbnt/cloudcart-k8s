import { API_BASE } from './config.js';

export async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  if (options.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json');

  const response = await fetch(`${API_BASE}${path}`, {
    credentials: 'include',
    ...options,
    headers,
  });

  let data = {};
  try { data = await response.json(); } catch (_) {}

  if (!response.ok) {
    throw new Error(data.detail || 'Request failed');
  }

  return data;
}
