import json
import os
import time
import traceback
from dataclasses import asdict
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from rdflib import Graph

from p510_generate_synthetic import generar_grafo_p510
from run_queries_p510 import load_graph
from text2sparql import GenerationConfig, GenerationResult, generate_sparql


HTML = """<!doctype html>
<html lang=\"es\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>TFG · Text2SPARQL (offline)</title>
  <style>
    :root { --bg:#0b1020; --panel:#111a33; --text:#eaf0ff; --muted:#a9b3d1; --accent:#7aa2ff; --danger:#ff6b6b; }
    body { margin:0; font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial; background: var(--bg); color: var(--text); }
    .wrap { max-width: 1200px; margin: 0 auto; padding: 20px; }
    h1 { margin: 0 0 8px 0; font-size: 22px; }
    .sub { color: var(--muted); margin-bottom: 18px; }
    .grid { display:grid; grid-template-columns: 1fr 1fr; gap: 14px; }
    .card { background: var(--panel); border: 1px solid rgba(255,255,255,0.08); border-radius: 14px; padding: 14px; }
    label { display:block; font-size: 12px; color: var(--muted); margin: 10px 0 6px; }
    input, select, textarea { width:100%; box-sizing:border-box; border-radius: 10px; border: 1px solid rgba(255,255,255,0.12); background: rgba(0,0,0,0.15); color: var(--text); padding: 10px; }
    textarea { min-height: 120px; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
    button { border:0; background: linear-gradient(90deg, #7aa2ff, #9b8cff); color: #071024; font-weight: 700; padding: 10px 14px; border-radius: 10px; cursor:pointer; }
    button.secondary { background: transparent; border: 1px solid rgba(255,255,255,0.16); color: var(--text); font-weight: 600; }
    .row { display:flex; gap:10px; align-items:center; flex-wrap:wrap; }
    .status { font-size: 12px; color: var(--muted); }
    .error { color: var(--danger); white-space: pre-wrap; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
    pre { margin:0; white-space: pre-wrap; }
    table { width:100%; border-collapse: collapse; }
    th, td { text-align:left; padding: 8px; border-bottom: 1px solid rgba(255,255,255,0.10); font-size: 13px; }
    th { color: var(--muted); font-weight: 600; }
    code { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
    @media (max-width: 980px) { .grid { grid-template-columns: 1fr; } }
  </style>
</head>
<body>
  <div class=\"wrap\">
    <h1>Text2SPARQL offline — visual demo</h1>
    <div class=\"sub\">English question → SPARQL → execution over a local P510-like RDF graph</div>

    <div class=\"grid\">
      <div class=\"card\">
        <h3 style=\"margin:0 0 6px 0\">Question</h3>
        <label>Quick examples</label>
        <select id=\"examples\">
          <option value=\"requirements without end-to-end traceability\">requirements without end-to-end traceability</option>
          <option value=\"audit duplicate links\">audit duplicate links</option>
          <option value=\"physical models without tests\">physical models without tests</option>
          <option value=\"how many suppliers are there\">how many suppliers are there</option>
          <option value=\"used documents\">used documents</option>
        </select>

        <label>Question (NL)</label>
        <textarea id=\"question\" spellcheck=\"false\"></textarea>

        <label><input id=\"execute\" type=\"checkbox\" checked /> Execute on graph (otherwise translate only)</label>

        <div class=\"row\" style=\"margin-top:10px\">
          <button id=\"run\">Generate</button>
          <button class=\"secondary\" id=\"regen\">Regenerate graph</button>
          <span class=\"status\" id=\"status\"></span>
        </div>

        <div style=\"margin-top:10px\" class=\"status\">TTL: <code id=\"ttlLabel\"></code></div>
      </div>

      <div class=\"card\">
        <h3 style=\"margin:0 0 6px 0\">Settings</h3>
        <div class=\"row\">
          <div style=\"flex:1\">
            <label>LIMIT (if missing)</label>
            <input id=\"limit\" type=\"number\" value=\"200\" />
          </div>
          <div style=\"flex:1\">
            <label>Match threshold</label>
            <input id=\"threshold\" type=\"number\" step=\"0.01\" value=\"0.35\" />
          </div>
        </div>
        <label>Catalog JSONL (optional)</label>
        <input id=\"examplesPath\" value=\"eval/text2sparql_examples.jsonl\" />

        <label>Synonyms prompt file (optional)</label>
        <input id=\"synonymsFile\" value=\"prompts/system_en.txt\" />

        <label>Classifier model (optional)</label>
        <input id=\"classifierModel\" value=\"models/catalog_nb_v1.json\" />

        <label>Classifier min probability</label>
        <input id=\"classifierMinProb\" type=\"number\" step=\"0.01\" value=\"0.60\" />

        <label>Max rows</label>
        <input id=\"rows\" type=\"number\" value=\"200\" />

        <div class=\"status\" style=\"margin-top:10px\">
          Deterministic mode: no backend, no server.
        </div>
      </div>

      <div class=\"card\" style=\"grid-column: 1 / -1\">
        <h3 style=\"margin:0 0 6px 0\">Generated SPARQL</h3>
        <pre><code id=\"sparql\"></code></pre>
      </div>

      <div class=\"card\" style=\"grid-column: 1 / -1\">
        <h3 style=\"margin:0 0 6px 0\">Results</h3>
        <div id=\"error\" class=\"error\"></div>
        <details id=\"traceBox\" style=\"margin-top:10px; display:none\">
          <summary class=\"status\">Technical details (trace)</summary>
          <pre class=\"error\"><code id=\"trace\"></code></pre>
        </details>
        <div id=\"table\"></div>
      </div>

    </div>
  </div>

<script>
  const el = (id) => document.getElementById(id);
  const setStatus = (s) => { el('status').textContent = s; };

  function renderTable(obj) {
    const tableDiv = el('table');
    tableDiv.innerHTML = '';

    if (obj === null || obj === undefined) {
      tableDiv.innerHTML = `<div class="status">(translate-only)</div>`;
      return;
    }

    if (obj.askAnswer !== undefined) {
      tableDiv.innerHTML = `<div class="status">ASK: <b>${obj.askAnswer}</b></div>`;
      return;
    }

    const cols = obj.columns || [];
    const rows = obj.rows || [];

    if (!cols.length) {
      tableDiv.innerHTML = `<div class="status">(no columns)</div>`;
      return;
    }

    let html = '<table><thead><tr>';
    for (const c of cols) html += `<th>${c}</th>`;
    html += '</tr></thead><tbody>';

    if (!rows.length) {
      html += `<tr><td colspan="${cols.length}" class="status">(no results)</td></tr>`;
    } else {
      for (const r of rows) {
        html += '<tr>';
        for (const c of cols) html += `<td>${(r[c] ?? '')}</td>`;
        html += '</tr>';
      }
    }

    html += '</tbody></table>';
    tableDiv.innerHTML = html;
  }

  async function postJson(url, payload) {
    const resp = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
    const text = await resp.text();
    let data;
    try { data = JSON.parse(text); } catch { data = { error: 'Server returned non-JSON response', raw: text }; }
    if (!resp.ok) throw data;
    return data;
  }

  el('examples').addEventListener('change', () => {
    el('question').value = el('examples').value;
  });
  el('question').value = el('examples').value;

  async function refreshInfo() {
    try {
      const info = await (await fetch('/api/info')).json();
      el('ttlLabel').textContent = info.ttl_path;
    } catch {}
  }

  el('regen').addEventListener('click', async () => {
    el('error').textContent = '';
    setStatus('Regenerating graph...');
    try {
      const info = await postJson('/api/generate', {});
      setStatus(`Graph regenerated (${info.ttl_path})`);
    } catch (e) {
      el('error').textContent = e.error || JSON.stringify(e, null, 2);
      setStatus('Error');
    }
  });

  el('run').addEventListener('click', async () => {
    el('error').textContent = '';
    el('traceBox').style.display = 'none';
    el('trace').textContent = '';
    el('sparql').textContent = '';
    el('table').innerHTML = '';

    setStatus('Generating/running...');

    const payload = {
      question: el('question').value,
      execute: el('execute').checked,
      limit: Number(el('limit').value || 200),
      match_threshold: Number(el('threshold').value || 0.35),
      examples_path: el('examplesPath').value,
      synonyms_file: el('synonymsFile').value,
      classifier_model_file: el('classifierModel').value,
      classifier_min_prob: Number(el('classifierMinProb').value || 0.60),
      max_rows: Number(el('rows').value || 200),
    };

    try {
      const res = await postJson('/api/ask', payload);
      el('sparql').textContent = res.sparql;
      renderTable(res.result);
      const mode = (payload.execute ? 'run' : 'translate');
      const mid = (res.matched_id || 'catalog');
      const ms = (typeof res.match_score === 'number' ? res.match_score.toFixed(3) : 'n/a');
      setStatus(`OK (${mode}) · match=${mid} · score=${ms} · attempts=${res.attempts} · ${res.elapsed_s.toFixed(2)}s`);
    } catch (e) {
      el('error').textContent = e.error || JSON.stringify(e, null, 2);
      if (e.trace) {
        el('trace').textContent = e.trace;
        el('traceBox').style.display = 'block';
      }
      if (e.sparql) el('sparql').textContent = e.sparql;
      setStatus('Error');
    }
  });

  refreshInfo();
</script>
</body>
</html>
"""


