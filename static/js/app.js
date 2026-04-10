/* ─── IRIS — Main JavaScript ─────────────────────────────────────────────── */

// ─── Theme ────────────────────────────────────────────────────────────────

function toggleTheme() {
  const html = document.documentElement;
  const current = html.getAttribute('data-theme');
  const next = current === 'dark' ? 'light' : 'dark';
  html.setAttribute('data-theme', next);
  localStorage.setItem('iris-theme', next);
  updateThemeIcon();
}

function updateThemeIcon() {
  const icon = document.getElementById('theme-icon');
  if (!icon) return;
  const theme = document.documentElement.getAttribute('data-theme');
  icon.textContent = theme === 'dark' ? 'light_mode' : 'dark_mode';
}

// ─── Sidebar (mobile) ─────────────────────────────────────────────────────

function openSidebar() {
  document.getElementById('sidebar').classList.add('open');
  document.getElementById('sidebar-overlay').classList.add('show');
}

function closeSidebar() {
  document.getElementById('sidebar').classList.remove('open');
  document.getElementById('sidebar-overlay').classList.remove('show');
}

// ─── File label ───────────────────────────────────────────────────────────

function updateFileLabel(input) {
  const label = document.getElementById('file-label');
  if (!label) return;
  if (input.files.length === 0) {
    label.textContent = 'Keine Datei ausgewählt';
  } else if (input.files.length === 1) {
    label.textContent = input.files[0].name;
  } else {
    label.textContent = `${input.files.length} Dateien ausgewählt`;
  }
}

// ─── Ticket Form (create + edit) ──────────────────────────────────────────

function initTicketForm(existingLinkedIds) {
  // Flatpickr date picker
  const dateInput = document.getElementById('event-date-input');
  if (dateInput) {
    flatpickr(dateInput, {
      enableTime: true,
      dateFormat: 'Y-m-d H:i',
      defaultDate: dateInput.value || new Date(),
      time_24hr: true,
    });
  }

  // Dynamic subcategory
  const catSelect = document.getElementById('category-select');
  if (catSelect) {
    catSelect.addEventListener('change', loadSubcategories);
    // Trigger on load for edit form
    setTimeout(() => loadSubcategories.call(catSelect), 200);
  }

  // Preset tag chips
  loadPresetTagChips();

  // Linked ticket autocomplete
  initLinkedAutocomplete(existingLinkedIds || []);
}

async function loadSubcategories() {
  const category = this.value || document.getElementById('category-select')?.value;
  const subSelect = document.getElementById('subcategory-select');
  if (!subSelect) return;

  try {
    const resp = await fetch(`/api/subcategories?category=${encodeURIComponent(category)}`);
    const subs = await resp.json();

    // Clear and repopulate
    subSelect.innerHTML = '<mdui-menu-item value="">— Keine —</mdui-menu-item>';
    subs.forEach(s => {
      const item = document.createElement('mdui-menu-item');
      item.value = s.value;
      item.textContent = s.label;
      subSelect.appendChild(item);
    });

    subSelect.disabled = subs.length === 0;
    if (subs.length === 0) subSelect.value = '';
  } catch (e) {
    console.error('Subcategory load failed', e);
  }
}

async function loadPresetTagChips() {
  const container = document.getElementById('preset-tags');
  if (!container) return;

  try {
    const resp = await fetch('/api/tags');
    const tags = await resp.json();

    container.innerHTML = '';
    tags.forEach(tag => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'tag-chip';
      btn.textContent = tag.name;
      btn.style.background = tag.color + '33';
      btn.style.color = tag.color;
      btn.style.border = `1px solid ${tag.color}66`;
      btn.addEventListener('click', () => appendTag(tag.name));
      container.appendChild(btn);
    });
  } catch (e) {
    console.error('Tag chips load failed', e);
  }
}

function appendTag(name) {
  const field = document.getElementById('tags-input');
  if (!field) return;
  const existing = (field.value || '').split(',').map(t => t.trim()).filter(Boolean);
  if (!existing.includes(name)) {
    field.value = [...existing, name].join(', ');
  }
}

// ─── Linked Ticket Autocomplete ───────────────────────────────────────────

let linkedTickets = {};
let searchTimeout;

