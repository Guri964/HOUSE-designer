// IntelliTwin API service — identical endpoints and payloads to the original frontend.
(function () {
  const KEY = 'intellitwin-api-base';
  const PATHS = {
    parse: '/api/parse', generate: '/api/generate', validate: '/api/validate', cost: '/api/cost',
    health: '/api/health', modelStatus: '/api/model/status', rates: '/api/rates'
  };
  const base = () => (localStorage.getItem(KEY) || '').replace(/\/$/, '');
  const url = p => base() + p;

  async function readJson(r) {
    const t = await r.text();
    try { return t ? JSON.parse(t) : {}; }
    catch { throw new Error(`Backend returned a non-JSON response (HTTP ${r.status}).`); }
  }
  const post = (p, body) => fetch(url(p), { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });

  window.IntelliAPI = {
    PATHS,
    getBase: base,
    setBase: v => localStorage.setItem(KEY, (v || '').trim().replace(/\/$/, '')),
    async parse(text) { const j = await readJson(await post(PATHS.parse, { text })); return j.parsed || null; },
    async generate(payload) {
      const r = await post(PATHS.generate, payload); const d = await readJson(r);
      if (!r.ok) throw new Error(d.error || d.detail || 'Generation failed');
      return d;
    },
    async modelStatus() { const r = await fetch(url(PATHS.modelStatus)); if (!r.ok) throw new Error('HTTP ' + r.status); return readJson(r); },
    async rates() { const r = await fetch(url(PATHS.rates)); if (!r.ok) throw new Error('HTTP ' + r.status); return readJson(r); },
    async health() { const r = await fetch(url(PATHS.health)); return readJson(r); }
  };
})();