class AppState:
    def __init__(self, ttl_path: str) -> None:
        self.ttl_path = ttl_path
        self._graph: Graph | None = None
        self._mtime: float = 0.0

    def ensure_graph(self) -> Graph:
        p = Path(self.ttl_path)
        if not p.exists():
            generar_grafo_p510(out_path=self.ttl_path)

        mtime = p.stat().st_mtime
        if self._graph is None or mtime != self._mtime:
            self._graph = load_graph(self.ttl_path)
            self._mtime = mtime
        return self._graph

    def regenerate(self) -> None:
        generar_grafo_p510(out_path=self.ttl_path)
        self._graph = None
        self._mtime = 0.0


def _query_result_to_json(qres: Any, max_rows: int) -> dict[str, Any]:
    if hasattr(qres, "askAnswer") and qres.askAnswer is not None:
        return {"askAnswer": bool(qres.askAnswer)}

    cols = [str(v) for v in getattr(qres, "vars", [])]
    out_rows: list[dict[str, str]] = []

    for i, row in enumerate(qres):
        if max_rows is not None and i >= max_rows:
            break
        values = list(row)
        d: dict[str, str] = {}
        for j, c in enumerate(cols):
            val = values[j] if j < len(values) else None
            d[c] = "" if val is None else str(val)
        out_rows.append(d)

    return {"columns": cols, "rows": out_rows}