function initLinkedAutocomplete(existingIds) {
  const searchInput = document.getElementById('linked-search-input');
  const dropdown = document.getElementById('linked-dropdown');
  const chipsContainer = document.getElementById('linked-chips');
  const hiddenInput = document.getElementById('linked-tickets-value');

  if (!searchInput) return;

  // Pre-populate from existing linked tickets (edit form)
  existingIds.forEach(id => {
    fetch(`/api/tickets/search?q=${id}`)
      .then(r => r.json())
      .then(results => {
        const t = results.find(t => t.id == id);
        if (t) addLinkedTicket(t);
      });
  });

  searchInput.addEventListener('input', (e) => {
    clearTimeout(searchTimeout);
    const q = e.target.value.trim();
    if (q.length < 1) {
      dropdown.style.display = 'none';
      return;
    }
    searchTimeout = setTimeout(async () => {
      try {
        const resp = await fetch(`/api/tickets/search?q=${encodeURIComponent(q)}`);
        const tickets = await resp.json();
        renderLinkedDropdown(tickets, dropdown, searchInput);
      } catch (e) {}
    }, 300);
  });

  document.addEventListener('click', (e) => {
    if (!searchInput.contains(e.target) && !dropdown.contains(e.target)) {
      dropdown.style.display = 'none';
    }
  });

  function renderLinkedDropdown(tickets, dropdown, searchInput) {
    dropdown.innerHTML = '';
    if (tickets.length === 0) {
      dropdown.style.display = 'none';
      return;
    }
    tickets.forEach(t => {
      if (linkedTickets[t.id]) return;
      const item = document.createElement('div');
      item.className = 'autocomplete-item';
      item.textContent = `#${t.id} — ${t.title}`;
      item.addEventListener('click', () => {
        addLinkedTicket(t);
        searchInput.value = '';
        dropdown.style.display = 'none';
      });
      dropdown.appendChild(item);
    });
    dropdown.style.display = dropdown.children.length ? 'block' : 'none';
  }

  function addLinkedTicket(ticket) {
    if (linkedTickets[ticket.id]) return;
    linkedTickets[ticket.id] = ticket;
    updateLinkedValue();
    renderLinkedChips();
  }

  function removeLinkedTicket(id) {
    delete linkedTickets[id];
    updateLinkedValue();
    renderLinkedChips();
  }

  function updateLinkedValue() {
    hiddenInput.value = Object.keys(linkedTickets).join(',');
  }

  function renderLinkedChips() {
    chipsContainer.innerHTML = '';
    Object.values(linkedTickets).forEach(t => {
      const chip = document.createElement('span');
      chip.className = 'linked-chip';
      chip.innerHTML = `#${t.id} — ${t.title} <button type="button" onclick="removeLinked(${t.id})" title="Entfernen">×</button>`;
      chipsContainer.appendChild(chip);
    });
  }

  // Expose for onclick handler
  window.removeLinked = removeLinkedTicket;
}

// ─── Filters (ticket list) ────────────────────────────────────────────────

function applyFilters() {
  const params = new URLSearchParams();
  const keys = ['category', 'status', 'priority', 'mood'];
  keys.forEach(key => {
    const el = document.getElementById(`filter-${key}`);
    const val = el ? el.value : '';
    if (val) params.set(key, val);
  });
  const q = document.getElementById('search-input');
  if (q && q.value.trim()) params.set('q', q.value.trim());
  const df = document.getElementById('date-from');
  const dt = document.getElementById('date-to');
  if (df && df.value) params.set('date_from', df.value);
  if (dt && dt.value) params.set('date_to', dt.value);
  window.location.search = params.toString();
}

function clearFilters() {
  window.location.search = '';
}

// ─── Inline Status Update ─────────────────────────────────────────────────

function initStatusUpdate(ticketId) {
  const select = document.getElementById('status-select');
  if (!select) return;
  select.addEventListener('change', async (e) => {
    try {
      const resp = await fetch(`/tickets/${ticketId}/status`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: e.target.value }),
      });
      const data = await resp.json();
      if (data.ok) {
        showToast(`Status: ${data.status_label}`);
        const badge = document.getElementById('status-badge');
        if (badge) {
          badge.className = `status-badge status-${data.status}`;
          badge.textContent = data.status_label;
        }
      }
    } catch (e) {
      showToast('Fehler beim Speichern');
    }
  });
}

// ─── Delete Confirmation ──────────────────────────────────────────────────

function confirmDelete(ticketId, title) {
  if (confirm(`"${title}" wirklich löschen? Diese Aktion kann nicht rückgängig gemacht werden.`)) {
    document.getElementById(`delete-form-${ticketId}`).submit();
  }
}

// ─── Settings: Tag CRUD ───────────────────────────────────────────────────

async function addTag() {
  const nameInput = document.getElementById('new-tag-name');
  const colorInput = document.getElementById('new-tag-color');
  const name = nameInput ? nameInput.value.trim() : '';
  const color = colorInput ? colorInput.value : '#6750A4';
  if (!name) return;

  try {
    const resp = await fetch('/settings/tags', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, color }),
    });
    const data = await resp.json();
    if (data.ok) {
      location.reload();
    } else {
      showToast(data.error || 'Fehler');
    }
  } catch (e) {
    showToast('Netzwerkfehler');
  }
}

async function deleteTag(id) {
  if (!confirm('Tag löschen?')) return;
  try {
    const resp = await fetch(`/settings/tags/${id}`, { method: 'DELETE' });
    const data = await resp.json();
    if (data.ok) location.reload();
  } catch (e) {
    showToast('Fehler beim Löschen');
  }
}

function showToast(msg) {
  const el = document.createElement('div');
  el.textContent = msg;
  el.style.cssText = `position:fixed;bottom:24px;left:50%;transform:translateX(-50%);background:var(--mdui-color-inverse-surface, #313033);color:var(--mdui-color-inverse-on-surface, #f4eff4);padding:12px 20px;border-radius:8px;font-size:14px;z-index:9999;box-shadow:0 4px 12px rgba(0,0,0,0.3);`;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 2500);
}

// ─── Init on load ─────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  updateThemeIcon();

  // Init flatpickr for filter date inputs
  const df = document.getElementById('date-from');
  const dt = document.getElementById('date-to');
  if (df) flatpickr(df, { dateFormat: 'Y-m-d', allowInput: true });
  if (dt) flatpickr(dt, { dateFormat: 'Y-m-d', allowInput: true });

  // Enter key on search input applies filters
  const searchInput = document.getElementById('search-input');
  if (searchInput) {
    searchInput.addEventListener('keydown', e => {
      if (e.key === 'Enter') applyFilters();
    });
  }
});
