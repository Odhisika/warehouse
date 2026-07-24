/* ── Nexus Warehouse – JS ── */

// ─── Mobile sidebar toggle ───
function toggleSidebar() {
  const sidebar = document.getElementById('sidebar');
  const overlay = document.getElementById('sidebar-overlay');
  if (!sidebar) return;
  sidebar.classList.toggle('open');
  if (overlay) overlay.classList.toggle('open');
}
// Close sidebar on nav click (mobile)
document.addEventListener('click', function (e) {
  const link = e.target.closest('.sidebar a');
  if (!link || window.innerWidth > 768) return;
  const sidebar = document.getElementById('sidebar');
  const overlay = document.getElementById('sidebar-overlay');
  if (sidebar) sidebar.classList.remove('open');
  if (overlay) overlay.classList.remove('open');
});

// ─── Sidebar settings toggle ───
function toggleSettings() {
  const sub   = document.getElementById('settings-sub');
  const caret = document.getElementById('settings-caret');
  if (!sub) return;
  const open = sub.classList.toggle('open');
  if (caret) caret.classList.toggle('open', open);
}

// ─── Accordion (Returns) ───
document.addEventListener('click', function (e) {
  const header = e.target.closest('.accordion-header');
  if (!header) return;
  const accordion = header.closest('.accordion');
  // close siblings
  document.querySelectorAll('.accordion.open').forEach(a => {
    if (a !== accordion) a.classList.remove('open');
  });
  accordion.classList.toggle('open');
});

// ─── Roles sidebar ───
document.addEventListener('click', function (e) {
  const item = e.target.closest('.role-item');
  if (!item) return;
  document.querySelectorAll('.role-item').forEach(r => r.classList.remove('active'));
  item.classList.add('active');
});

// ─── Modal helpers ───
function openModal(id) {
  const el = document.getElementById(id);
  if (el) el.classList.add('open');
}
function closeModal(id) {
  const el = document.getElementById(id);
  if (el) el.classList.remove('open');
}
// close on backdrop click
document.addEventListener('click', function (e) {
  if (e.target.classList.contains('modal-overlay')) {
    e.target.classList.remove('open');
  }
});

// ─── Auto-dismiss toasts ───
document.addEventListener('DOMContentLoaded', function () {
  document.querySelectorAll('.toast').forEach(function (t) {
    setTimeout(function () {
      t.style.opacity = '0';
      t.style.transition = 'opacity .4s';
      setTimeout(() => t.remove(), 400);
    }, 4000);
  });
});

// ─── Receiving: add row ───
let recvRowCount = 1;
function addReceivingRow() {
  recvRowCount++;
  const tbody = document.getElementById('recv-tbody');
  if (!tbody) return;
  const tr = document.createElement('tr');
  tr.innerHTML = `
    <td><input type="checkbox" class="checkbox" name="item_check_${recvRowCount}"></td>
    <td style="position:relative;min-width:200px">
      <input type="text" class="form-control product-search" data-row="${recvRowCount}" placeholder="Search SKU or name…" autocomplete="off" style="width:100%">
      <input type="hidden" name="product_${recvRowCount}" value="">
    </td>
    <td><input name="batch_${recvRowCount}" class="form-control" type="text" placeholder="B-XXX" style="width:90px"></td>
    <td><input name="expiry_${recvRowCount}" class="form-control" type="date" style="width:140px"></td>
    <td><input name="qty_${recvRowCount}" class="form-control" type="number" value="0" min="0" style="width:80px" oninput="updateReceivingTotals()"></td>
    <td><input name="cost_${recvRowCount}" class="form-control" type="number" step="0.01" value="0.00" style="width:100px" oninput="updateReceivingTotals()"></td>
    <td><select name="condition_${recvRowCount}" class="form-control" style="width:120px">
          <option>Pristine</option><option>Good</option><option>Damaged</option></select></td>
    <td><button type="button" class="btn btn-sm" style="color:var(--red);background:none;border:none;cursor:pointer;" onclick="this.closest('tr').remove();updateReceivingTotals()">
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3,6 5,6 21,6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/></svg>
    </button></td>`;
  tbody.appendChild(tr);
  const newInput = tr.querySelector('.product-search');
  if (newInput && typeof initProductSearch === 'function') initProductSearch(newInput);
}

