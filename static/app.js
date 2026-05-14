const form = document.querySelector('#search-form');
const statusEl = document.querySelector('#status');
const summaryEl = document.querySelector('#summary');
const resultsEl = document.querySelector('#results');
const presetsEl = document.querySelector('#presets');

const thisYear = new Date().getFullYear();
document.querySelector('#startDate').value = `${thisYear}-06-01`;
document.querySelector('#endDate').value = `${thisYear}-09-30`;

if (location.protocol === 'file:') {
  setStatus('ParkFinder must be opened from the local Python server, not directly as a file. Run `python3 -m parkfinder.server`, then open http://127.0.0.1:8000.', true);
} else {
  loadPresets();
}

async function apiFetch(path, options) {
  try {
    const response = await fetch(path, options);
    return response;
  } catch (error) {
    throw new Error(`Cannot reach the ParkFinder server at ${location.origin}. If the browser shows net::ERR_CONNECTION_REFUSED, start the server with \`python3 -m parkfinder.server\`, keep that terminal window open, and browse to http://127.0.0.1:8000 instead of opening static/index.html directly.`);
  }
}

async function loadPresets() {
  try {
    const response = await apiFetch('/api/presets');
    const presets = await response.json();
    presetsEl.innerHTML = presets.map(preset => `
      <label class="chip" title="${escapeHtml(preset.source || '')}">
        <input type="checkbox" name="preset" value="${escapeHtml(preset.id)}" />
        ${escapeHtml(preset.name)}
      </label>
    `).join('') || '<p class="hint">No presets configured. Use the all-parks scan or paste official result URLs above.</p>';
  } catch (error) {
    presetsEl.innerHTML = '<p class="hint">Could not load presets because the local server is unreachable.</p>';
    setStatus(error.message, true);
  }
}

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  const scanMode = new FormData(form).get('scanMode');
  setStatus(scanMode === 'all'
    ? 'Scanning every Ontario Parks campground for every Friday–Sunday weekend. This can take several minutes...'
    : 'Scanning selected parks and weekends...', false);
  resultsEl.innerHTML = '';
  summaryEl.hidden = true;
  const data = Object.fromEntries(new FormData(form).entries());
  data.waterFirst = document.querySelector('#waterFirst').checked;
  data.presetIds = [...document.querySelectorAll('input[name="preset"]:checked')].map(input => input.value);
  try {
    const response = await apiFetch('/api/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    const payload = await response.json();
    if (!response.ok || payload.error) throw new Error(payload.error || 'Search failed');
    render(payload);
  } catch (error) {
    setStatus(error.message, true);
  }
});

function render(payload) {
  const count = payload.results.length;
  setStatus(`Search complete: ${count} available campsite${count === 1 ? '' : 's'} found.`, false);
  summaryEl.hidden = false;
  summaryEl.innerHTML = `<strong>${payload.weekends.length}</strong> Friday–Sunday weekends checked in <strong>${escapeHtml(payload.mode)}</strong> mode: ${payload.weekends.map(w => `${w.start} → ${w.end}`).join(', ')}`;
  resultsEl.innerHTML = payload.results.map(result => `
    <article class="card">
      <div>
        <h3>${escapeHtml(result.park)} · Site ${escapeHtml(result.site_name)}</h3>
        <div class="meta">${escapeHtml(result.weekend_start)} → ${escapeHtml(result.weekend_end)} · resource ${escapeHtml(result.resource_id)}</div>
      </div>
      <div class="badges">
        <span class="badge water">Water score ${result.water_score}</span>
        ${result.water_reasons.map(reason => `<span class="badge">${escapeHtml(reason)}</span>`).join('')}
      </div>
      <a class="official" href="${escapeHtml(result.booking_url)}" target="_blank" rel="noreferrer">Book/check official page</a>
      <dl class="attrs">
        ${Object.entries(result.attributes).slice(0, 28).map(([key, value]) => `<div><dt>${escapeHtml(key)}</dt><dd>${escapeHtml(Array.isArray(value) ? value.join(' › ') : value)}</dd></div>`).join('')}
      </dl>
    </article>
  `).join('') || '<p class="hint">No matching available sites were returned. Try disabling the water-only filter or checking official availability.</p>';
}

function setStatus(message, isError) {
  statusEl.hidden = false;
  statusEl.className = `status${isError ? ' error' : ''}`;
  statusEl.textContent = message;
}

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>'"]/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[char]));
}
