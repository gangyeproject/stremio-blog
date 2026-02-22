#!/usr/bin/env python3
"""Editor - 本地 Markdown 编辑器 + 一键发布到 Strapi (Addon / Article)"""

import http.server
import json
import uuid
import re
import requests as req_lib
from io import BytesIO

import boto3
from botocore.config import Config
from PIL import Image

# ============ 配置 ============
# Cloudflare R2
CLOUDFLARE_ACCOUNT_ID = "a25ecbe5ae9398766a250c772cd1ce62"
R2_ACCESS_KEY_ID = "428a5cd44b7d1261852666684f013036"
R2_SECRET_ACCESS_KEY = "7db3f9a42de74c0fe03d13ce19a7cb1d0693ce6badc6abfbc08d8fe3f508fbdd"
R2_BUCKET_NAME = "stremio-blog"
R2_CUSTOM_DOMAIN = "img.stremioaddonmanager.org"
R2_ENDPOINT = f"https://{CLOUDFLARE_ACCOUNT_ID}.r2.cloudflarestorage.com"

# Strapi
STRAPI_URL = "https://admin.stremioaddonmanager.org"
STRAPI_API_TOKEN = "db479c1008822e2d09f3a303833c24cf1539a0da6f034d41613cccb3371c605fa19f997530c66f4c17b642b18d30c9e7cfd425baca62c5cceb560c65c653abe160827cc172b3fd7b3a18e9e48adc91d6f37ef82235875a60f92ff640e3052925c67f1d644337b4444edef0bb7a786bd980717ae35f04e5461a2345c7e22f39cf"

# 服务器
PORT = 8899

# ============ R2 客户端 ============
s3_client = boto3.client(
    's3',
    endpoint_url=R2_ENDPOINT,
    aws_access_key_id=R2_ACCESS_KEY_ID,
    aws_secret_access_key=R2_SECRET_ACCESS_KEY,
    config=Config(signature_version='s3v4'),
    region_name='auto'
)

