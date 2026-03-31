/* Embedding Loader */
(function () {
  'use strict';
  const overlay    = document.getElementById('embedding-loader-overlay');
  const progressBar= document.getElementById('el-progress-bar');
  let _timers = [], _apiDone = false, _step3Active = false, _pendingCallback = null;
  const _originalIcons = {};

  function setProgress(pct) { if (progressBar) progressBar.style.width = pct + '%'; }

  function activateStep(id) {
    const el = document.getElementById(id);
    if (!el) return;
    el.classList.remove('el-waiting','el-done');
    el.classList.add('el-running');
  }

  function completeStep(id) {
    const el = document.getElementById(id);
    if (!el) return;
    el.classList.remove('el-running','el-waiting');
    el.classList.add('el-done');
    const iconWrap = el.querySelector('.el-step-icon');
    if (iconWrap) {
      iconWrap.innerHTML = '<svg width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><polyline class="el-check-svg" stroke-linecap="round" stroke-linejoin="round" points="20 6 9 17 4 12"/></svg>';
    }
  }

  function schedule(fn, ms) { const t = setTimeout(fn, ms); _timers.push(t); return t; }
  function clearAllTimers() { _timers.forEach(clearTimeout); _timers = []; }

  window.showEmbeddingLoader = function () {
    _apiDone = false; _step3Active = false;
    ['el-step-1','el-step-2','el-step-3','el-step-4'].forEach(function(id) {
      const el = document.getElementById(id);
      if (!el) return;
      el.className = 'el-step el-waiting';
      const icon = el.querySelector('.el-step-icon');
      if (icon && _originalIcons[id]) icon.innerHTML = _originalIcons[id];
    });
    setProgress(0);
    if (overlay) overlay.classList.add('el-active');

    schedule(function() { activateStep('el-step-1'); setProgress(15); }, 100);
    schedule(function() { completeStep('el-step-1'); setProgress(25); }, 1900);
    schedule(function() { activateStep('el-step-2'); setProgress(38); }, 2100);
    schedule(function() { completeStep('el-step-2'); setProgress(55); }, 4500);
    schedule(function() {
      activateStep('el-step-3'); setProgress(62);
      _step3Active = true;
      if (_apiDone) _finishLoading(_pendingCallback);
    }, 4700);
  };

  window.notifyEmbeddingDone = function (callback) {
    _apiDone = true;
    _pendingCallback = callback || function(){};
    if (_step3Active) _finishLoading(_pendingCallback);
  };

  function _finishLoading(callback) {
    schedule(function() { completeStep('el-step-3'); setProgress(82); }, 400);
    schedule(function() { activateStep('el-step-4');  setProgress(95); }, 900);
    schedule(function() { completeStep('el-step-4');  setProgress(100); }, 1600);
    schedule(function() {
      if (overlay) overlay.classList.remove('el-active');
      setProgress(0);
      if (callback) callback();
    }, 2200);
  }

  window.hideEmbeddingLoader = function () {
    clearAllTimers(); _apiDone = false;
    if (overlay) overlay.classList.remove('el-active');
    setProgress(0);
  };

  document.addEventListener('DOMContentLoaded', function() {
    ['el-step-1','el-step-2','el-step-3','el-step-4'].forEach(function(id) {
      const el = document.getElementById(id);
      if (el) { const icon = el.querySelector('.el-step-icon'); if (icon) _originalIcons[id] = icon.innerHTML; }
    });
  });
})();
