(function () {
  function parseEvery(trigger) {
    const match = String(trigger || '').match(/every\s+(\d+(?:\.\d+)?)(ms|s)/i);
    if (!match) return null;
    const value = Number(match[1]);
    return match[2].toLowerCase() === 's' ? value * 1000 : value;
  }
  function activeTabs(el) {
    const state = {};
    el.querySelectorAll('[data-tabs]').forEach(function (tabs) {
      const name = tabs.getAttribute('data-tabs');
      const activeButtons = tabs.querySelectorAll(':scope > .tab-list .tab-button.active, :scope > .model-output-tab-list .tab-button.active');
      const active = Array.from(activeButtons).find(function (button) {
        return button.closest('[data-tabs]') === tabs;
      });
      if (name && active) state[name] = active.getAttribute('data-tab-target');
    });
    return state;
  }
  function activateTab(root, name, target) {
    const tabs = root.matches && root.matches('[data-tabs="' + name + '"]') ? root : root.querySelector('[data-tabs="' + name + '"]');
    if (!tabs || !target) return;
    const buttons = tabs.querySelectorAll(':scope > .tab-list .tab-button[data-tab-target], :scope > .model-output-tab-list .tab-button[data-tab-target]');
    buttons.forEach(function (button) {
      if (button.closest('[data-tabs]') === tabs) {
        button.classList.toggle('active', button.getAttribute('data-tab-target') === target);
      }
    });
    const panels = tabs.querySelectorAll(':scope > .tab-panel, :scope > .model-output-item.tab-panel');
    panels.forEach(function (panel) {
      panel.classList.toggle('active', panel.getAttribute('data-tab-panel') === target);
    });
  }
  function restoreTabs(el, state) {
    Object.keys(state || {}).forEach(function (name) {
      activateTab(el, name, state[name]);
    });
  }
  function bindTabs(root) {
    root.querySelectorAll('.tab-button[data-tab-target]').forEach(function (button) {
      if (button.dataset.boundTabs === '1') return;
      button.dataset.boundTabs = '1';
      button.addEventListener('click', function () {
        const tabs = button.closest('[data-tabs]');
        if (!tabs) return;
        activateTab(tabs, tabs.getAttribute('data-tabs'), button.getAttribute('data-tab-target'));
      });
    });
  }
  function modelOutputPanelKey(panel) {
    const tabs = panel.closest('[data-tabs]');
    const panelName = panel.getAttribute('data-tab-panel');
    const tabsName = tabs ? tabs.getAttribute('data-tabs') : '';
    return tabsName && panelName ? tabsName + '::' + panelName : '';
  }
  function snapshotFrozenModelOutputs(el) {
    const state = {};
    el.querySelectorAll('.model-output-item.tab-panel').forEach(function (panel) {
      const isRunning = !!panel.querySelector('.badge.running, .streaming-output');
      const key = modelOutputPanelKey(panel);
      if (!key || isRunning) return;
      const scroller = panel.querySelector('pre');
      state[key] = {
        html: panel.innerHTML,
        scrollTop: scroller ? scroller.scrollTop : 0
      };
    });
    return state;
  }
  function restoreFrozenModelOutputs(el, state) {
    Object.keys(state || {}).forEach(function (key) {
      el.querySelectorAll('.model-output-item.tab-panel').forEach(function (panel) {
        if (modelOutputPanelKey(panel) !== key) return;
        const isRunning = !!panel.querySelector('.badge.running, .streaming-output');
        if (isRunning) return;
        panel.innerHTML = state[key].html;
        const scroller = panel.querySelector('pre');
        if (scroller) scroller.scrollTop = state[key].scrollTop || 0;
      });
    });
  }
  function activeChannelSlot(el) {
    if (el.dataset.selectedChannelSlot) return el.dataset.selectedChannelSlot;
    const active = el.querySelector('.channel-dot.active[data-channel-slot]');
    return active ? active.getAttribute('data-channel-slot') : '';
  }
  function markActiveChannelSlot(el, channelSlot) {
    if (!channelSlot) return;
    el.querySelectorAll('.channel-dot[data-channel-slot]').forEach(function (button) {
      button.classList.toggle('active', button.getAttribute('data-channel-slot') === channelSlot);
    });
  }
  function selectedSlotInHtml(html) {
    const match = String(html || '').match(/data-selected-slot="([^"]*)"/);
    return match ? match[1] : '';
  }
  function refreshUrl(url, channelSlot) {
    if (!channelSlot) return url;
    const next = new URL(url, window.location.href);
    next.searchParams.set('selected_channel_slot', channelSlot);
    return next.pathname + next.search;
  }
  async function refresh(el, forcedChannelSlot) {
    const url = el.getAttribute('hx-get');
    if (!url) return;
    const selectedChannelSlot = forcedChannelSlot || activeChannelSlot(el);
    if (selectedChannelSlot) el.dataset.selectedChannelSlot = selectedChannelSlot;
    const refreshSeq = Number(el.dataset.refreshSeq || '0') + 1;
    el.dataset.refreshSeq = String(refreshSeq);
    const openDetails = Array.from(el.querySelectorAll('details')).map(function (node) {
      return node.open;
    });
    const tabState = activeTabs(el);
    const frozenModelOutputs = snapshotFrozenModelOutputs(el);
    try {
      const headers = { 'X-Requested-With': 'htmx-lite' };
      if (selectedChannelSlot) headers['X-Selected-Channel-Slot'] = selectedChannelSlot;
      const res = await fetch(refreshUrl(url, selectedChannelSlot), { headers });
      if (res.ok) {
        if (el.dataset.refreshSeq !== String(refreshSeq)) return;
        const html = await res.text();
        if (selectedChannelSlot) {
          const responseSlot = selectedSlotInHtml(html);
          if (responseSlot && responseSlot !== selectedChannelSlot) return;
        }
        el.innerHTML = html;
        if (selectedChannelSlot) {
          el.dataset.selectedChannelSlot = selectedChannelSlot;
          markActiveChannelSlot(el, selectedChannelSlot);
        }
        Array.from(el.querySelectorAll('details')).forEach(function (node, index) {
          if (openDetails[index]) node.open = true;
        });
        restoreFrozenModelOutputs(el, frozenModelOutputs);
        restoreTabs(el, tabState);
        bindTabs(el);
        bindChannelDots(el);
      }
    } catch (error) {
      if (el.dataset.refreshSeq !== String(refreshSeq)) return;
      el.innerHTML = '<section class="panel"><div class="alert">刷新失败: ' + String(error) + '</div></section>';
    }
  }
  function boot() {
    bindTabs(document);
    bindChannelDots(document);
    document.querySelectorAll('[hx-get]').forEach(function (el) {
      const trigger = el.getAttribute('hx-trigger') || '';
      if (trigger.includes('load')) refresh(el);
      const interval = parseEvery(trigger);
      if (interval) {
        setInterval(function () {
          const statusEl = el.querySelector('[data-status]');
          const status = statusEl ? statusEl.getAttribute('data-status') : '';
          if (status === 'completed' || status === 'failed' || status === 'stopped') return;
          refresh(el);
        }, interval);
      }
    });
  }
  function bindChannelDots(root) {
    root.querySelectorAll('.channel-dot[data-channel-slot]').forEach(function (button) {
      if (button.dataset.boundChannel === '1') return;
      button.dataset.boundChannel = '1';
      button.addEventListener('click', function () {
        const host = button.closest('[hx-get]');
        if (!host) return;
        host.dataset.selectedChannelSlot = button.getAttribute('data-channel-slot') || '';
        markActiveChannelSlot(host, host.dataset.selectedChannelSlot);
        refresh(host, host.dataset.selectedChannelSlot);
      });
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