class Handler(BaseHTTPRequestHandler):
    server_version = "Text2SPARQLDemo/1.0"

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, status: int, obj: dict[str, Any]) -> None:
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self._send(status, body, "application/json; charset=utf-8")

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/" or self.path.startswith("/?"):
            self._send(HTTPStatus.OK, HTML.encode("utf-8"), "text/html; charset=utf-8")
            return

        if self.path == "/api/info":
            state: AppState = self.server.state  # type: ignore[attr-defined]
            self._send_json(HTTPStatus.OK, {"ttl_path": state.ttl_path})
            return

        self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length) if length > 0 else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8")) if raw else {}
        except Exception:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "Invalid JSON"})
            return

        state: AppState = self.server.state  # type: ignore[attr-defined]

        if self.path == "/api/generate":
            try:
                state.regenerate()
                self._send_json(HTTPStatus.OK, {"ttl_path": state.ttl_path})
            except Exception as e:  # noqa: BLE001
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(e)})
            return

        if self.path != "/api/ask":
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})
            return

        question = str(payload.get("question") or "").strip()
        if not question:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "Missing 'question'"})
            return

        execute = bool(payload.get("execute") if payload.get("execute") is not None else True)
        limit = int(payload.get("limit") or 200)
        match_threshold = float(payload.get("match_threshold") or 0.35)
        examples_path = str(payload.get("examples_path") or "").strip() or None
        synonyms_file = str(payload.get("synonyms_file") or "").strip() or None
        classifier_model_file = str(payload.get("classifier_model_file") or "").strip() or None
        classifier_min_prob = float(payload.get("classifier_min_prob") or 0.20)
        max_rows = int(payload.get("max_rows") or 200)

        if examples_path and not Path(examples_path).exists():
            examples_path = None

        if synonyms_file and not Path(synonyms_file).exists():
          synonyms_file = None

        if classifier_model_file and not Path(classifier_model_file).exists():
          classifier_model_file = None

        start = time.perf_counter()
        try:
            g = state.ensure_graph()
            cfg = GenerationConfig(
                limit=limit,
                match_threshold=match_threshold,
                synonyms_file=synonyms_file,
                classifier_model_file=classifier_model_file,
                classifier_min_prob=classifier_min_prob,
            )

            result: GenerationResult = generate_sparql(g, question, config=cfg, examples_path=examples_path)
            qres = g.query(result.sparql) if execute else None
            elapsed = time.perf_counter() - start

            self._send_json(
                HTTPStatus.OK,
                {
                    **asdict(result),
                    "elapsed_s": elapsed,
                    "result": _query_result_to_json(qres, max_rows=max_rows) if qres is not None else None,
                },
            )
        except Exception as e:  # noqa: BLE001
            elapsed = time.perf_counter() - start
            # Try to preserve partial info when available
            err_obj: dict[str, Any] = {
                "error": str(e),
                "elapsed_s": elapsed,
                "trace": traceback.format_exc(limit=8),
            }
            self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, err_obj)


def main() -> None:
    ttl_path = os.environ.get("TEXT2SPARQL_TTL", os.path.join("data", "p510_sintetico.ttl"))
    host = os.environ.get("TEXT2SPARQL_DEMO_HOST", "127.0.0.1")
    port = int(os.environ.get("TEXT2SPARQL_DEMO_PORT", "8000"))

    httpd = ThreadingHTTPServer((host, port), Handler)
    httpd.state = AppState(ttl_path)  # type: ignore[attr-defined]

    print(f"Demo visual: http://{host}:{port}")
    print(f"TTL: {ttl_path}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
