/**
 * Smart File Preview — handles PDF, DOCX, XLSX, XLS, CSV, TXT, MD
 * Usage: initSmartPreview('container-id', '/api/preview-file', 'filename.xlsx')
 */

function loadScript(src, onload) {
  if (document.querySelector('script[src="' + src + '"]')) {
    onload(); return;
  }
  const s = document.createElement('script');
  s.src = src; s.onload = onload;
  s.onerror = () => console.error('Failed to load: ' + src);
  document.head.appendChild(s);
}

function escHtml(t) {
  return String(t)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

var previewStyles = `
  @keyframes spin { to { transform: rotate(360deg); } }
  @keyframes fadeSlideIn { from { opacity:0; transform:translateY(8px); } to { opacity:1; transform:translateY(0); } }

  .preview-wrapper {
    height: 100%;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    background: #f8fafc;
    animation: fadeSlideIn 0.3s ease-out;
  }
  .preview-toolbar {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 16px;
    background: white;
    border-bottom: 1px solid #e2e8f0;
    flex-shrink: 0;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
  }
  .preview-toolbar-icon {
    width: 30px; height: 30px;
    border-radius: 8px;
    display: flex; align-items: center; justify-content: center;
    flex-shrink: 0;
  }
  .preview-toolbar-label {
    font-size: 12px; font-weight: 600;
    color: #64748b; letter-spacing: 0.04em; text-transform: uppercase;
  }
  .preview-scroll {
    flex: 1;
    overflow: auto;
    padding: 0;
  }

  /* ── TXT / MD styles ── */
  .text-preview-inner {
    padding: 28px 36px;
    max-width: 820px;
    margin: 0 auto;
  }
  .text-preview-line-nums {
    display: flex;
    gap: 0;
  }
  .text-line-num-col {
    padding: 18px 12px 18px 20px;
    font-size: 12px; line-height: 1.8;
    color: #94a3b8;
    user-select: none;
    text-align: right;
    min-width: 44px;
    background: #f1f5f9;
    border-right: 1px solid #e2e8f0;
    flex-shrink: 0;
    font-family: 'Courier New', monospace;
  }
  .text-code-col {
    padding: 18px 28px;
    flex: 1;
    overflow: hidden;
  }
  .text-code-col pre {
    font-family: 'Courier New', monospace;
    font-size: 13px;
    line-height: 1.8;
    white-space: pre-wrap;
    word-break: break-word;
    color: #1e293b;
    margin: 0;
  }

  /* ── CSV / XLSX table styles ── */
  .table-preview-wrap {
    overflow: auto;
    height: 100%;
  }
  .preview-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
    font-family: 'Inter', sans-serif;
  }
  .preview-table thead tr {
    background: linear-gradient(to bottom, #f8fafc, #f1f5f9);
    position: sticky;
    top: 0;
    z-index: 2;
  }
  .preview-table th {
    padding: 10px 14px;
    text-align: left;
    font-weight: 700;
    color: #374151;
    border-bottom: 2px solid #e2e8f0;
    border-right: 1px solid #e9eef5;
    white-space: nowrap;
    font-size: 12px;
    letter-spacing: 0.02em;
  }
  .preview-table th:first-child { padding-left: 18px; }
  .preview-table td {
    padding: 9px 14px;
    color: #374151;
    border-bottom: 1px solid #f1f5f9;
    border-right: 1px solid #f1f5f9;
    max-width: 240px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-size: 13px;
  }
  .preview-table td:first-child { padding-left: 18px; }
  .preview-table tbody tr:hover { background: #f0f6ff !important; }
  .preview-table tbody tr:nth-child(even) { background: #fafbfc; }
  .preview-table tbody tr:nth-child(odd)  { background: white; }

  /* ── Row count badge ── */
  .row-count-badge {
    margin-left: auto;
    font-size: 11px;
    font-weight: 600;
    padding: 3px 10px;
    border-radius: 999px;
    background: #eff6ff;
    color: #3b82f6;
    border: 1px solid #bfdbfe;
  }

  /* ── Sheet tabs ── */
  .sheet-tabs {
    display: flex;
    gap: 4px;
    padding: 8px 16px;
    background: #f8fafc;
    border-bottom: 1px solid #e2e8f0;
    overflow-x: auto;
    flex-shrink: 0;
  }
  .sheet-tab {
    padding: 5px 16px;
    border-radius: 6px;
    border: 1.5px solid #e2e8f0;
    background: white;
    color: #64748b;
    font-size: 12px;
    font-weight: 600;
    cursor: pointer;
    white-space: nowrap;
    transition: all 0.15s ease;
    outline: none;
  }
  .sheet-tab:hover { border-color: #6366f1; color: #6366f1; }
  .sheet-tab.active {
    background: #6366f1;
    color: white;
    border-color: #6366f1;
    box-shadow: 0 2px 8px rgba(99,102,241,0.25);
  }

  /* ── DOCX viewer styles ── */
  .docx-preview-inner {
    max-width: 780px;
    margin: 0 auto;
    padding: 48px 64px;
    background: white;
    min-height: calc(100% - 4px);
    box-shadow: 0 0 0 1px #e2e8f0;
  }
  .docx-preview-inner h1, .docx-preview-inner h2, .docx-preview-inner h3,
  .docx-preview-inner h4, .docx-preview-inner h5, .docx-preview-inner h6 {
    font-family: 'Outfit', sans-serif;
    color: #111827;
    margin: 1.4em 0 0.5em;
    line-height: 1.3;
  }
  .docx-preview-inner h1 { font-size: 1.75rem; border-bottom: 2px solid #e2e8f0; padding-bottom: 0.4em; }
  .docx-preview-inner h2 { font-size: 1.35rem; }
  .docx-preview-inner h3 { font-size: 1.15rem; }
  .docx-preview-inner p  { margin: 0.6em 0; line-height: 1.85; color: #1e293b; font-size: 14px; }
  .docx-preview-inner ul, .docx-preview-inner ol { padding-left: 1.6em; margin: 0.6em 0; }
  .docx-preview-inner li { margin: 0.3em 0; line-height: 1.7; color: #1e293b; font-size: 14px; }
  .docx-preview-inner table { border-collapse: collapse; width: 100%; margin: 1em 0; font-size: 13px; }
  .docx-preview-inner table td, .docx-preview-inner table th {
    border: 1px solid #e2e8f0; padding: 8px 12px;
  }
  .docx-preview-inner table th { background: #f8fafc; font-weight: 700; }
  .docx-preview-inner img { max-width: 100%; border-radius: 6px; margin: 0.5em 0; }
  .docx-preview-inner strong, .docx-preview-inner b { color: #0f172a; }
  .docx-preview-inner em, .docx-preview-inner i { color: #334155; }
`;

function injectStyles() {
  if (document.getElementById('smart-preview-styles')) return;
  var st = document.createElement('style');
  st.id = 'smart-preview-styles';
  st.textContent = previewStyles;
  document.head.appendChild(st);
}

function showLoading(container) {
  injectStyles();
  container.innerHTML = `
    <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;
                height:100%;min-height:300px;gap:14px;color:#64748b;background:#f8fafc;">
      <div style="width:44px;height:44px;border-radius:50%;background:hsl(221,83%,95%);
                  display:flex;align-items:center;justify-content:center;">
        <svg width="22" height="22" fill="none" viewBox="0 0 24 24" style="animation:spin 0.9s linear infinite;">
          <circle cx="12" cy="12" r="10" stroke="#dde6f0" stroke-width="3"/>
          <path d="M12 2a10 10 0 010 20" stroke="#6366f1" stroke-width="3" stroke-linecap="round"/>
        </svg>
      </div>
      <span style="font-size:13px;font-weight:600;color:#475569;">Loading preview…</span>
    </div>
    <style>@keyframes spin{to{transform:rotate(360deg)}}</style>`;
}

function showError(container, msg) {
  injectStyles();
  container.innerHTML = `
    <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;
                height:100%;min-height:300px;gap:12px;color:#64748b;padding:32px;text-align:center;background:#f8fafc;">
      <div style="width:52px;height:52px;border-radius:14px;background:#fff7ed;display:flex;align-items:center;justify-content:center;">
        <svg width="26" height="26" fill="none" stroke="#f97316" stroke-width="1.8" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round"
                d="M12 9v4m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/>
        </svg>
      </div>
      <p style="font-size:13px;font-weight:500;color:#64748b;max-width:280px;line-height:1.6;">${escHtml(msg)}</p>
    </div>`;
}

/* ── Toolbar builder ── */

function makeToolbar(iconSvg, iconBg, iconColor, label, extra) {
  return `<div class="preview-toolbar">
    <div class="preview-toolbar-icon" style="background:${iconBg};color:${iconColor};">
      ${iconSvg}
    </div>
    <span class="preview-toolbar-label">${escHtml(label)}</span>
    ${extra || ''}
  </div>`;
}

/* ── Renderers ── */

function renderPdf(container, url) {
  injectStyles();
  container.style.padding = '0';
  container.style.overflow = 'hidden';
  container.style.position = 'relative';
  var iframe = document.createElement('iframe');
  iframe.src = url;
  iframe.title = 'PDF Preview';
  iframe.style.cssText = 'position:absolute;top:0;left:0;width:100%;height:100%;border:none;display:block;background:white;';
  container.innerHTML = '';
  container.appendChild(iframe);
}

function renderText(container, text, filename) {
  injectStyles();
  var ext = (filename || '').split('.').pop().toLowerCase();
  var isMd = ext === 'md';
  var lines = text.split('\n');
  var lineNums = lines.map((_, i) => (i + 1)).join('\n');

  var iconSvg = isMd
    ? `<svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg>`
    : `<svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M4 6h16M4 10h16M4 14h10"/></svg>`;

  var linesBadge = `<span class="row-count-badge">${lines.length} lines</span>`;

  container.innerHTML = `
    <div class="preview-wrapper">
      ${makeToolbar(iconSvg, isMd ? '#f0fdf4' : '#eff6ff', isMd ? '#16a34a' : '#3b82f6', isMd ? 'Markdown' : 'Plain Text', linesBadge)}
      <div class="preview-scroll">
        <div class="text-preview-line-nums" style="min-height:100%;">
          <div class="text-line-num-col"><pre style="margin:0;font-family:inherit;">${lineNums}</pre></div>
          <div class="text-code-col"><pre>${escHtml(text)}</pre></div>
        </div>
      </div>
    </div>`;
}

function renderCsv(container, text, filename) {
  injectStyles();
  loadScript('https://cdn.jsdelivr.net/npm/papaparse@5.4.1/papaparse.min.js', function() {
    var result = Papa.parse(text.trim(), { header: true, skipEmptyLines: true });
    var fields = result.meta.fields || [];
    var rows   = result.data;

    var iconSvg = `<svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M9 3H5a2 2 0 00-2 2v4m6-6h10a2 2 0 012 2v4M9 3v18m0 0h10a2 2 0 002-2V9M9 21H5a2 2 0 01-2-2V9m0 0h18"/></svg>`;
    var rowsBadge = `<span class="row-count-badge">${rows.length} rows · ${fields.length} cols</span>`;

    var tableHtml = `<table class="preview-table">
      <thead><tr>${fields.map(function(f) { return '<th>' + escHtml(f) + '</th>'; }).join('')}</tr></thead>
      <tbody>${rows.map(function(row) {
        return '<tr>' + fields.map(function(f) {
          return '<td title="' + escHtml(row[f] || '') + '">' + escHtml(row[f] || '') + '</td>';
        }).join('') + '</tr>';
      }).join('')}</tbody>
    </table>`;

    container.innerHTML = `
      <div class="preview-wrapper">
        ${makeToolbar(iconSvg, '#f0fdf4', '#16a34a', 'CSV Spreadsheet', rowsBadge)}
        <div class="table-preview-wrap">${tableHtml}</div>
      </div>`;
  });
}

function renderXlsx(container, arrayBuffer, filename) {
  injectStyles();
  loadScript('https://cdn.sheetjs.com/xlsx-0.20.3/package/dist/xlsx.full.min.js', function() {
    try {
      var wb = XLSX.read(arrayBuffer, { type: 'array' });
      var sheetNames = wb.SheetNames;

      var iconSvg = `<svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M9 3H5a2 2 0 00-2 2v4m6-6h10a2 2 0 012 2v4M9 3v18m0 0h10a2 2 0 002-2V9M9 21H5a2 2 0 01-2-2V9m0 0h18"/></svg>`;

      function getSheetRows(idx) {
        var ws = wb.Sheets[sheetNames[idx]];
        var data = XLSX.utils.sheet_to_json(ws, { header: 1, defval: '' });
        if (!data.length) return { headers: [], rows: [] };
        var headers = data[0];
        var rows = data.slice(1);
        return { headers: headers, rows: rows };
      }

      function buildTable(idx) {
        var d = getSheetRows(idx);
        var badge = `<span class="row-count-badge">${d.rows.length} rows · ${d.headers.length} cols</span>`;
        var table = `<table class="preview-table">
          <thead><tr>${d.headers.map(function(h) { return '<th>' + escHtml(String(h)) + '</th>'; }).join('')}</tr></thead>
          <tbody>${d.rows.map(function(row) {
            return '<tr>' + d.headers.map(function(_, ci) {
              var val = row[ci] !== undefined ? String(row[ci]) : '';
              return '<td title="' + escHtml(val) + '">' + escHtml(val) + '</td>';
            }).join('') + '</tr>';
          }).join('')}</tbody>
        </table>`;
        return { table: table, badge: badge };
      }

      var tabsHtml = sheetNames.length > 1
        ? `<div class="sheet-tabs">${sheetNames.map(function(name, i) {
            return '<button class="sheet-tab' + (i===0?' active':'') + '" onclick="switchXlsxSheet(' + i + ')" id="xlsx-tab-' + i + '">' + escHtml(name) + '</button>';
          }).join('')}</div>` : '';

      var initial = buildTable(0);

      container.innerHTML = `
        <div class="preview-wrapper">
          ${makeToolbar(iconSvg, '#f0fdf4', '#16a34a', 'Excel Spreadsheet', initial.badge)}
          ${tabsHtml}
          <div id="xlsx-badge-area" style="display:none;"></div>
          <div class="table-preview-wrap" id="xlsx-sheet-content">${initial.table}</div>
        </div>`;

      window.switchXlsxSheet = function(idx) {
        var d = buildTable(idx);
        document.getElementById('xlsx-sheet-content').innerHTML = d.table;
        sheetNames.forEach(function(_, i) {
          var btn = document.getElementById('xlsx-tab-' + i);
          if (btn) { btn.className = 'sheet-tab' + (i === idx ? ' active' : ''); }
        });
      };

    } catch (err) {
      showError(container, 'Could not render Excel file: ' + err.message);
    }
  });
}

function renderDocx(container, arrayBuffer) {
  injectStyles();
  loadScript('https://cdn.jsdelivr.net/npm/mammoth@1.8.0/mammoth.browser.min.js', function() {
    mammoth.convertToHtml({ arrayBuffer: arrayBuffer })
      .then(function(result) {
        var iconSvg = `<svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg>`;
        container.innerHTML = `
          <div class="preview-wrapper">
            ${makeToolbar(iconSvg, '#eff6ff', '#3b82f6', 'Word Document', '')}
            <div class="preview-scroll" style="background:#f1f5f9;padding:20px;">
              <div class="docx-preview-inner">${result.value || '<p style="color:#94a3b8;">Empty document</p>'}</div>
            </div>
          </div>`;
      })
      .catch(function(err) {
        showError(container, 'Could not render Word document: ' + err.message);
      });
  });
}

function renderImage(container, url, filename) {
  injectStyles();
  var ext = (filename || '').split('.').pop().toUpperCase();
  var iconSvg = `<svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"/></svg>`;
  container.innerHTML = `
    <div class="preview-wrapper">
      ${makeToolbar(iconSvg, '#fdf4ff', '#a855f7', ext + ' Image', '')}
      <div class="preview-scroll" style="display:flex;align-items:center;justify-content:center;padding:24px;background:#f8fafc;">
        <div style="max-width:100%;max-height:100%;text-align:center;">
          <img src="${url}"
               alt="${escHtml(filename)}"
               style="max-width:100%;max-height:calc(55vh - 80px);object-fit:contain;
                      border-radius:10px;box-shadow:0 4px 24px rgba(0,0,0,0.10);
                      border:1px solid #e2e8f0;background:white;padding:4px;"
               onerror="this.parentElement.innerHTML='<p style=\'color:#94a3b8;font-size:13px;\'>Could not load image.</p>'" />
          <p style="margin-top:12px;font-size:12px;color:#94a3b8;font-weight:500;">${escHtml(filename)}</p>
        </div>
      </div>
    </div>`;
}

/* ── Main entry point ── */

function initSmartPreview(containerId, previewUrl, filename) {
  var container = document.getElementById(containerId);
  if (!container) return;

  var ext = (filename.split('.').pop() || '').toLowerCase().trim();
  showLoading(container);

  if (ext === 'pdf') {
    renderPdf(container, previewUrl);
    return;
  }

  if (ext === 'txt' || ext === 'md') {
    fetch(previewUrl)
      .then(function(r) { if (!r.ok) throw new Error('Fetch failed'); return r.text(); })
      .then(function(text) { renderText(container, text, filename); })
      .catch(function(err) { showError(container, 'Could not load file: ' + err.message); });
    return;
  }

  if (ext === 'csv') {
    fetch(previewUrl)
      .then(function(r) { if (!r.ok) throw new Error('Fetch failed'); return r.text(); })
      .then(function(text) { renderCsv(container, text, filename); })
      .catch(function(err) { showError(container, 'Could not load CSV: ' + err.message); });
    return;
  }

  if (ext === 'xlsx' || ext === 'xls') {
    fetch(previewUrl)
      .then(function(r) { if (!r.ok) throw new Error('Fetch failed'); return r.arrayBuffer(); })
      .then(function(ab) { renderXlsx(container, ab, filename); })
      .catch(function(err) { showError(container, 'Could not load spreadsheet: ' + err.message); });
    return;
  }

  if (ext === 'docx') {
    fetch(previewUrl)
      .then(function(r) { if (!r.ok) throw new Error('Fetch failed'); return r.arrayBuffer(); })
      .then(function(ab) { renderDocx(container, ab); })
      .catch(function(err) { showError(container, 'Could not load document: ' + err.message); });
    return;
  }

  if (ext === 'png' || ext === 'jpg' || ext === 'jpeg' || ext === 'webp' || ext === 'bmp') {
    renderImage(container, previewUrl, filename);
    return;
  }

  if (ext === 'ppt' || ext === 'pptx') {
    showError(container, 'PowerPoint preview is not supported in the browser. Your file has been uploaded successfully — click "Process & Start Asking" to continue.');
    return;
  }

  if (ext === 'doc') {
    showError(container, 'Old .doc format preview is not supported. Please save as .docx for preview.');
    return;
  }

  showError(container, 'Preview not available for .' + ext + ' files.');
}
