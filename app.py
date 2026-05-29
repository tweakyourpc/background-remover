#!/usr/bin/env python3
from __future__ import annotations

import base64
import io
import json
import os
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, jsonify, request, send_file, url_for
from PIL import Image, ImageOps
from rembg import new_session, remove
from werkzeug.utils import secure_filename

APP_NAME = "Background Remover"
APP_VERSION = "0.3.0"
DEFAULT_MODEL = os.getenv("BACKGROUND_REMOVER_MODEL", "u2net")
MAX_CONTENT_LENGTH = 16 * 1024 * 1024
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "bmp", "tif", "tiff"}
JOB_LIMIT = 50
UPLOAD_TTL_SECONDS = 3600
EDGE_PRESETS = {
    "balanced": (30, 30),
    "soft": (45, 45),
    "crisp": (18, 18),
}

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
UPLOAD_DIR = ROOT / "uploads"
OUTPUT_DIR = ROOT / "outputs"
INDEX_FILE = DATA_DIR / "jobs.json"

STARTED_AT = datetime.now(timezone.utc)
_session_lock = threading.Lock()
_rembg_session = None
_jobs_lock = threading.Lock()
_job_cache: list[dict] = []

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def isoformat(ts: datetime | None = None) -> str:
    return (ts or utc_now()).isoformat().replace("+00:00", "Z")


def ensure_dirs() -> None:
    for path in (DATA_DIR, UPLOAD_DIR, OUTPUT_DIR):
        path.mkdir(parents=True, exist_ok=True)


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def load_jobs() -> list[dict]:
    if not INDEX_FILE.exists():
        return []
    try:
        data = json.loads(INDEX_FILE.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data[:JOB_LIMIT]
    except json.JSONDecodeError:
        pass
    return []


def save_jobs(jobs: list[dict]) -> None:
    INDEX_FILE.write_text(json.dumps(jobs[:JOB_LIMIT], indent=2) + "\n", encoding="utf-8")


def get_jobs() -> list[dict]:
    with _jobs_lock:
        return list(_job_cache)


def record_job(job: dict) -> None:
    with _jobs_lock:
        _job_cache.insert(0, job)
        del _job_cache[JOB_LIMIT:]
        save_jobs(_job_cache)


def cleanup_uploads() -> None:
    cutoff = utc_now().timestamp() - UPLOAD_TTL_SECONDS
    for path in UPLOAD_DIR.glob("*"):
        try:
            if path.is_file() and path.stat().st_mtime < cutoff:
                path.unlink()
        except OSError:
            continue


def resolve_edge_sizes(preset: str) -> tuple[int, int]:
    return EDGE_PRESETS.get(preset, EDGE_PRESETS["balanced"])


def get_session():
    global _rembg_session
    with _session_lock:
        if _rembg_session is None:
            _rembg_session = new_session(DEFAULT_MODEL)
        return _rembg_session


def file_to_data_url(image_path: Path) -> str:
    data = image_path.read_bytes()
    return "data:image/png;base64," + base64.b64encode(data).decode("utf-8")


def process_upload(file_storage, alpha_matting: bool, return_mask: bool, edge_preset: str):
    filename = secure_filename(file_storage.filename or "upload")
    source_ext = Path(filename).suffix.lower() or ".png"
    job_id = uuid.uuid4().hex
    fg_size, bg_size = resolve_edge_sizes(edge_preset)

    raw = file_storage.read()
    input_path = UPLOAD_DIR / f"{job_id}-{Path(filename).stem}{source_ext}"
    input_path.write_bytes(raw)

    try:
        input_image = Image.open(io.BytesIO(raw))
        input_image = ImageOps.exif_transpose(input_image).convert("RGBA")

        session = get_session()
        output_image = remove(
            input_image,
            session=session,
            alpha_matting=alpha_matting,
            alpha_matting_foreground_size=fg_size,
            alpha_matting_background_size=bg_size,
        )

        if return_mask:
            output_image = output_image.split()[-1]

        output_path = OUTPUT_DIR / f"{job_id}.png"
        output_image.save(output_path, format="PNG")

        return {
            "job_id": job_id,
            "input_path": input_path,
            "output_path": output_path,
            "filename": filename,
            "started_at": utc_now(),
            "edge_preset": edge_preset,
        }
    finally:
        try:
            input_path.unlink(missing_ok=True)
        except OSError:
            pass


HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Background Remover</title>
<style>
:root {
  --bg: #f5f7fb;
  --surface: #ffffff;
  --surface-2: #f8fafc;
  --surface-3: #eef4f8;
  --border: #dbe3eb;
  --text: #17212b;
  --muted: #5d6b7a;
  --primary: #117c6f;
  --primary-2: #2f8fd6;
  --accent: #a855f7;
  --danger: #c2410c;
  --shadow: 0 18px 45px rgba(23, 33, 43, 0.10);
}
* { box-sizing: border-box; }
body {
  margin: 0;
  min-height: 100vh;
  color: var(--text);
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  background:
    linear-gradient(135deg, rgba(17, 124, 111, 0.08), transparent 34%),
    linear-gradient(225deg, rgba(47, 143, 214, 0.08), transparent 36%),
    var(--bg);
}
button, select, input { font: inherit; }
.shell {
  width: min(1180px, calc(100% - 32px));
  margin: 0 auto;
  padding: 26px 0 42px;
}
.topbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  margin-bottom: 20px;
}
.brand {
  display: flex;
  align-items: center;
  gap: 12px;
  font-weight: 800;
  letter-spacing: 0;
}
.mark {
  width: 38px;
  height: 38px;
  display: grid;
  place-items: center;
  border-radius: 8px;
  color: #fff;
  background: linear-gradient(135deg, var(--primary), var(--primary-2));
  box-shadow: 0 12px 26px rgba(17, 124, 111, 0.22);
}
.service-pill {
  color: var(--muted);
  border: 1px solid var(--border);
  border-radius: 999px;
  padding: 7px 11px;
  background: rgba(255, 255, 255, 0.74);
  font-size: 0.86rem;
}
.hero {
  display: grid;
  grid-template-columns: minmax(0, 0.95fr) minmax(340px, 1.05fr);
  align-items: end;
  gap: 24px;
  margin-bottom: 18px;
}
.hero-copy {
  padding: 10px 0 8px;
}
.eyebrow {
  color: var(--primary);
  font-size: 0.78rem;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}