# ============ HTML 页面 ============
HTML_PAGE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Stremio Editor</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/easymde/dist/easymde.min.css">
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #1a1a2e; color: #e0e0e0; padding: 20px; }
.container { max-width: 960px; margin: 0 auto; }
h1 { text-align: center; margin-bottom: 16px; color: #7c83ff; font-size: 1.6rem; }
.mode-switch { display: flex; justify-content: center; gap: 0; margin-bottom: 20px; }
.mode-btn { padding: 8px 28px; border: 2px solid #7c83ff; background: transparent; color: #7c83ff; cursor: pointer; font-size: 0.95rem; font-weight: 600; transition: all 0.2s; }
.mode-btn:first-child { border-radius: 6px 0 0 6px; }
.mode-btn:last-child { border-radius: 0 6px 6px 0; }
.mode-btn.active { background: #7c83ff; color: #fff; }
.form-row { display: flex; gap: 12px; margin-bottom: 12px; }
.form-group { flex: 1; }
.form-group label { display: block; margin-bottom: 4px; font-size: 0.85rem; color: #aaa; }
.form-group input, .form-group textarea { width: 100%; padding: 8px 12px; background: #16213e; border: 1px solid #333; border-radius: 6px; color: #e0e0e0; font-size: 0.95rem; }
.form-group input:focus, .form-group textarea:focus { outline: none; border-color: #7c83ff; }
.manifest-row { display: flex; gap: 8px; align-items: flex-end; }
.manifest-row .form-group { flex: 1; }
.btn { padding: 8px 16px; border: none; border-radius: 6px; cursor: pointer; font-size: 0.9rem; font-weight: 500; }
.btn-fetch { background: #2d6a4f; color: #fff; }
.btn-fetch:hover { background: #40916c; }
.btn-publish { background: #7c83ff; color: #fff; padding: 12px 32px; font-size: 1rem; width: 100%; margin-top: 16px; }
.btn-publish:hover { background: #6a71e0; }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.editor-wrap { margin: 12px 0; }
.tags { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 4px; }
.tag { background: #2d6a4f; color: #fff; padding: 2px 10px; border-radius: 12px; font-size: 0.8rem; }
.toast { position: fixed; top: 20px; right: 20px; padding: 12px 20px; border-radius: 8px; color: #fff; font-size: 0.9rem; z-index: 999; display: none; }
.toast.success { background: #2d6a4f; }
.toast.error { background: #c0392b; }
.toast.info { background: #2c3e80; }
.cover-preview { margin-top: 6px; }
.cover-preview img { max-height: 80px; border-radius: 4px; border: 1px solid #333; }
.addon-only { display: none; }
.EasyMDEContainer .CodeMirror { background: #16213e; color: #e0e0e0; border-color: #333; min-height: 300px; }
.EasyMDEContainer .editor-toolbar { background: #16213e; border-color: #333; }
.EasyMDEContainer .editor-toolbar button { color: #aaa !important; }
.EasyMDEContainer .editor-toolbar button:hover { background: #333; }
.EasyMDEContainer .editor-preview { background: #1a1a2e; color: #e0e0e0; }
</style>
</head>
<body>
<div class="container">
  <h1>Stremio Editor</h1>
<!-- PLACEHOLDER_BODY -->

  <div class="mode-switch">
    <button class="mode-btn active" onclick="switchMode('addon')">Addon</button>
    <button class="mode-btn" onclick="switchMode('article')">Article</button>
  </div>

  <div class="form-row">
    <div class="form-group">
      <label>Title</label>
      <input type="text" id="title" placeholder="标题" oninput="autoSlug()">
    </div>
    <div class="form-group">
      <label id="slugLabel">Sulg (URL)</label>
      <input type="text" id="slugField" placeholder="auto-generated-from-title">
    </div>
  </div>

  <div class="form-group" style="margin-bottom:12px">
    <label>Summary</label>
    <input type="text" id="summary" placeholder="简短描述">
  </div>

  <div class="form-group" style="margin-bottom:12px">
    <label>Cover (自动提取文章中第一张上传图片)</label>
    <input type="text" id="cover" placeholder="自动填充或手动输入图片URL">
    <div class="cover-preview" id="coverPreview"></div>
  </div>

  <div class="addon-only" id="addonFields">
    <div class="manifest-row" style="margin-bottom:12px">
      <div class="form-group">
        <label>Manifest URL</label>
        <input type="text" id="manifestUrl" placeholder="https://xxx/manifest.json">
      </div>
      <button class="btn btn-fetch" onclick="fetchManifest()">获取</button>
    </div>
    <div class="form-row">
      <div class="form-group">
        <label>Description (from manifest)</label>
        <textarea id="description" rows="2" placeholder="自动获取或手动填写"></textarea>
      </div>
      <div class="form-group">
        <label>Types (from manifest)</label>
        <div id="typesDisplay" class="tags" style="min-height:30px"></div>
        <input type="hidden" id="types" value="[]">
      </div>
    </div>
  </div>

  <div class="editor-wrap">
    <label style="display:block;margin-bottom:4px;font-size:0.85rem;color:#aaa">Content (Markdown - 可直接粘贴图片)</label>
    <textarea id="content"></textarea>
  </div>

  <button class="btn btn-publish" id="publishBtn" onclick="publish()">发布 Addon 到 Strapi</button>
</div>

<div class="toast" id="toast"></div>

<!-- PLACEHOLDER_SCRIPTS -->
<script src="https://cdn.jsdelivr.net/npm/easymde/dist/easymde.min.js"></script>
<script>
let currentMode = 'addon';
const r2Domain = '__R2_DOMAIN__';

function switchMode(mode) {
  currentMode = mode;
  document.querySelectorAll('.mode-btn').forEach((b, i) => {
    b.classList.toggle('active', (i === 0 && mode === 'addon') || (i === 1 && mode === 'article'));
  });
  document.getElementById('addonFields').style.display = mode === 'addon' ? 'block' : 'none';
  document.getElementById('slugLabel').textContent = mode === 'addon' ? 'Sulg (URL)' : 'Slug (URL)';
  document.getElementById('publishBtn').textContent = mode === 'addon' ? '发布 Addon 到 Strapi' : '发布 Article 到 Strapi';
}

const easyMDE = new EasyMDE({
  element: document.getElementById('content'),
  spellChecker: false,
  autosave: { enabled: false },
  placeholder: '在这里写内容...\n可以直接粘贴图片，会自动上传到 R2',
  toolbar: ['bold','italic','heading','|','quote','unordered-list','ordered-list','|','link','image','|','preview','side-by-side','fullscreen','|','guide'],
  status: false
});

// 粘贴图片
easyMDE.codemirror.on('paste', async function(cm, e) {
  const items = e.clipboardData?.items;
  if (!items) return;
  for (const item of items) {
    if (item.type.startsWith('image/')) {
      e.preventDefault();
      await uploadImage(item.getAsFile(), cm);
      return;
    }
  }
});

// 拖拽图片
easyMDE.codemirror.on('drop', async function(cm, e) {
  const files = e.dataTransfer?.files;
  if (!files || files.length === 0) return;
  for (const file of files) {
    if (file.type.startsWith('image/')) {
      e.preventDefault();
      await uploadImage(file, cm);
    }
  }
});

async function uploadImage(file, cm) {
  showToast('上传图片中...', 'info');
  try {
    const arrayBuf = await file.arrayBuffer();
    const res = await fetch('/upload-image', {
      method: 'POST',
      headers: { 'Content-Type': file.type },
      body: arrayBuf
    });
    const data = await res.json();
    if (data.url) {
      const cursor = cm.getCursor();
      cm.replaceRange('![image](' + data.url + ')\n', cursor);
      showToast('图片上传成功', 'success');
      autoFillCover();
    } else {
      showToast('上传失败: ' + (data.error || '未知错误'), 'error');
    }
  } catch (err) {
    showToast('上传失败: ' + err.message, 'error');
  }
}

function autoFillCover() {
  const coverInput = document.getElementById('cover');
  if (coverInput.value) return;
  const md = easyMDE.value();
  const match = md.match(/!\[.*?\]\((https:\/\/[^\s)]+)\)/);
  if (match) {
    coverInput.value = match[1];
    updateCoverPreview(match[1]);
  }
}

function updateCoverPreview(url) {
  const el = document.getElementById('coverPreview');
  el.innerHTML = url ? '<img src="' + url + '" alt="cover">' : '';
}

document.getElementById('cover').addEventListener('input', function() {
  updateCoverPreview(this.value);
});

function autoSlug() {
  const title = document.getElementById('title').value;
  const slug = title.toLowerCase().replace(/[^a-z0-9\u4e00-\u9fa5]+/g, '-').replace(/^-|-$/g, '');
  document.getElementById('slugField').value = slug;
}

async function fetchManifest() {
  const url = document.getElementById('manifestUrl').value.trim();
  if (!url) { showToast('请输入 Manifest URL', 'error'); return; }
  showToast('获取 Manifest...', 'info');
  try {
    const res = await fetch('/fetch-manifest', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url })
    });
    const data = await res.json();
    if (data.error) { showToast(data.error, 'error'); return; }
    if (data.description) document.getElementById('description').value = data.description;
    if (data.name && !document.getElementById('title').value) {
      document.getElementById('title').value = data.name;
      autoSlug();
    }
    if (data.types) {
      document.getElementById('types').value = JSON.stringify(data.types);
      document.getElementById('typesDisplay').innerHTML = data.types.map(t => '<span class="tag">' + t + '</span>').join('');
    }
    showToast('Manifest 获取成功', 'success');
  } catch (err) {
    showToast('获取失败: ' + err.message, 'error');
  }
}

async function publish() {
  const btn = document.getElementById('publishBtn');
  const title = document.getElementById('title').value.trim();
  const slug = document.getElementById('slugField').value.trim();
  const content = easyMDE.value().trim();
  if (!title) { showToast('请填写 Title', 'error'); return; }
  if (!slug) { showToast('请填写 Slug', 'error'); return; }
  if (!content) { showToast('请填写内容', 'error'); return; }

  autoFillCover();
  const cover = document.getElementById('cover').value.trim();

  btn.disabled = true;
  btn.textContent = '发布中...';
  showToast('正在发布...', 'info');

  try {
    let payload, endpoint;
    if (currentMode === 'addon') {
      endpoint = '/publish-addon';
      payload = {
        title,
        sulg: slug,
        summary: document.getElementById('summary').value.trim(),
        content,
        manifestUrl: document.getElementById('manifestUrl').value.trim(),
        description: document.getElementById('description').value.trim(),
        types: JSON.parse(document.getElementById('types').value || '[]')
      };
    } else {
      endpoint = '/publish-article';
      payload = {
        title,
        slug,
        summary: document.getElementById('summary').value.trim(),
        content
      };
    }
    const res = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (data.success) {
      showToast('发布成功! ID: ' + data.id, 'success');
    } else {
      showToast('发布失败: ' + (data.error || '未知错误'), 'error');
    }
  } catch (err) {
    showToast('发布失败: ' + err.message, 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = currentMode === 'addon' ? '发布 Addon 到 Strapi' : '发布 Article 到 Strapi';
  }
}

function showToast(msg, type) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.className = 'toast ' + type;
  t.style.display = 'block';
  clearTimeout(t._timer);
  t._timer = setTimeout(() => t.style.display = 'none', 3000);
}

// init
switchMode('addon');
</script>
</body>
</html>"""


# ============ 图片处理 ============
def process_and_upload_image(image_data, content_type):
    """压缩图片并上传到 R2，返回 URL"""
    try:
        img = Image.open(BytesIO(image_data))
        if img.mode in ('RGBA', 'LA', 'P'):
            bg = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            bg.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
            img = bg
        elif img.mode != 'RGB':
            img = img.convert('RGB')

        w, h = img.size
        if w > 1200:
            ratio = 1200 / w
            img = img.resize((1200, int(h * ratio)), Image.LANCZOS)

        output = BytesIO()
        img.save(output, format='JPEG', quality=85, optimize=True)
        output.seek(0)
        processed = output.getvalue()
    except Exception:
        processed = image_data

    name = f"addons/{uuid.uuid4().hex[:12]}.jpg"
    s3_client.put_object(
        Bucket=R2_BUCKET_NAME,
        Key=name,
        Body=processed,
        ContentType='image/jpeg',
        CacheControl='public, max-age=31536000'
    )
    return f"https://{R2_CUSTOM_DOMAIN}/{name}"


# ============ HTTP 服务器 ============
class Handler(http.server.BaseHTTPRequestHandler):

    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        page = HTML_PAGE.replace('__R2_DOMAIN__', R2_CUSTOM_DOMAIN)
        self.wfile.write(page.encode('utf-8'))

    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length)

        if self.path == '/upload-image':
            self._handle_upload(body)
        elif self.path == '/fetch-manifest':
            self._handle_manifest(body)
        elif self.path == '/publish-addon':
            self._publish_to_strapi(body, '/api/addons')
        elif self.path == '/publish-article':
            self._publish_to_strapi(body, '/api/articles')
        else:
            self._json_response({'error': 'Not found'}, 404)

    def _handle_upload(self, body):
        try:
            content_type = self.headers.get('Content-Type', 'image/png')
            url = process_and_upload_image(body, content_type)
            self._json_response({'url': url})
        except Exception as e:
            self._json_response({'error': str(e)}, 500)

    def _handle_manifest(self, body):
        try:
            data = json.loads(body)
            url = data.get('url', '')
            resp = req_lib.get(url, timeout=15, headers={'User-Agent': 'AddonEditor/1.0'})
            resp.raise_for_status()
            manifest = resp.json()
            self._json_response({
                'name': manifest.get('name', ''),
                'description': manifest.get('description', ''),
                'types': manifest.get('types', []),
                'logo': manifest.get('logo', ''),
            })
        except Exception as e:
            self._json_response({'error': f'获取失败: {e}'}, 500)

    def _publish_to_strapi(self, body, api_path):
        try:
            data = json.loads(body)
            resp = req_lib.post(
                f"{STRAPI_URL}{api_path}",
                json={'data': data},
                headers={'Authorization': f'Bearer {STRAPI_API_TOKEN}'},
                timeout=15
            )
            if resp.ok:
                result = resp.json()
                self._json_response({'success': True, 'id': result.get('data', {}).get('id')})
            else:
                self._json_response({'error': f'Strapi {resp.status_code}: {resp.text[:500]}'}, 500)
        except Exception as e:
            self._json_response({'error': str(e)}, 500)

    def _json_response(self, data, code=200):
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))

    def log_message(self, format, *args):
        print(f"[{self.log_date_time_string()}] {args[0]}")


if __name__ == '__main__':
    import webbrowser
    server = http.server.HTTPServer(('127.0.0.1', PORT), Handler)
    print(f"Stremio Editor running at http://127.0.0.1:{PORT}")
    webbrowser.open(f"http://127.0.0.1:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
        server.server_close()
