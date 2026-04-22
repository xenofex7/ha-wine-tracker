// Advanced Filter — a powerful client-side filter that augments the quick
// popover filter on index.html. Conditions are AND-combined and evaluated
// against each card's data-* attributes inside applyFilters().
(function () {
  'use strict';

  var STORAGE_KEY = 'wine-advanced-filter';
  var T = window.T || {};

  // ── Field catalogue ────────────────────────────────────────────────────
  // Each field defines its grouping, input type, and accepted operators.
  // Order here is the order shown inside each accordion group.
  var FIELDS = [
    // Text
    { key: 'name',         group: 'text',   type: 'text',   label: 'filter_field_name' },
    { key: 'region',       group: 'text',   type: 'text',   label: 'filter_field_region' },
    { key: 'grape',        group: 'text',   type: 'text',   label: 'filter_field_grape' },
    { key: 'location',     group: 'text',   type: 'text',   label: 'filter_field_location' },
    { key: 'notes',        group: 'text',   type: 'text',   label: 'filter_field_notes' },
    // Numbers
    { key: 'year',         group: 'numbers', type: 'number', label: 'filter_field_year',     integer: true },
    { key: 'price',        group: 'numbers', type: 'number', label: 'filter_field_price' },
    { key: 'rating',       group: 'numbers', type: 'number', label: 'filter_field_rating',   integer: true, min: 0, max: 5 },
    { key: 'quantity',     group: 'numbers', type: 'number', label: 'filter_field_quantity', integer: true, min: 0 },
    // Choice
    { key: 'type',          group: 'choice', type: 'choice', label: 'filter_field_type' },
    { key: 'bottle_format', group: 'choice', type: 'choice', label: 'filter_field_bottle_format' },
    // Date
    { key: 'purchased_at', group: 'date',   type: 'date',   label: 'filter_field_purchased_at' },
    // Drink window (virtual, computed from drink_from/drink_until)
    { key: 'drink_window', group: 'drinkwindow', type: 'drinkwindow', label: 'filter_group_drinkwindow' },
  ];

  var GROUPS = [
    { key: 'text',         label: 'filter_group_text',        icon: 'mdi-format-text' },
    { key: 'numbers',      label: 'filter_group_numbers',     icon: 'mdi-numeric' },
    { key: 'choice',       label: 'filter_group_choice',      icon: 'mdi-format-list-bulleted' },
    { key: 'date',         label: 'filter_group_date',        icon: 'mdi-calendar' },
    { key: 'drinkwindow',  label: 'filter_group_drinkwindow', icon: 'mdi-clock-outline' },
  ];

  var OPS = {
    text:        ['contains', 'not_contains', 'equals', 'empty', 'not_empty'],
    number:      ['eq', 'neq', 'lt', 'gt', 'between', 'empty'],
    choice:      ['in', 'not_in', 'empty'],
    date:        ['before', 'after', 'between', 'last_n_days', 'empty'],
    drinkwindow: ['in'], // multi-select over status values: in / last / past / future
  };

  var OP_LABEL = {
    contains: 'filter_op_contains', not_contains: 'filter_op_not_contains',
    equals: 'filter_op_equals', empty: 'filter_op_empty', not_empty: 'filter_op_not_empty',
    eq: 'filter_op_eq', neq: 'filter_op_neq', lt: 'filter_op_lt', gt: 'filter_op_gt',
    between: 'filter_op_between',
    in: 'filter_op_in', not_in: 'filter_op_not_in',
    before: 'filter_op_before', after: 'filter_op_after', last_n_days: 'filter_op_last_n_days',
  };

  var DW_STATUSES = ['in', 'last', 'past', 'future'];
  var DW_LABELS = {
    'in': 'filter_dw_status_in',
    'last': 'filter_dw_status_last',
    'past': 'filter_dw_status_past',
    'future': 'filter_dw_status_future',
  };

  // ── State ─────────────────────────────────────────────────────────────
  // state.rules is an object keyed by field — one rule per field at most.
  // Rule shape: { op: 'between', value: [min, max] }
  var state = {
    rules: {},        // { [fieldKey]: { op, value } }
    presets: [],      // [{id, name, conditions: {rules}}, ...]
    editingId: null,  // preset currently being edited (null when not in edit mode)
    editingName: '',  // current editable name in edit banner
  };

  function apiBase() {
    // INGRESS is declared via `const INGRESS = '{{ ingress }}'` in index.html.
    // Because const doesn't attach to window, reach it via eval from the outer
    // script scope — but fall back gracefully if it doesn't exist.
    var ingress = '';
    try { ingress = window.INGRESS != null ? window.INGRESS : (typeof INGRESS !== 'undefined' ? INGRESS : ''); }
    catch (e) { /* ignore */ }
    return ingress + '/api/filter-presets';
  }

  function tr(key) { return T[key] || key; }

  // ── Persistence ───────────────────────────────────────────────────────
  function save() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ rules: state.rules }));
    } catch (e) { /* ignore */ }
  }
  function load() {
    try {
      var raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return;
      var parsed = JSON.parse(raw);
      if (parsed && typeof parsed.rules === 'object' && parsed.rules !== null) {
        state.rules = parsed.rules;
      }
    } catch (e) { /* ignore */ }
  }

  function activeCount() {
    return Object.keys(state.rules).length;
  }

  // ── Evaluation ────────────────────────────────────────────────────────
  // Returns true if the card's dataset satisfies all active rules.
  function evaluate(ds) {
    for (var fieldKey in state.rules) {
      if (!state.rules.hasOwnProperty(fieldKey)) continue;
      var rule = state.rules[fieldKey];
      if (!rule || !rule.op) continue;
      if (!evalRule(ds, fieldKey, rule)) return false;
    }
    return true;
  }

  function cardValue(ds, fieldKey) {
    // Browser normalises data-purchased_at to purchased_at on dataset
    return ds[fieldKey];
  }

  function evalRule(ds, fieldKey, rule) {
    var field = fieldByKey(fieldKey);
    if (!field) return true;

    if (field.type === 'drinkwindow') {
      return evalDrinkWindow(ds, rule);
    }

    var raw = cardValue(ds, fieldKey) || '';

    if (rule.op === 'empty')     return String(raw).trim() === '';
    if (rule.op === 'not_empty') return String(raw).trim() !== '';

    if (field.type === 'text') {
      var needle = String(rule.value || '').trim().toLowerCase();
      var hay = String(raw).toLowerCase();
      if (rule.op === 'contains')     return needle === '' || hay.indexOf(needle) !== -1;
      if (rule.op === 'not_contains') return needle === '' || hay.indexOf(needle) === -1;
      if (rule.op === 'equals')       return hay === needle;
      return true;
    }

    if (field.type === 'number') {
      var trimmed = String(raw).trim();
      if (trimmed === '') return false; // a missing value can never satisfy a numeric comparison
      var n = parseFloat(trimmed);
      if (isNaN(n)) return false;
      if (rule.op === 'eq')      return n === parseFloat(rule.value);
      if (rule.op === 'neq')     return n !== parseFloat(rule.value);
      if (rule.op === 'lt')      return n < parseFloat(rule.value);
      if (rule.op === 'gt')      return n > parseFloat(rule.value);
      if (rule.op === 'between') {
        var lo = parseFloat((rule.value || [])[0]);
        var hi = parseFloat((rule.value || [])[1]);
        if (isNaN(lo) && isNaN(hi)) return true;
        if (!isNaN(lo) && n < lo) return false;
        if (!isNaN(hi) && n > hi) return false;
        return true;
      }
      return true;
    }

    if (field.type === 'choice') {
      var selected = Array.isArray(rule.value) ? rule.value : [];
      if (selected.length === 0) return true; // nothing selected = no constraint
      var has = selected.indexOf(String(raw)) !== -1;
      if (rule.op === 'in')     return has;
      if (rule.op === 'not_in') return !has;
      return true;
    }

    if (field.type === 'date') {
      var dateStr = String(raw).trim();
      if (rule.op === 'before') {
        if (!rule.value) return true;
        return dateStr !== '' && dateStr < rule.value;
      }
      if (rule.op === 'after') {
        if (!rule.value) return true;
        return dateStr !== '' && dateStr > rule.value;
      }
      if (rule.op === 'between') {
        var d1 = (rule.value || [])[0];
        var d2 = (rule.value || [])[1];
        if (!d1 && !d2) return true;
        if (dateStr === '') return false;
        if (d1 && dateStr < d1) return false;
        if (d2 && dateStr > d2) return false;
        return true;
      }
      if (rule.op === 'last_n_days') {
        var n2 = parseInt(rule.value, 10);
        if (!n2 || isNaN(n2)) return true;
        if (dateStr === '') return false;
        var cutoff = new Date();
        cutoff.setDate(cutoff.getDate() - n2);
        var cutoffStr = cutoff.toISOString().slice(0, 10);
        return dateStr >= cutoffStr;
      }
      return true;
    }

    return true;
  }

  function evalDrinkWindow(ds, rule) {
    var selected = Array.isArray(rule.value) ? rule.value : [];
    if (selected.length === 0) return true;
    var status = dwStatus(ds);
    return selected.indexOf(status) !== -1;
  }

  function dwStatus(ds) {
    var until = parseInt(ds.drink_until, 10);
    var from  = parseInt(ds.drink_from, 10);
    if (!until) return null;
    var year = new Date().getFullYear();
    if (until < year) return 'past';
    if (until === year) return 'last';
    if ((!from || from <= year) && until >= year) return 'in';
    if (from && from > year) return 'future';
    return null;
  }

  // ── Helpers ───────────────────────────────────────────────────────────
  function fieldByKey(key) {
    for (var i = 0; i < FIELDS.length; i++) {
      if (FIELDS[i].key === key) return FIELDS[i];
    }
    return null;
  }

  function distinctValues(fieldKey) {
    var cards = document.querySelectorAll('.grid .card');
    var out = {};
    cards.forEach(function (c) {
      var v = c.dataset[fieldKey];
      if (v !== undefined && v !== null && String(v).trim() !== '') out[String(v)] = true;
    });
    return Object.keys(out).sort();
  }

  // ── DOM builders ──────────────────────────────────────────────────────
  function el(tag, attrs, children) {
    var n = document.createElement(tag);
    if (attrs) {
      for (var k in attrs) {
        if (!attrs.hasOwnProperty(k)) continue;
        if (k === 'class') n.className = attrs[k];
        else if (k === 'text') n.textContent = attrs[k];
        else if (k === 'html') n.innerHTML = attrs[k];
        else if (k.slice(0, 2) === 'on') n.addEventListener(k.slice(2).toLowerCase(), attrs[k]);
        else if (k === 'dataset') {
          for (var dk in attrs[k]) n.dataset[dk] = attrs[k][dk];
        }
        else n.setAttribute(k, attrs[k]);
      }
    }
    if (children) children.forEach(function (c) {
      if (c != null) n.appendChild(typeof c === 'string' ? document.createTextNode(c) : c);
    });
    return n;
  }

  function render() {
    var container = document.getElementById('advFilterGroups');
    if (!container) return;
    container.innerHTML = '';

    GROUPS.forEach(function (g) {
      var fields = FIELDS.filter(function (f) { return f.group === g.key; });
      if (!fields.length) return;
      container.appendChild(renderGroup(g, fields));
    });

    updateBadge();
    updateSaveButtons();
  }

  function renderGroup(group, fields) {
    var hasActive = fields.some(function (f) { return state.rules[f.key]; });
    var activeInGroup = fields.reduce(function (n, f) { return n + (state.rules[f.key] ? 1 : 0); }, 0);

    var details = el('details', { class: 'adv-filter-group' });
    if (hasActive) details.open = true;
    var summary = el('summary', { class: 'adv-filter-group-summary' }, [
      el('i', { class: 'mdi ' + group.icon + ' adv-filter-group-icon' }),
      el('span', { class: 'adv-filter-group-label', text: tr(group.label) }),
      activeInGroup > 0
        ? el('span', { class: 'adv-filter-group-badge', text: String(activeInGroup) })
        : null,
    ]);
    details.appendChild(summary);

    var body = el('div', { class: 'adv-filter-group-body' });
    fields.forEach(function (f) { body.appendChild(renderField(f)); });
    details.appendChild(body);
    return details;
  }

  function renderField(field) {
    var row = el('div', { class: 'adv-cond', dataset: { field: field.key } });
    var rule = state.rules[field.key];

    // Drink window is a single multi-select row (no operator dropdown)
    if (field.type === 'drinkwindow') {
      row.appendChild(el('label', { class: 'adv-cond-label', text: tr('filter_group_drinkwindow') }));
      var dwGroup = el('div', { class: 'adv-cond-value adv-cond-dwgroup' });
      DW_STATUSES.forEach(function (s) {
        var active = rule && Array.isArray(rule.value) && rule.value.indexOf(s) !== -1;
        dwGroup.appendChild(el('button', {
          type: 'button',
          class: 'adv-cond-chip' + (active ? ' active' : ''),
          text: tr(DW_LABELS[s]),
          onclick: function () {
            var cur = state.rules[field.key] && Array.isArray(state.rules[field.key].value)
              ? state.rules[field.key].value.slice() : [];
            var idx = cur.indexOf(s);
            if (idx === -1) cur.push(s); else cur.splice(idx, 1);
            if (cur.length === 0) delete state.rules[field.key];
            else state.rules[field.key] = { op: 'in', value: cur };
            render();
          },
        }));
      });
      row.appendChild(dwGroup);
      return row;
    }

    // Standard row: [label] [op] [value]
    row.appendChild(el('label', { class: 'adv-cond-label', text: tr(field.label) }));

    var opSelect = el('select', { class: 'adv-cond-op' });
    opSelect.appendChild(el('option', { value: '', text: '—' }));
    OPS[field.type].forEach(function (op) {
      var o = el('option', { value: op, text: tr(OP_LABEL[op] || op) });
      if (rule && rule.op === op) o.selected = 'selected';
      opSelect.appendChild(o);
    });
    opSelect.addEventListener('change', function (e) {
      var op = e.target.value;
      if (!op) {
        delete state.rules[field.key];
      } else {
        // Preserve value when possible, else reset
        var prev = state.rules[field.key];
        state.rules[field.key] = { op: op, value: prev ? prev.value : defaultValueFor(field, op) };
      }
      render();
    });
    row.appendChild(opSelect);

    var valueWrap = el('div', { class: 'adv-cond-value' });
    if (rule && rule.op) valueWrap.appendChild(renderValueInput(field, rule));
    row.appendChild(valueWrap);
    return row;
  }

  function defaultValueFor(field, op) {
    if (op === 'empty' || op === 'not_empty') return null;
    if (op === 'between') return field.type === 'date' ? ['', ''] : ['', ''];
    if (op === 'in' || op === 'not_in') return [];
    return '';
  }

  function renderValueInput(field, rule) {
    if (rule.op === 'empty' || rule.op === 'not_empty') {
      return el('span', { class: 'adv-cond-empty-hint', text: '' });
    }

    if (field.type === 'text') {
      return el('input', {
        type: 'text',
        class: 'adv-cond-input',
        placeholder: tr('filter_placeholder_text'),
        value: rule.value || '',
        oninput: function (e) { state.rules[field.key].value = e.target.value; updateBadge(); },
      });
    }

    if (field.type === 'number') {
      if (rule.op === 'between') {
        var lo = (rule.value || [])[0] || '';
        var hi = (rule.value || [])[1] || '';
        var wrap = el('div', { class: 'adv-cond-range' });
        wrap.appendChild(numberInput(field, lo, tr('filter_placeholder_min'), function (v) {
          var r = state.rules[field.key]; r.value = [v, r.value ? r.value[1] : '']; updateBadge();
        }));
        wrap.appendChild(el('span', { class: 'adv-cond-range-sep', text: '–' }));
        wrap.appendChild(numberInput(field, hi, tr('filter_placeholder_max'), function (v) {
          var r = state.rules[field.key]; r.value = [r.value ? r.value[0] : '', v]; updateBadge();
        }));
        return wrap;
      }
      return numberInput(field, rule.value != null ? rule.value : '', '', function (v) {
        state.rules[field.key].value = v; updateBadge();
      });
    }

    if (field.type === 'choice') {
      var selected = Array.isArray(rule.value) ? rule.value.slice() : [];
      var options = distinctValues(field.key);
      if (options.length === 0) {
        return el('span', { class: 'adv-cond-empty-hint', text: '—' });
      }
      var wrap2 = el('div', { class: 'adv-cond-chips' });
      options.forEach(function (opt) {
        var active = selected.indexOf(opt) !== -1;
        var displayLabel = opt;
        if (field.key === 'type') {
          var wtKey = 'wine_type_' + opt;
          if (T[wtKey]) displayLabel = T[wtKey];
        }
        if (field.key === 'bottle_format') {
          displayLabel = opt + ' L';
        }
        wrap2.appendChild(el('button', {
          type: 'button',
          class: 'adv-cond-chip' + (active ? ' active' : ''),
          text: displayLabel,
          onclick: function (e) {
            var i = selected.indexOf(opt);
            if (i === -1) selected.push(opt); else selected.splice(i, 1);
            state.rules[field.key].value = selected.slice();
            render();
          },
        }));
      });
      return wrap2;
    }

    if (field.type === 'date') {
      if (rule.op === 'between') {
        var d1 = (rule.value || [])[0] || '';
        var d2 = (rule.value || [])[1] || '';
        var w = el('div', { class: 'adv-cond-range' });
        w.appendChild(el('input', {
          type: 'date', class: 'adv-cond-input', value: d1,
          oninput: function (e) { var r = state.rules[field.key]; r.value = [e.target.value, r.value ? r.value[1] : '']; updateBadge(); },
        }));
        w.appendChild(el('span', { class: 'adv-cond-range-sep', text: '–' }));
        w.appendChild(el('input', {
          type: 'date', class: 'adv-cond-input', value: d2,
          oninput: function (e) { var r = state.rules[field.key]; r.value = [r.value ? r.value[0] : '', e.target.value]; updateBadge(); },
        }));
        return w;
      }
      if (rule.op === 'last_n_days') {
        return el('input', {
          type: 'number', min: '1', step: '1',
          class: 'adv-cond-input adv-cond-input-narrow',
          placeholder: tr('filter_placeholder_days'),
          value: rule.value != null ? rule.value : '',
          oninput: function (e) { state.rules[field.key].value = e.target.value; updateBadge(); },
        });
      }
      return el('input', {
        type: 'date', class: 'adv-cond-input',
        value: rule.value || '',
        oninput: function (e) { state.rules[field.key].value = e.target.value; updateBadge(); },
      });
    }

    return el('span', {});
  }

  function numberInput(field, value, placeholder, onChange) {
    var attrs = {
      type: 'number', class: 'adv-cond-input adv-cond-input-narrow',
      placeholder: placeholder || '', value: value != null ? value : '',
      oninput: function (e) { onChange(e.target.value); },
    };
    if (field.integer) attrs.step = '1';
    if (field.min != null) attrs.min = field.min;
    if (field.max != null) attrs.max = field.max;
    return el('input', attrs);
  }

  // ── Badge ─────────────────────────────────────────────────────────────
  function updateBadge() {
    var count = activeCount();
    var modalBadge = document.getElementById('advFilterBadge');
    if (modalBadge) {
      if (count > 0) {
        modalBadge.textContent = count + ' ' + tr('filter_active_count');
        modalBadge.hidden = false;
      } else {
        modalBadge.hidden = true;
      }
    }
    var outer = document.getElementById('advFilterOuterBadge');
    if (outer) {
      if (count > 0) { outer.textContent = String(count); outer.hidden = false; }
      else { outer.hidden = true; }
    }
  }

  // ── Modal lifecycle ───────────────────────────────────────────────────
  function openModal() {
    var m = document.getElementById('advancedFilterModal');
    if (!m) return;
    m.classList.add('open');
    updateEditBanner();
    render();
    loadPresets();
  }

  function closeModal() {
    var m = document.getElementById('advancedFilterModal');
    if (m) m.classList.remove('open');
    // Closing the modal also exits edit mode, so reopening starts clean.
    if (state.editingId) {
      state.editingId = null;
      state.editingName = '';
    }
  }

  function apply() {
    save();
    if (typeof window.applyFilters === 'function') window.applyFilters();
    closeModal();
  }

  function reset() {
    state.rules = {};
    state.editingId = null;
    state.editingName = '';
    save();
    updateEditBanner();
    render();
    if (typeof window.applyFilters === 'function') window.applyFilters();
  }

  // ── Presets ───────────────────────────────────────────────────────────
  function loadPresets() {
    return fetch(apiBase()).then(function (r) { return r.json(); }).then(function (data) {
      if (data && data.ok && Array.isArray(data.presets)) {
        state.presets = data.presets;
      } else {
        state.presets = [];
      }
      renderPresetList();
    }).catch(function () {
      state.presets = [];
      renderPresetList();
    });
  }

  function renderPresetList() {
    var section = document.getElementById('advFilterPresetsSection');
    var list = document.getElementById('advFilterPresetList');
    if (!section || !list) return;

    if (!state.presets.length) {
      section.hidden = true;
      list.innerHTML = '';
      return;
    }
    section.hidden = false;
    list.innerHTML = '';
    state.presets.forEach(function (p) {
      list.appendChild(renderPresetRow(p));
    });
  }

  function renderPresetRow(preset) {
    var isEditing = state.editingId === preset.id;
    var row = el('div', {
      class: 'adv-filter-preset-row' + (isEditing ? ' editing' : ''),
      dataset: { id: preset.id },
    });
    var nameBtn = el('button', {
      type: 'button', class: 'adv-filter-preset-name',
      text: preset.name,
      onclick: function () { loadAndApplyPreset(preset); },
    });
    var editBtn = el('button', {
      type: 'button', class: 'adv-filter-preset-edit',
      title: tr('filter_preset_edit'),
      html: '<i class="mdi mdi-pencil-outline"></i>',
      onclick: function (e) { e.stopPropagation(); enterEditMode(preset); },
    });
    var delBtn = el('button', {
      type: 'button', class: 'adv-filter-preset-delete',
      title: tr('filter_preset_delete'),
      html: '<i class="mdi mdi-trash-can-outline"></i>',
      onclick: function (e) { e.stopPropagation(); confirmDeletePreset(preset); },
    });
    row.appendChild(nameBtn);
    row.appendChild(editBtn);
    row.appendChild(delBtn);
    return row;
  }

  function enterEditMode(preset) {
    state.editingId = preset.id;
    state.editingName = preset.name;
    state.rules = (preset.conditions && preset.conditions.rules) ? Object.assign({}, preset.conditions.rules) : {};
    save();
    updateEditBanner();
    render();
    renderPresetList();
    if (typeof window.applyFilters === 'function') window.applyFilters();
  }

  function cancelEdit() {
    state.editingId = null;
    state.editingName = '';
    updateEditBanner();
    renderPresetList();
    updateSaveButtons();
  }

  function updateEditBanner() {
    var banner = document.getElementById('advFilterEditBanner');
    var input = document.getElementById('advFilterEditName');
    var saveBtn = document.getElementById('advFilterSaveBtn');
    var saveAsNewBtn = document.getElementById('advFilterSaveAsNewBtn');
    var saveLabel = document.getElementById('advFilterSaveLabel');
    if (!banner) return;
    if (state.editingId) {
      banner.hidden = false;
      if (input) {
        input.value = state.editingName || '';
        input.oninput = function (e) { state.editingName = e.target.value; };
      }
      if (saveBtn) saveBtn.hidden = false;
      if (saveAsNewBtn) saveAsNewBtn.hidden = false;
      if (saveLabel) saveLabel.textContent = tr('filter_preset_save_overwrite');
      // Rewire save button to overwrite in edit mode
      if (saveBtn) saveBtn.onclick = function () { overwriteEditingPreset(); };
    } else {
      banner.hidden = true;
      if (saveAsNewBtn) saveAsNewBtn.hidden = true;
      if (saveLabel) saveLabel.textContent = tr('filter_preset_save');
      if (saveBtn) saveBtn.onclick = function () { openSaveDialog(); };
    }
  }

  function overwriteEditingPreset() {
    if (!state.editingId) return;
    var name = (state.editingName || '').trim();
    if (!name) { window.alert(tr('filter_preset_name_exists')); return; }
    fetch(apiBase() + '/' + state.editingId, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: name, conditions: { rules: state.rules } }),
    }).then(function (r) { return r.json().then(function (d) { return { status: r.status, data: d }; }); })
      .then(function (res) {
        if (res.status === 409) {
          window.alert(tr('filter_preset_name_exists'));
          return;
        }
        if (res.data && res.data.ok) {
          state.editingId = null;
          state.editingName = '';
          updateEditBanner();
          loadPresets();
        }
      });
  }

  function loadAndApplyPreset(preset) {
    state.rules = (preset.conditions && preset.conditions.rules) ? preset.conditions.rules : {};
    save();
    if (typeof window.applyFilters === 'function') window.applyFilters();
    closeModal();
  }

  function confirmDeletePreset(preset) {
    if (!window.confirm(tr('filter_preset_delete_confirm'))) return;
    fetch(apiBase() + '/' + preset.id, { method: 'DELETE' })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data && data.ok) {
          if (state.editingId === preset.id) {
            state.editingId = null;
            state.editingName = '';
            updateEditBanner();
          }
          loadPresets();
        }
      });
  }

  function openSaveDialog() {
    var name = window.prompt(tr('filter_preset_save_prompt'), '');
    if (!name) return;
    createPreset(name.trim());
  }

  function openSaveAsNewDialog() {
    var defaultName = state.editingId ? '' : '';
    var name = window.prompt(tr('filter_preset_save_prompt'), defaultName);
    if (!name) return;
    createPreset(name.trim());
  }

  function createPreset(name) {
    if (!name) return;
    fetch(apiBase(), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: name, conditions: { rules: state.rules } }),
    }).then(function (r) { return r.json().then(function (data) { return { status: r.status, data: data }; }); })
      .then(function (res) {
        if (res.status === 409) {
          window.alert(tr('filter_preset_name_exists'));
          return;
        }
        if (res.data && res.data.ok) {
          // "Save as new" while editing leaves the original preset untouched
          // and exits edit mode; a normal "save" from outside edit mode has
          // no edit state to clear.
          if (state.editingId) {
            state.editingId = null;
            state.editingName = '';
            updateEditBanner();
          }
          loadPresets();
        }
      });
  }

  function updateSaveButtons() {
    var saveBtn = document.getElementById('advFilterSaveBtn');
    if (!saveBtn) return;
    if (state.editingId) {
      // Edit mode forces the button visible regardless of active count so the
      // user can save a preset whose rules they've just cleared.
      saveBtn.hidden = false;
    } else {
      saveBtn.hidden = activeCount() === 0;
    }
  }

  // ── Init ──────────────────────────────────────────────────────────────
  load();

  window.AdvancedFilter = {
    evaluate: evaluate,
    openModal: openModal,
    closeModal: closeModal,
    apply: apply,
    reset: reset,
    updateBadge: updateBadge,
    openSaveDialog: openSaveDialog,
    openSaveAsNewDialog: openSaveAsNewDialog,
    cancelEdit: cancelEdit,
    activeCount: activeCount,
    // expose for tests / debug
    _state: state,
  };

  // On DOM ready, update the badge and re-run the global filter so persisted
  // rules take effect (the inline <script> runs applyFilters() before this
  // external file has loaded, so AdvancedFilter.evaluate was a no-op there).
  function onReady() {
    updateBadge();
    if (activeCount() > 0 && typeof window.applyFilters === 'function') {
      window.applyFilters();
    }
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', onReady);
  } else {
    onReady();
  }
})();
