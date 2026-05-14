const statusEl = document.querySelector('#status');

if (location.protocol === 'file:') {
  setStatus('ParkFinder must be opened from the local Python UI server, not directly as a file. Run `python3 -m parkfinder.server`, then open http://127.0.0.1:8000.', true);
} else {
  checkHealth();
}

async function checkHealth() {
  try {
    const response = await fetch('/api/health');
    const payload = await response.json();
    setStatus(payload.message || 'ParkFinder UI server is running.', false);
  } catch (error) {
    setStatus('Cannot reach the local ParkFinder UI server. Start it with `python3 -m parkfinder.server`, keep that terminal open, and browse to http://127.0.0.1:8000.', true);
  }
}

function setStatus(message, isError) {
  statusEl.hidden = false;
  statusEl.className = `status${isError ? ' error' : ''}`;
  statusEl.textContent = message;
}