function updateReceivingTotals() {
  let units = 0, value = 0;
  document.querySelectorAll('#recv-tbody tr').forEach(tr => {
    const qty  = parseFloat(tr.querySelector('[name^="qty_"]')?.value)  || 0;
    const cost = parseFloat(tr.querySelector('[name^="cost_"]')?.value) || 0;
    units += qty; value += qty * cost;
  });
  const u = document.getElementById('recv-total-units');
  const v = document.getElementById('recv-total-value');
  if (u) u.textContent = units + ' Units';
  if (v) v.textContent = (window.CURRENCY_SYM || '$') + value.toFixed(2);
}

// ─── Dispatch: qty update → recalc totals ───
function updateDispatchTotals() {
  let subtotal = 0;
  document.querySelectorAll('.manifest-row').forEach(tr => {
    const qty   = parseFloat(tr.querySelector('.manifest-qty')?.value)  || 0;
    const price = parseFloat(tr.dataset.price) || 0;
    const line  = qty * price;
    const lineEl = tr.querySelector('.manifest-line');
    if (lineEl) lineEl.textContent = (window.CURRENCY_SYM || '$') + line.toFixed(2);
    subtotal += line;
  });
  const handling = parseFloat(document.getElementById('handling-fee')?.value) || 0;
  const taxRate  = parseFloat(document.getElementById('tax-rate')?.value) || 15;
  const tax      = subtotal * taxRate / 100;
  const grand    = subtotal + handling + tax;
  const cs = window.CURRENCY_SYM || '$';
  const setEl = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val; };
  setEl('dispatch-subtotal', cs + subtotal.toFixed(2));
  setEl('dispatch-handling', cs + handling.toFixed(2));
  setEl('dispatch-tax',      cs + tax.toFixed(2));
  setEl('dispatch-grand',    cs + grand.toFixed(2));
}

// ─── Password visibility toggle ───
function togglePassword(inputId, btn) {
  var input = document.getElementById(inputId);
  if (!input) return;
  var isPassword = input.type === 'password';
  input.type = isPassword ? 'text' : 'password';
  var open = btn.querySelector('.eye-open');
  var closed = btn.querySelector('.eye-closed');
  if (open && closed) {
    open.style.display = isPassword ? 'none' : '';
    closed.style.display = isPassword ? '' : 'none';
  }
}

// ─── Theme toggle ───
document.addEventListener('click', function (e) {
  const btn = e.target.closest('.theme-btn');
  if (!btn) return;
  document.querySelectorAll('.theme-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
});

// ─── Dropdowns: close on outside click ───
document.addEventListener('click', function (e) {
  const branchDD = document.getElementById('branch-dropdown');
  if (!branchDD || branchDD.classList.contains('open')) {
    if (!e.target.closest('.branch-pill') && !e.target.closest('#branch-dropdown')) {
      if (branchDD) branchDD.classList.remove('open');
    }
  }
  const notifDD = document.getElementById('notif-dropdown');
  if (notifDD && notifDD.classList.contains('open')) {
    if (!e.target.closest('.bell-wrap') && !e.target.closest('#notif-dropdown')) {
      notifDD.classList.remove('open');
    }
  }
  const profileDD = document.getElementById('profile-dropdown');
  if (profileDD && profileDD.classList.contains('open')) {
    if (!e.target.closest('#profile-wrap')) {
      profileDD.classList.remove('open');
    }
  }
});

// ─── Table select all ───
document.addEventListener('change', function (e) {
  if (e.target.id === 'select-all') {
    const checked = e.target.checked;
    document.querySelectorAll('.row-check').forEach(c => c.checked = checked);
  }
});
