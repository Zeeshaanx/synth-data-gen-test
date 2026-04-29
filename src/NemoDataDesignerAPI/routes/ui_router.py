"""
UI Routes
  GET  /data_generation/v1/home   – Job submission frontend
  GET  /data_generation/v1/jobs/ui – Jobs history page (Postgres-backed)
  GET  /data_generation/v1/download/{job_id} – Stream CSV to browser
"""

import os
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
import db
from config import OUTPUT_DIR

router = APIRouter(prefix="/data_generation/v1")

# ─────────────────────────────────────────────────────────────────────────────
# Helper: stream a CSV file from disk
# ─────────────────────────────────────────────────────────────────────────────
@router.get("/download/{job_id}")
async def download_csv(job_id: str):
    filename = f"generated_{job_id}.csv"
    file_path = OUTPUT_DIR / filename
    if not file_path.exists():
        raise HTTPException(404, "CSV not found – file may have been cleaned up")

    def iterfile():
        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                yield chunk

    return StreamingResponse(
        iterfile(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ─────────────────────────────────────────────────────────────────────────────
# /home  – submission UI
# ─────────────────────────────────────────────────────────────────────────────
HOME_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>NeMo Data Designer</title>
<style>
  :root{--bg:#0f1117;--card:#1a1d27;--border:#2a2d3e;--accent:#7c3aed;--accent2:#06b6d4;
        --text:#e2e8f0;--muted:#64748b;--success:#10b981;--danger:#ef4444;--warn:#f59e0b;}
  *{box-sizing:border-box;margin:0;padding:0;}
  body{background:var(--bg);color:var(--text);font-family:'Inter',system-ui,sans-serif;min-height:100vh;}
  header{background:var(--card);border-bottom:1px solid var(--border);padding:1rem 2rem;
         display:flex;align-items:center;justify-content:space-between;}
  header h1{font-size:1.25rem;font-weight:700;background:linear-gradient(135deg,var(--accent),var(--accent2));
            -webkit-background-clip:text;-webkit-text-fill-color:transparent;}
  header a{color:var(--accent2);text-decoration:none;font-size:.9rem;border:1px solid var(--accent2);
           padding:.35rem .8rem;border-radius:.4rem;transition:all .2s;}
  header a:hover{background:var(--accent2);color:#000;}
  main{max-width:900px;margin:2rem auto;padding:0 1.5rem;}
  h2{font-size:1rem;font-weight:600;color:var(--muted);text-transform:uppercase;letter-spacing:.08em;margin-bottom:1rem;}
  .card{background:var(--card);border:1px solid var(--border);border-radius:.75rem;padding:1.5rem;margin-bottom:1.5rem;}
  label{display:block;font-size:.8rem;color:var(--muted);margin-bottom:.3rem;margin-top:.9rem;}
  label:first-child{margin-top:0;}
  input,select,textarea{width:100%;background:#0f1117;border:1px solid var(--border);color:var(--text);
    border-radius:.4rem;padding:.55rem .75rem;font-size:.875rem;outline:none;transition:border .2s;}
  input:focus,select:focus,textarea:focus{border-color:var(--accent);}
  textarea{resize:vertical;min-height:120px;font-family:'Fira Code','Cascadia Code',monospace;font-size:.8rem;}
  .row{display:grid;grid-template-columns:1fr 1fr;gap:1rem;}
  .row3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:1rem;}
  .btn{display:inline-flex;align-items:center;gap:.5rem;padding:.65rem 1.4rem;border:none;border-radius:.5rem;
       font-size:.9rem;font-weight:600;cursor:pointer;transition:all .2s;}
  .btn-primary{background:linear-gradient(135deg,var(--accent),#5b21b6);color:#fff;}
  .btn-primary:hover{opacity:.85;transform:translateY(-1px);}
  .btn-secondary{background:var(--border);color:var(--text);}
  .btn-secondary:hover{background:var(--muted);}
  .btn:disabled{opacity:.5;cursor:not-allowed;transform:none;}
  .actions{display:flex;gap:.75rem;margin-top:1.25rem;align-items:center;}
  #status-box{display:none;margin-top:1.25rem;padding:1rem;border-radius:.5rem;font-size:.85rem;
              border:1px solid var(--border);}
  #status-box.processing{border-color:var(--warn);background:#451a03;}
  #status-box.completed{border-color:var(--success);background:#022c22;}
  #status-box.failed{border-color:var(--danger);background:#450a0a;}
  .tag{display:inline-block;padding:.15rem .5rem;border-radius:.25rem;font-size:.7rem;font-weight:600;
       text-transform:uppercase;margin-right:.4rem;}
  .tag.processing{background:#451a03;color:var(--warn);}
  .tag.completed{background:#022c22;color:var(--success);}
  .tag.failed{background:#450a0a;color:var(--danger);}
  .hint{font-size:.75rem;color:var(--muted);margin-top:.25rem;}
  .col-entry{background:#0f1117;border:1px solid var(--border);border-radius:.5rem;
             padding:.75rem;margin-top:.5rem;position:relative;}
  .col-entry .remove-btn{position:absolute;top:.5rem;right:.5rem;background:none;border:none;
    color:var(--danger);cursor:pointer;font-size:.8rem;opacity:.6;}
  .col-entry .remove-btn:hover{opacity:1;}
  .section-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:.5rem;}
  .add-btn{background:none;border:1px dashed var(--border);color:var(--muted);border-radius:.4rem;
           padding:.35rem .75rem;font-size:.8rem;cursor:pointer;width:100%;margin-top:.5rem;transition:all .2s;}
  .add-btn:hover{border-color:var(--accent);color:var(--accent);}
  #job-id-display{font-family:monospace;font-size:.8rem;opacity:.7;margin-left:.5rem;}
</style>
</head>
<body>
<header>
  <h1>🧬 NeMo Data Designer</h1>
  <a href="/synth-data-gen/data_generation/v1/jobs/ui">📋 View All Jobs</a>
</header>
<main>

<div class="card">
  <h2>Model Configuration</h2>
  <div class="row">
    <div>
      <label>Model Provider</label>
      <select id="model_provider">
        <option value="nvidiabuild">NVIDIA Build</option>
        <option value="openai">OpenAI</option>
        <option value="anthropic">Anthropic</option>
        <option value="groq">Groq</option>
        <option value="google">Google</option>
        <option value="deepseek">DeepSeek</option>
        <option value="mistral">Mistral</option>
        <option value="microsoft">Microsoft Azure</option>
        <option value="custom">Custom</option>
      </select>
    </div>
    <div>
      <label>Model ID</label>
      <input id="model_id" type="text" placeholder="e.g. qwen/qwen2.5-coder-32b-instruct"/>
    </div>
  </div>
  <label>Provider API Key</label>
  <input id="provider_api_key" type="password" placeholder="nvapi-... or sk-..."/>
  <div id="azure-extra" style="display:none">
    <label>Base URL (Azure only)</label>
    <input id="provider_base_url" type="text" placeholder="https://your-resource.openai.azure.com"/>
    <label>API Version (Azure only)</label>
    <input id="provider_api_version" type="text" placeholder="2023-05-15"/>
  </div>
</div>

<div class="card">
  <h2>Job Settings</h2>
  <div class="row3">
    <div>
      <label>Number of Records</label>
      <input id="num_records" type="number" value="10" min="1" max="10000"/>
    </div>
    <div>
      <label>Temperature (0–2)</label>
      <input id="temperature" type="number" value="0.8" step="0.05" min="0" max="2"/>
    </div>
    <div>
      <label>Top P (0–1)</label>
      <input id="top_p" type="number" value="0.95" step="0.05" min="0" max="1"/>
    </div>
  </div>
  <label>Max Tokens</label>
  <input id="max_tokens" type="number" value="1024" min="64"/>
  <label style="margin-top:.9rem">Seed Data CSV <span style="color:var(--muted)">(optional)</span></label>
  <input id="seed_data" type="file" accept=".csv"/>
  <p class="hint">Upload a CSV file to use existing rows as seed data for new column generation.</p>
</div>

<!-- Sampler Columns -->
<div class="card">
  <div class="section-header">
    <h2>Sampler Columns</h2>
  </div>
  <p class="hint">Generate random values from statistical distributions or predefined categories.</p>
  <div id="sampler-list"></div>
  <button class="add-btn" onclick="addSampler()">+ Add Sampler Column</button>
</div>

<!-- Expression Columns -->
<div class="card">
  <h2>Expression Columns</h2>
  <p class="hint">Derive column values from other columns using Jinja2 expressions.</p>
  <div id="expr-list"></div>
  <button class="add-btn" onclick="addExpr()">+ Add Expression Column</button>
</div>

<!-- LLM Text Columns -->
<div class="card">
  <h2>LLM Text Columns</h2>
  <p class="hint">Generate freeform text using the LLM. Reference other columns with <code>{{ "{{" }} column_name {{ "}}" }}</code>.</p>
  <div id="llmtext-list"></div>
  <button class="add-btn" onclick="addLLMText()">+ Add LLM Text Column</button>
</div>

<!-- LLM Structured Columns -->
<div class="card">
  <h2>LLM Structured Columns</h2>
  <p class="hint">Generate JSON-schema–validated structured output from the LLM.</p>
  <div id="llmstruct-list"></div>
  <button class="add-btn" onclick="addLLMStruct()">+ Add LLM Structured Column</button>
</div>

<!-- LLM Judge Columns -->
<div class="card">
  <h2>LLM Judge Columns</h2>
  <p class="hint">Have the LLM evaluate and score previously generated columns.</p>
  <div id="llmjudge-list"></div>
  <button class="add-btn" onclick="addLLMJudge()">+ Add LLM Judge Column</button>
</div>

<div class="actions">
  <button class="btn btn-secondary" onclick="submitJob('preview')">👁 Preview (fast, ≤100 rows)</button>
  <button class="btn btn-primary" onclick="submitJob('create')">🚀 Create Full Dataset</button>
  <span id="job-id-display"></span>
</div>

<div id="status-box"></div>

</main>

<script>
// ── DOM helpers ─────────────────────────────────────────────────────────────
function el(id){ return document.getElementById(id); }
function v(id){ return el(id).value.trim(); }

// ── Azure extra fields ───────────────────────────────────────────────────────
el('model_provider').addEventListener('change', function(){
  el('azure-extra').style.display = this.value === 'microsoft' ? 'block' : 'none';
});

// ── Sampler columns ──────────────────────────────────────────────────────────
const SAMPLER_TYPES = ["category","gaussian","uniform","bernoulli","poisson","uuid",
  "datetime","person","person_from_faker","binomial","bernoulli_mixture","scipy",
  "subcategory","timedelta"];

function addSampler(){
  const id = Date.now();
  const div = document.createElement('div');
  div.className = 'col-entry'; div.id = 'samp-'+id;
  div.innerHTML = `
    <button class="remove-btn" onclick="this.parentElement.remove()">✕</button>
    <div class="row">
      <div><label>Column Name</label><input placeholder="e.g. topic" id="sn-${id}"/></div>
      <div><label>Sampler Type</label><select id="st-${id}">
        ${SAMPLER_TYPES.map(t=>`<option value="${t}">${t}</option>`).join('')}
      </select></div>
    </div>
    <label>Params (JSON) <span style="color:var(--muted)">– e.g. {"values":["A","B"],"weights":[0.6,0.4]}</span></label>
    <textarea id="sp-${id}" rows="2" placeholder='{"values": ["Option A", "Option B"]}'></textarea>`;
  el('sampler-list').appendChild(div);
}

function getSamplers(){
  const cols = [];
  document.querySelectorAll('[id^="sn-"]').forEach(inp=>{
    const id = inp.id.replace('sn-','');
    const name = inp.value.trim();
    const type = el('st-'+id).value;
    const paramStr = el('sp-'+id).value.trim();
    if(!name) return;
    const col = {name, sampler_type: type};
    if(paramStr){ try{ col.params = JSON.parse(paramStr); }catch(e){ alert('Invalid JSON in sampler params for: '+name); throw e; } }
    cols.push(col);
  });
  return cols;
}

// ── Expression columns ───────────────────────────────────────────────────────
function addExpr(){
  const id = Date.now();
  const div = document.createElement('div');
  div.className = 'col-entry'; div.id = 'expr-'+id;
  div.innerHTML = `
    <button class="remove-btn" onclick="this.parentElement.remove()">✕</button>
    <div class="row">
      <div><label>Column Name</label><input placeholder="e.g. full_name" id="en-${id}"/></div>
      <div><label>Expression</label><input placeholder="{{ first_name }} {{ last_name }}" id="ee-${id}"/></div>
    </div>`;
  el('expr-list').appendChild(div);
}

function getExprs(){
  const cols = [];
  document.querySelectorAll('[id^="en-"]').forEach(inp=>{
    const id = inp.id.replace('en-','');
    const name = inp.value.trim(); const expr = el('ee-'+id).value.trim();
    if(name && expr) cols.push({name, expr});
  });
  return cols;
}

// ── LLM Text columns ──────────────────────────────────────────────────────────
function addLLMText(){
  const id = Date.now();
  const div = document.createElement('div');
  div.className = 'col-entry'; div.id = 'lt-'+id;
  div.innerHTML = `
    <button class="remove-btn" onclick="this.parentElement.remove()">✕</button>
    <label>Column Name</label><input id="ltn-${id}" placeholder="e.g. generated_content"/>
    <label>Prompt</label><textarea id="ltp-${id}" placeholder="Write a {{ content_format }} about {{ topic }} for {{ target_audience }}."></textarea>
    <label>System Prompt <span style="color:var(--muted)">(optional)</span></label>
    <input id="lts-${id}" placeholder="You are a helpful assistant..."/>`;
  el('llmtext-list').appendChild(div);
}

function getLLMText(){
  const cols = [];
  document.querySelectorAll('[id^="ltn-"]').forEach(inp=>{
    const id = inp.id.replace('ltn-','');
    const name = inp.value.trim(); const prompt = el('ltp-'+id).value.trim();
    const sys = el('lts-'+id).value.trim();
    if(!name || !prompt) return;
    const col = {name, prompt};
    if(sys) col.system_prompt = sys;
    cols.push(col);
  });
  return cols;
}

// ── LLM Structured columns ───────────────────────────────────────────────────
function addLLMStruct(){
  const id = Date.now();
  const div = document.createElement('div');
  div.className = 'col-entry'; div.id = 'ls-'+id;
  const exSchema = JSON.stringify({type:"object",properties:{sentiment:{type:"string",enum:["Positive","Negative","Neutral"]},score:{type:"integer"}},required:["sentiment","score"]},null,2);
  div.innerHTML = `
    <button class="remove-btn" onclick="this.parentElement.remove()">✕</button>
    <label>Column Name</label><input id="lsn-${id}" placeholder="e.g. content_metadata"/>
    <label>Prompt</label><textarea id="lsp-${id}" rows="2" placeholder="Analyze the content for {{ topic }}."></textarea>
    <label>Output Format (JSON Schema)</label>
    <textarea id="lsf-${id}" rows="5">${exSchema}</textarea>`;
  el('llmstruct-list').appendChild(div);
}

function getLLMStruct(){
  const cols = [];
  document.querySelectorAll('[id^="lsn-"]').forEach(inp=>{
    const id = inp.id.replace('lsn-','');
    const name = inp.value.trim(); const prompt = el('lsp-'+id).value.trim();
    const fmtStr = el('lsf-'+id).value.trim();
    if(!name || !prompt) return;
    let fmt;
    try{ fmt = JSON.parse(fmtStr); }catch(e){ alert('Invalid JSON schema for structured column: '+name); throw e; }
    cols.push({name, prompt, output_format: fmt});
  });
  return cols;
}

// ── LLM Judge columns ────────────────────────────────────────────────────────
function addLLMJudge(){
  const id = Date.now();
  const div = document.createElement('div');
  div.className = 'col-entry'; div.id = 'lj-'+id;
  const exOpts = JSON.stringify({"High":"Perfect match","Medium":"Somewhat related","Low":"Off-topic"});
  div.innerHTML = `
    <button class="remove-btn" onclick="this.parentElement.remove()">✕</button>
    <label>Column Name</label><input id="ljn-${id}" placeholder="e.g. content_quality_score"/>
    <label>Prompt</label><textarea id="ljp-${id}" rows="2" placeholder="Evaluate this content: {{ generated_content }}"></textarea>
    <label>Score Name</label><input id="ljsn-${id}" placeholder="e.g. relevance"/>
    <label>Score Description</label><input id="ljsd-${id}" placeholder="Does the content match the topic?"/>
    <label>Options (JSON) – key=label, value=description</label>
    <textarea id="ljso-${id}" rows="2">${exOpts}</textarea>`;
  el('llmjudge-list').appendChild(div);
}

function getLLMJudge(){
  const cols = [];
  document.querySelectorAll('[id^="ljn-"]').forEach(inp=>{
    const id = inp.id.replace('ljn-','');
    const name = inp.value.trim(); const prompt = el('ljp-'+id).value.trim();
    const sname = el('ljsn-'+id).value.trim(); const sdesc = el('ljsd-'+id).value.trim();
    const optsStr = el('ljso-'+id).value.trim();
    if(!name || !prompt) return;
    let opts;
    try{ opts = JSON.parse(optsStr); }catch(e){ alert('Invalid JSON options for judge column: '+name); throw e; }
    cols.push({name, prompt, scores:[{name:sname, description:sdesc, options:opts}]});
  });
  return cols;
}

// ── Submit ────────────────────────────────────────────────────────────────────
async function submitJob(mode){
  const payload = {
    model_provider: v('model_provider'),
    model_id: v('model_id'),
    provider_api_key: v('provider_api_key'),
    num_records: parseInt(v('num_records')) || 10,
    temperature: parseFloat(v('temperature')) || 0.8,
    top_p: parseFloat(v('top_p')) || 0.95,
    max_tokens: parseInt(v('max_tokens')) || 1024,
  };
  if(v('provider_base_url')) payload.provider_base_url = v('provider_base_url');
  if(v('provider_api_version')) payload.provider_api_version = v('provider_api_version');

  const samplers = getSamplers(); if(samplers.length) payload.sampler_columns = samplers;
  const exprs = getExprs(); if(exprs.length) payload.expression_columns = exprs;
  const llmtext = getLLMText(); if(llmtext.length) payload.llm_text_columns = llmtext;
  const llmstruct = getLLMStruct(); if(llmstruct.length) payload.llm_structured_columns = llmstruct;
  const llmjudge = getLLMJudge(); if(llmjudge.length) payload.llm_judge_columns = llmjudge;

  if(!payload.model_id || !payload.provider_api_key){
    alert('Model ID and API Key are required.'); return;
  }

  const fd = new FormData();
  fd.append('generate_request', JSON.stringify(payload));
  const seedFile = el('seed_data').files[0];
  if(seedFile) fd.append('seed_data', seedFile);

  const endpoint = `/synth-data-gen/data_generation/v1/${mode}`;
  showStatus('processing', `Submitting ${mode} job...`);

  try {
    const resp = await fetch(endpoint, {method:'POST', body: fd});
    if(!resp.ok){ const t = await resp.text(); showStatus('failed','Submit failed: '+t); return; }
    const data = await resp.json();
    const jobId = data.job_id;
    el('job-id-display').textContent = 'Job: '+jobId;
    showStatus('processing', `Job submitted! ID: ${jobId} — polling status...`);
    pollJob(jobId, mode);
  } catch(e){ showStatus('failed', 'Network error: '+e.message); }
}

async function pollJob(jobId, mode){
  const start = Date.now();
  while(true){
    await sleep(4000);
    try{
      const resp = await fetch(`/synth-data-gen/data_generation/v1/jobs/${jobId}`);
      const job = await resp.json();
      const elapsed = Math.round((Date.now()-start)/1000);
      if(job.status === 'completed'){
        const res = job.result || {};
        const dlLink = mode === 'create'
          ? `<br/><a href="/synth-data-gen/data_generation/v1/download/${jobId}" 
               style="color:#06b6d4;text-decoration:none;font-weight:600;margin-top:.5rem;display:inline-block">
               ⬇ Download CSV</a>` : '';
        showStatus('completed',
          `✅ Completed in ${elapsed}s — ${res.num_records || '?'} records generated (${res.duration_seconds || '?'}s NeMo time)${dlLink}`);
        return;
      } else if(job.status === 'failed'){
        showStatus('failed', `❌ Failed: ${job.error || 'Unknown error'}`);
        return;
      } else {
        showStatus('processing', `Status: ${job.status.toUpperCase()} (${elapsed}s elapsed)...`);
      }
    } catch(e){ showStatus('failed','Polling error: '+e.message); return; }
  }
}

function showStatus(type, msg){
  const box = el('status-box');
  box.style.display = 'block';
  box.className = type;
  box.innerHTML = msg;
}
function sleep(ms){ return new Promise(r=>setTimeout(r,ms)); }
</script>
</body>
</html>"""


# ─────────────────────────────────────────────────────────────────────────────
# /jobs/ui  – jobs history page (reads from PostgreSQL)
# ─────────────────────────────────────────────────────────────────────────────
@router.get("/home", response_class=HTMLResponse)
async def home_page():
    return HTMLResponse(content=HOME_HTML)


@router.get("/jobs/ui", response_class=HTMLResponse)
async def jobs_ui_page():
    jobs = await db.list_jobs(limit=200)

    rows_html = ""
    if not jobs:
        rows_html = '<tr><td colspan="8" style="text-align:center;color:var(--muted);padding:2rem">No jobs found. <a href="/synth-data-gen/data_generation/v1/home" style="color:var(--accent2)">Submit one →</a></td></tr>'
    else:
        for j in jobs:
            status = j.get("status", "unknown")
            tag_cls = {"completed": "completed", "failed": "failed", "processing": "processing"}.get(status, "processing")
            created = j.get("created_at")
            created_str = created.strftime("%Y-%m-%d %H:%M:%S UTC") if created else "—"
            updated = j.get("updated_at")
            updated_str = updated.strftime("%H:%M:%S") if updated else "—"
            csv_filename = j.get("csv_filename") or ""
            job_id = j.get("job_id", "")
            download_cell = ""
            if status == "completed" and csv_filename and csv_filename != "":
                download_cell = f'<a href="/synth-data-gen/data_generation/v1/download/{job_id}" style="color:var(--accent2);text-decoration:none;font-weight:600">⬇ CSV</a>'
            elif status == "failed":
                err = (j.get("error_message") or "")[:80]
                download_cell = f'<span style="color:var(--danger);font-size:.75rem" title="{err}">Error ↗</span>'

            duration = j.get("duration_seconds") or "—"
            rows_html += f"""
            <tr>
              <td><code style="font-size:.75rem;color:var(--accent2)">{job_id[:18]}…</code></td>
              <td><span class="tag {tag_cls}">{status}</span></td>
              <td>{j.get('job_type','—')}</td>
              <td>{j.get('model_provider','—')}</td>
              <td style="font-size:.8rem;max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{j.get('model_id','—')}</td>
              <td style="text-align:center">{j.get('num_records','—')}</td>
              <td style="font-size:.8rem">{created_str}</td>
              <td style="text-align:center">{download_cell}</td>
            </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Jobs — NeMo Data Designer</title>
<style>
  :root{{--bg:#0f1117;--card:#1a1d27;--border:#2a2d3e;--accent:#7c3aed;--accent2:#06b6d4;
        --text:#e2e8f0;--muted:#64748b;--success:#10b981;--danger:#ef4444;--warn:#f59e0b;}}
  *{{box-sizing:border-box;margin:0;padding:0;}}
  body{{background:var(--bg);color:var(--text);font-family:'Inter',system-ui,sans-serif;min-height:100vh;}}
  header{{background:var(--card);border-bottom:1px solid var(--border);padding:1rem 2rem;
          display:flex;align-items:center;justify-content:space-between;}}
  header h1{{font-size:1.25rem;font-weight:700;background:linear-gradient(135deg,var(--accent),var(--accent2));
             -webkit-background-clip:text;-webkit-text-fill-color:transparent;}}
  header a{{color:var(--accent2);text-decoration:none;font-size:.9rem;border:1px solid var(--accent2);
            padding:.35rem .8rem;border-radius:.4rem;transition:all .2s;}}
  header a:hover{{background:var(--accent2);color:#000;}}
  main{{max-width:1200px;margin:2rem auto;padding:0 1.5rem;}}
  .stats{{display:grid;grid-template-columns:repeat(4,1fr);gap:1rem;margin-bottom:1.5rem;}}
  .stat-card{{background:var(--card);border:1px solid var(--border);border-radius:.75rem;padding:1rem 1.25rem;}}
  .stat-card .num{{font-size:1.75rem;font-weight:700;}}
  .stat-card .lbl{{font-size:.75rem;color:var(--muted);text-transform:uppercase;letter-spacing:.05em;}}
  .num.green{{color:var(--success);}} .num.red{{color:var(--danger);}} .num.yellow{{color:var(--warn);}}
  .card{{background:var(--card);border:1px solid var(--border);border-radius:.75rem;overflow:hidden;}}
  table{{width:100%;border-collapse:collapse;}}
  th{{background:#12141e;padding:.75rem 1rem;text-align:left;font-size:.75rem;color:var(--muted);
      text-transform:uppercase;letter-spacing:.06em;border-bottom:1px solid var(--border);}}
  td{{padding:.75rem 1rem;border-bottom:1px solid var(--border);font-size:.85rem;vertical-align:middle;}}
  tr:last-child td{{border-bottom:none;}}
  tr:hover td{{background:#1e2130;}}
  .tag{{display:inline-block;padding:.15rem .5rem;border-radius:.25rem;font-size:.7rem;font-weight:600;text-transform:uppercase;}}
  .tag.processing{{background:#451a03;color:var(--warn);}}
  .tag.completed{{background:#022c22;color:var(--success);}}
  .tag.failed{{background:#450a0a;color:var(--danger);}}
  .refresh-btn{{background:var(--card);border:1px solid var(--border);color:var(--text);
                padding:.4rem .9rem;border-radius:.4rem;cursor:pointer;font-size:.85rem;}}
  .refresh-btn:hover{{border-color:var(--accent2);color:var(--accent2);}}
</style>
</head>
<body>
<header>
  <h1>📋 Job History</h1>
  <a href="/synth-data-gen/data_generation/v1/home">+ New Job</a>
</header>
<main>

<div class="stats">
  <div class="stat-card"><div class="num">{len(jobs)}</div><div class="lbl">Total Jobs</div></div>
  <div class="stat-card"><div class="num green">{sum(1 for j in jobs if j.get('status')=='completed')}</div><div class="lbl">Completed</div></div>
  <div class="stat-card"><div class="num red">{sum(1 for j in jobs if j.get('status')=='failed')}</div><div class="lbl">Failed</div></div>
  <div class="stat-card"><div class="num yellow">{sum(1 for j in jobs if j.get('status')=='processing')}</div><div class="lbl">Running</div></div>
</div>

<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:.75rem">
  <span style="color:var(--muted);font-size:.85rem">Showing last {len(jobs)} jobs — newest first — sourced from PostgreSQL</span>
  <button class="refresh-btn" onclick="location.reload()">↻ Refresh</button>
</div>

<div class="card">
<table>
  <thead>
    <tr>
      <th>Job ID</th><th>Status</th><th>Type</th><th>Provider</th>
      <th>Model</th><th style="text-align:center">Records</th>
      <th>Created (UTC)</th><th style="text-align:center">Download</th>
    </tr>
  </thead>
  <tbody>
    {rows_html}
  </tbody>
</table>
</div>

<p style="color:var(--muted);font-size:.75rem;margin-top:1rem;text-align:center">
  Auto-refresh every 15s while jobs are running
</p>
</main>
<script>
// Auto-refresh if any job is processing
const hasRunning = {str(any(j.get('status') in ('processing','pending') for j in jobs)).lower()};
if(hasRunning) setTimeout(()=>location.reload(), 15000);
</script>
</body>
</html>"""
    return HTMLResponse(content=html)