h1 {
  margin: 9px 0 12px;
  font-size: clamp(2.35rem, 6vw, 4.7rem);
  line-height: 0.96;
  letter-spacing: 0;
}
.subtitle {
  max-width: 62ch;
  color: var(--muted);
  font-size: 1.02rem;
  line-height: 1.65;
}
.hero-metrics {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 18px;
}
.metric {
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 9px 11px;
  background: rgba(255, 255, 255, 0.76);
  color: var(--muted);
  font-size: 0.88rem;
}
.workbench {
  border: 1px solid var(--border);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.78);
  box-shadow: var(--shadow);
  overflow: hidden;
}
.workbench-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  padding: 11px 12px;
  border-bottom: 1px solid var(--border);
  background: var(--surface-2);
}
.dots { display: flex; gap: 6px; }
.dots span {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: #cbd5df;
}
.dots span:nth-child(1) { background: #ef7b72; }
.dots span:nth-child(2) { background: #f1bd52; }
.dots span:nth-child(3) { background: #57bf78; }
.workbench-title {
  color: var(--muted);
  font-size: 0.82rem;
  font-weight: 700;
}
.workbench-body {
  display: grid;
  grid-template-columns: 0.86fr 1.14fr;
  gap: 14px;
  padding: 14px;
}
.tool-panel {
  display: grid;
  align-content: start;
  gap: 12px;
}
.dropzone {
  min-height: 168px;
  display: grid;
  place-items: center;
  gap: 8px;
  padding: 20px;
  border: 1px dashed #9eb2c4;
  border-radius: 8px;
  background: linear-gradient(180deg, #fff, #f7fbfb);
  text-align: center;
  cursor: pointer;
  transition: border-color .18s ease, box-shadow .18s ease, transform .18s ease;
}
.dropzone.dragover {
  border-color: var(--primary);
  box-shadow: 0 0 0 4px rgba(17, 124, 111, 0.12);
  transform: translateY(-1px);
}
.dropzone input { display: none; }
.upload-icon {
  width: 46px;
  height: 46px;
  display: grid;
  place-items: center;
  border-radius: 8px;
  background: #e9f7f4;
  color: var(--primary);
}
.drop-title { font-size: 1rem; font-weight: 800; }
.drop-copy { color: var(--muted); font-size: 0.9rem; line-height: 1.45; }
.controls { display: grid; gap: 12px; }
.field, .toggle { display: grid; gap: 7px; }
.field label, .toggle-label {
  color: var(--text);
  font-size: 0.86rem;
  font-weight: 750;
}
.field select {
  width: 100%;
  min-height: 42px;
  padding: 9px 10px;
  border-radius: 8px;
  border: 1px solid var(--border);
  color: var(--text);
  background: #fff;
}
.field-note, .toggle-help, .footer-note {
  color: var(--muted);
  font-size: 0.82rem;
  line-height: 1.45;
}
.toggles { display: grid; gap: 8px; }
.toggle {
  grid-template-columns: auto 1fr;
  align-items: start;
  padding: 11px;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: var(--surface-2);
}
.toggle input { accent-color: var(--primary); margin-top: 3px; }
.toggle span { display: grid; gap: 4px; }
.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.btn {
  min-height: 42px;
  border: 0;
  border-radius: 8px;
  padding: 10px 14px;
  font-weight: 800;
  cursor: pointer;
  transition: transform .15s ease, opacity .15s ease, box-shadow .15s ease, background .15s ease;
}
.btn:hover { transform: translateY(-1px); }
.btn.primary {
  background: linear-gradient(135deg, var(--primary), var(--primary-2));
  color: #fff;
  box-shadow: 0 12px 24px rgba(17, 124, 111, 0.20);
}
.btn.ghost {
  background: #fff;
  color: var(--text);
  border: 1px solid var(--border);
}
.btn.info {
  background: #17212b;
  color: #fff;
}
.btn:disabled { opacity: .52; cursor: not-allowed; transform: none; box-shadow: none; }
.preview-stack {
  display: grid;
  grid-template-rows: auto 1fr;
  gap: 10px;
}
.preview-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  color: var(--muted);
  font-size: 0.84rem;
}
.preview-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  min-height: 420px;
}
.preview-box {
  display: grid;
  grid-template-rows: auto 1fr;
  min-width: 0;
  overflow: hidden;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: #fff;
}
.preview-box header {
  display: flex;
  justify-content: space-between;
  padding: 10px 11px;
  border-bottom: 1px solid var(--border);
  color: var(--muted);
  font-size: 0.78rem;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}
.canvas-wrap {
  min-height: 360px;
  display: grid;
  place-items: center;
  background:
    linear-gradient(45deg, #d9e2ea 25%, transparent 25%),
    linear-gradient(-45deg, #d9e2ea 25%, transparent 25%),
    linear-gradient(45deg, transparent 75%, #d9e2ea 75%),
    linear-gradient(-45deg, transparent 75%, #d9e2ea 75%);
  background-color: #f8fbfd;
  background-size: 24px 24px;
  background-position: 0 0, 0 12px, 12px -12px, -12px 0;
}
.canvas-wrap img {
  width: 100%;
  max-height: 460px;
  object-fit: contain;
  display: block;
}
.empty-state {
  padding: 18px;
  color: var(--muted);
  text-align: center;
  font-size: 0.9rem;
}
.loading {
  display: none;
  align-items: center;
  gap: 10px;
  color: var(--muted);
  font-size: 0.9rem;
}
.loading.show { display: flex; }
.spinner {
  width: 17px;
  height: 17px;
  border-radius: 50%;
  border: 2px solid #cbd5df;
  border-top-color: var(--primary);
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
@media (max-width: 960px) {
  .hero, .workbench-body, .preview-row { grid-template-columns: 1fr; }
  .preview-row { min-height: 0; }
}
@media (max-width: 640px) {
  .shell { width: min(100% - 20px, 1180px); padding-top: 18px; }
  .topbar { align-items: flex-start; flex-direction: column; }
  .workbench-body { padding: 10px; }
  .actions .btn { flex: 1 1 100%; }
  h1 { font-size: 2.35rem; }
}
</style>
</head>
<body>
<div class="shell">
  <header class="topbar">
    <div class="brand">
      <div class="mark" aria-hidden="true">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M4 7.5C4 5.57 5.57 4 7.5 4H13v2H7.5C6.67 6 6 6.67 6 7.5V13H4V7.5Z" fill="currentColor"/>
          <path d="M18 11h2v5.5c0 1.93-1.57 3.5-3.5 3.5H11v-2h5.5c.83 0 1.5-.67 1.5-1.5V11Z" fill="currentColor"/>
          <path d="M8 15.25 15.25 8 16.7 9.45 9.45 16.7H8v-1.45Z" fill="currentColor"/>
        </svg>
      </div>
      <span>Background Remover</span>
    </div>
    <div class="service-pill" id="servicePill">Local utility</div>
  </header>

  <section class="hero">
    <div class="hero-copy">
      <div class="eyebrow">Local image cleanup</div>
      <h1>Remove backgrounds without leaving your machine.</h1>
      <p class="subtitle">
        Drop in an image, choose an edge mode, and export a clean transparent PNG. The app runs locally and uses rembg with ONNX Runtime under the hood.
      </p>
      <div class="hero-metrics">
        <span class="metric">PNG, JPG, WebP, BMP, TIFF</span>
        <span class="metric">Alpha matting</span>
        <span class="metric">Mask export</span>
      </div>
    </div>

    <main class="workbench" aria-label="Background removal tool">
      <div class="workbench-header">
        <div class="dots" aria-hidden="true"><span></span><span></span><span></span></div>
        <div class="workbench-title">Ready</div>
      </div>
      <div class="workbench-body">
        <section class="tool-panel">
          <div class="dropzone" id="dropzone" onclick="document.getElementById('fileInput').click()">
            <div class="upload-icon" aria-hidden="true">
              <svg width="25" height="25" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M12 3 7.75 7.25l1.42 1.41L11 6.83V16h2V6.83l1.83 1.83 1.42-1.41L12 3Z" fill="currentColor"/>
                <path d="M5 14h2v3h10v-3h2v3.5c0 .83-.67 1.5-1.5 1.5h-11c-.83 0-1.5-.67-1.5-1.5V14Z" fill="currentColor"/>
              </svg>
            </div>
            <div>
              <div class="drop-title">Drop an image here</div>
              <div class="drop-copy">or click to browse. Files up to 16 MB are accepted.</div>
            </div>
            <input type="file" id="fileInput" accept="image/*">
          </div>

          <div class="controls">
            <div class="toggles">
              <label class="toggle">
                <input type="checkbox" id="alphaMatting" checked>
                <span>
                  <span class="toggle-label">Alpha matting</span>
                  <span class="toggle-help">Refines hair, fabric, and soft edges.</span>
                </span>
              </label>
              <label class="toggle">
                <input type="checkbox" id="returnMask">
                <span>
                  <span class="toggle-label">Return mask only</span>
                  <span class="toggle-help">Exports the matte instead of the cutout.</span>
                </span>
              </label>
            </div>
            <div class="field">
              <label for="edgePreset">Edge mode</label>
              <select id="edgePreset">
                <option value="balanced" selected>Balanced</option>
                <option value="soft">Soft edges</option>
                <option value="crisp">Crisp edges</option>
              </select>
              <div class="field-note">Balanced is a good default for most product shots and portraits.</div>
            </div>
            <div class="actions">
              <button class="btn primary" id="removeBtn" onclick="removeBackground()" disabled>Remove background</button>
              <button class="btn ghost" onclick="resetForm()">New image</button>
              <button class="btn info" id="downloadBtn" style="display:none" onclick="downloadResult()">Download PNG</button>
            </div>
            <div class="loading" id="loading"><div class="spinner"></div><span>Removing background...</span></div>
            <div class="footer-note" id="jobNote">No image selected yet.</div>
          </div>
        </section>

        <section class="preview-stack" aria-label="Image preview">
          <div class="preview-toolbar">
            <span>Before and after</span>
            <span id="previewStatus">Waiting for image</span>
          </div>
          <div class="preview-row">
            <div class="preview-box">
              <header><span>Original</span></header>
              <div class="canvas-wrap">
                <img id="originalPreview" alt="Original preview" style="display:none;">
                <div class="empty-state" id="originalEmpty">Original preview appears here.</div>
              </div>
            </div>
            <div class="preview-box">
              <header><span>Result</span></header>
              <div class="canvas-wrap">
                <img id="resultPreview" alt="Result preview" style="display:none;">
                <div class="empty-state" id="resultEmpty">Transparent PNG result appears here.</div>
              </div>
            </div>
          </div>
        </section>
      </div>
    </main>
  </section>
</div>

<script>
let currentFile = null;
let resultData = null;
let currentJob = null;

const dropzone = document.getElementById('dropzone');
const fileInput = document.getElementById('fileInput');
const removeBtn = document.getElementById('removeBtn');

dropzone.addEventListener('dragover', e => { e.preventDefault(); dropzone.classList.add('dragover'); });
dropzone.addEventListener('dragleave', () => dropzone.classList.remove('dragover'));
dropzone.addEventListener('drop', e => {
  e.preventDefault();
  dropzone.classList.remove('dragover');
  if (e.dataTransfer.files[0]) handleFile(e.dataTransfer.files[0]);
});

fileInput.addEventListener('change', e => {
  if (e.target.files[0]) handleFile(e.target.files[0]);
});

async function bootstrap() {}

function handleFile(file) {
  if (!file.type.startsWith('image/')) {
    alert('Please select an image file.');
    return;
  }
  currentFile = file;
  removeBtn.disabled = false;
  const reader = new FileReader();
  reader.onload = e => {
    const image = document.getElementById('originalPreview');
    image.src = e.target.result;
    image.style.display = 'block';
    document.getElementById('resultPreview').style.display = 'none';
    document.getElementById('originalEmpty').style.display = 'none';
    document.getElementById('resultEmpty').style.display = 'block';
    document.getElementById('previewStatus').textContent = 'Image loaded';
    document.getElementById('downloadBtn').style.display = 'none';
    document.getElementById('jobNote').textContent = `Loaded ${file.name}.`;
    document.querySelector('.workbench-title').textContent = 'Image loaded';
  };
  reader.readAsDataURL(file);
}

async function removeBackground() {
  if (!currentFile) return;
  const loading = document.getElementById('loading');
  loading.classList.add('show');
  removeBtn.disabled = true;

  const formData = new FormData();
  formData.append('file', currentFile);
  formData.append('alpha_matting', document.getElementById('alphaMatting').checked ? 'true' : 'false');
  formData.append('return_mask', document.getElementById('returnMask').checked ? 'true' : 'false');
  formData.append('edge_preset', document.getElementById('edgePreset').value || 'balanced');

  try {
    const response = await fetch('/remove', { method: 'POST', body: formData });
    const data = await response.json();
    if (!response.ok || data.error) {
      throw new Error(data.error || response.statusText);
    }
    resultData = data.image;
    currentJob = data.job;
    const result = document.getElementById('resultPreview');
    result.src = 'data:image/png;base64,' + data.image;
    result.style.display = 'block';
    document.getElementById('downloadBtn').style.display = 'inline-flex';
    document.getElementById('resultEmpty').style.display = 'none';
    document.getElementById('previewStatus').textContent = 'Result ready';
    document.querySelector('.workbench-title').textContent = 'Result ready';
    const presetLabel = document.getElementById('edgePreset').selectedOptions[0].textContent;
    document.getElementById('jobNote').textContent = `Done with ${presetLabel}. Download the PNG or try another image.`;
  } catch (error) {
    alert('Upload failed: ' + error.message);
  } finally {
    loading.classList.remove('show');
    removeBtn.disabled = false;
  }
}

function downloadResult() {
  if (!currentJob) return;
  window.location.href = currentJob.download_url;
}

function resetForm() {
  currentFile = null;
  resultData = null;
  currentJob = null;
  removeBtn.disabled = true;
  document.getElementById('downloadBtn').style.display = 'none';
  document.getElementById('originalPreview').style.display = 'none';
  document.getElementById('resultPreview').style.display = 'none';
  document.getElementById('jobNote').textContent = 'No image selected yet.';
  document.getElementById('originalEmpty').style.display = 'block';
  document.getElementById('resultEmpty').style.display = 'block';
  document.getElementById('previewStatus').textContent = 'Waiting for image';
  document.querySelector('.workbench-title').textContent = 'Ready';
  fileInput.value = '';
  document.getElementById('edgePreset').value = 'balanced';
  document.getElementById('alphaMatting').checked = true;
  document.getElementById('returnMask').checked = false;
}

bootstrap();
</script>
</body>
</html>
"""


@app.route("/")
def index():
    return HTML


@app.route("/health")
def health():
    jobs = get_jobs()
    with _session_lock:
        model_loaded = _rembg_session is not None
    return jsonify(
        {
            "service": APP_NAME,
            "version": APP_VERSION,
            "status": "ok",
            "model": DEFAULT_MODEL,
            "model_status": "loaded" if model_loaded else "not_loaded",
            "jobs": len(jobs),
            "started_at": isoformat(STARTED_AT),
            "uptime_seconds": int((utc_now() - STARTED_AT).total_seconds()),
        }
    )


@app.route("/whoami")
def whoami():
    return jsonify(
        {
            "service": APP_NAME,
            "version": APP_VERSION,
            "pid": os.getpid(),
            "startedAt": isoformat(STARTED_AT),
            "host": os.getenv("HOST", "0.0.0.0"),
            "port": int(os.getenv("PORT", "5050")),
            "model": DEFAULT_MODEL,
        }
    )


@app.route("/api/jobs")
def api_jobs():
    jobs = []
    for job in get_jobs():
        jobs.append(
            {
                "job_id": job["job_id"],
                "filename": job["filename"],
                "created_at": job["created_at"],
                "duration_ms": job["duration_ms"],
                "alpha_matting": job["alpha_matting"],
                "return_mask": job["return_mask"],
                "status": job["status"],
                "download_url": url_for("download_job", job_id=job["job_id"], _external=False),
                "job_url": url_for("job_detail", job_id=job["job_id"], _external=False),
            }
        )
    return jsonify({"jobs": jobs})


@app.route("/jobs/<job_id>")
def job_detail(job_id: str):
    for job in get_jobs():
        if job["job_id"] == job_id:
            payload = dict(job)
            payload["download_url"] = url_for("download_job", job_id=job_id, _external=False)
            return jsonify(payload)
    return jsonify({"error": "job not found"}), 404


@app.route("/download/<job_id>")
def download_job(job_id: str):
    for job in get_jobs():
        if job["job_id"] == job_id:
            return send_file(job["output_path"], mimetype="image/png", as_attachment=True, download_name=f"{job_id}.png")
    return jsonify({"error": "job not found"}), 404


@app.route("/remove", methods=["POST"])
def remove_background():
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "No file selected"}), 400
    if not allowed_file(file.filename):
        return jsonify({"error": "Unsupported file type"}), 400

    alpha_matting = request.form.get("alpha_matting", "true").lower() == "true"
    return_mask = request.form.get("return_mask", "false").lower() == "true"
    edge_preset = request.form.get("edge_preset", "balanced")

    started = time.perf_counter()
    try:
        result = process_upload(file, alpha_matting, return_mask, edge_preset)
        output_data = result["output_path"].read_bytes()
        job = {
            "job_id": result["job_id"],
            "filename": result["filename"],
            "created_at": isoformat(result["started_at"]),
            "duration_ms": int((time.perf_counter() - started) * 1000),
            "alpha_matting": alpha_matting,
            "return_mask": return_mask,
            "edge_preset": edge_preset,
            "status": "ok",
            "input_path": str(result["input_path"]),
            "output_path": str(result["output_path"]),
            "download_url": url_for("download_job", job_id=result["job_id"], _external=False),
            "job_url": url_for("job_detail", job_id=result["job_id"], _external=False),
        }
        record_job(job)
        return jsonify(
            {
                "success": True,
                "image": base64.b64encode(output_data).decode("utf-8"),
                "job": job,
            }
        )
    except Exception as exc:
        try:
            uploaded = UPLOAD_DIR / secure_filename(file.filename or "")
            if uploaded.exists():
                uploaded.unlink()
        except OSError:
            pass
        failed_job = {
            "job_id": uuid.uuid4().hex,
            "filename": secure_filename(file.filename),
            "created_at": isoformat(),
            "duration_ms": int((time.perf_counter() - started) * 1000),
            "alpha_matting": alpha_matting,
            "return_mask": return_mask,
            "status": "error",
            "error": str(exc),
        }
        record_job(failed_job)
        return jsonify({"error": str(exc)}), 500


def main() -> None:
    ensure_dirs()
    cleanup_uploads()
    _job_cache[:] = load_jobs()
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "5050"))
    app.run(host=host, port=port, debug=False)


if __name__ == "__main__":
    main()
