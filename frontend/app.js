/* ==============================================================
   高考志愿指南 — JavaScript 应用逻辑
   ============================================================== */

// API base URL — in production, change to your deployed API URL
const API_BASE = 'http://localhost:8000/api/v1';

// Province list (from API or static)
let provinceList = [];

// Pagination state
const pagination = {};

/* ------------------------------------------------------------------ */
/*  Utility Helpers                                                   */
/* ------------------------------------------------------------------ */

async function apiGet(path, params = {}) {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== '') qs.set(k, v);
  }
  const url = `${API_BASE}${path}${qs.toString() ? '?' + qs.toString() : ''}`;
  const res = await fetch(url);
  if (!res.ok) {
    const txt = await res.text().catch(() => '');
    throw new Error(`API ${res.status}: ${txt.slice(0, 200)}`);
  }
  return res.json();
}

async function apiPost(path, body) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json();
}

function $(sel) { return document.querySelector(sel); }
function $$(sel) { return document.querySelectorAll(sel); }

function showLoading(el) {
  el.innerHTML = '<tr><td colspan="99"><span class="loading"></span> 加载中...</td></tr>';
}

function showError(el, msg) {
  el.innerHTML = `<tr><td colspan="99" class="empty" style="color:var(--danger)">❌ ${escHtml(msg)}</td></tr>`;
}

function escHtml(s) {
  const d = document.createElement('div');
  d.textContent = String(s ?? '');
  return d.innerHTML;
}

function updatePagination(id, total, page, pageSize, cb) {
  const container = $(`#${id}-pagination`);
  if (!container) return;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  pagination[id] = { page, totalPages, cb };
  let html = '';
  html += `<button ${page <= 1 ? 'disabled' : ''} data-page="${page - 1}">« 上一页</button>`;
  html += `<span class="page-info">第 ${page}/${totalPages} 页 (共 ${total} 条)</span>`;
  html += `<button ${page >= totalPages ? 'disabled' : ''} data-page="${page + 1}">下一页 »</button>`;
  container.innerHTML = html;
  container.querySelectorAll('button:not(:disabled)').forEach(btn => {
    btn.addEventListener('click', () => cb(parseInt(btn.dataset.page)));
  });
}

/* ------------------------------------------------------------------ */
/*  Tab switching                                                     */
/* ------------------------------------------------------------------ */

$$('.tab').forEach(tab => {
  tab.addEventListener('click', () => {
    $$('.tab').forEach(t => t.classList.remove('active'));
    $$('.tab-content').forEach(c => c.classList.remove('active'));
    tab.classList.add('active');
    $(`#tab-${tab.dataset.tab}`).classList.add('active');
  });
});

/* ------------------------------------------------------------------ */
/*  Province loader                                                   */
/* ------------------------------------------------------------------ */

async function loadProvinces() {
  try {
    const data = await apiGet('/schools', { page_size: 1 });
    // We can't easily get distinct provinces from this endpoint alone.
    // Use a fallback list instead.
    provinceList = [
      '北京','天津','河北','山西','内蒙古','辽宁','吉林','黑龙江',
      '上海','江苏','浙江','安徽','福建','江西','山东','河南',
      '湖北','湖南','广东','广西','海南','重庆','四川','贵州',
      '云南','西藏','陕西','甘肃','青海','宁夏','新疆',
    ];
    populateSelects();
  } catch (e) {
    // fallback
    provinceList = [
      '北京','天津','河北','山西','内蒙古','辽宁','吉林','黑龙江',
      '上海','江苏','浙江','安徽','福建','江西','山东','河南',
      '湖北','湖南','广东','广西','海南','重庆','四川','贵州',
      '云南','西藏','陕西','甘肃','青海','宁夏','新疆',
    ];
    populateSelects();
  }
}

function populateSelects() {
  const selects = ['school-province', 'score-province', 'rec-province', 'rank-province'];
  selects.forEach(id => {
    const sel = $(`#${id}`);
    if (!sel) return;
    // Keep first option if it exists
    const first = sel.options[0];
    sel.innerHTML = '';
    if (first) sel.appendChild(first);
    provinceList.forEach(p => {
      const opt = document.createElement('option');
      opt.value = p;
      opt.textContent = p;
      sel.appendChild(opt);
    });
  });
}

/* ------------------------------------------------------------------ */
/*  API Health Check                                                  */
/* ------------------------------------------------------------------ */

async function checkApiHealth() {
  const el = $('#api-status');
  try {
    const res = await fetch(`${API_BASE.replace('/api/v1', '')}/health`);
    const data = await res.json();
    if (data.status === 'ok') {
      el.textContent = '✅ 连接正常';
      el.className = 'status-ok';
    } else {
      el.textContent = '⚠️ 异常';
      el.className = 'status-error';
    }
  } catch {
    el.textContent = '❌ 无法连接';
    el.className = 'status-error';
  }
}

/* ============================================================== */
/*  1. SCHOOL SEARCH                                               */
/* ============================================================== */

let schoolPage = 1;
const SCHOOL_PAGE_SIZE = 20;

async function searchSchools(page = 1) {
  schoolPage = page;
  const tbody = $('#school-tbody');
  showLoading(tbody);
  try {
    const params = {
      page,
      page_size: SCHOOL_PAGE_SIZE,
    };
    const province = $('#school-province').value;
    const level = $('#school-level').value;
    const keyword = $('#school-keyword').value.trim();
    if (province) params.province = province;
    if (level) params.level = level;
    if (keyword) params.keyword = keyword;

    const data = await apiGet('/schools', params);
    $('#school-count').textContent = `共找到 ${data.total} 所学校`;

    if (!data.items || data.items.length === 0) {
      tbody.innerHTML = '<tr><td colspan="6" class="empty">暂无数据</td></tr>';
    } else {
      tbody.innerHTML = data.items.map(s => `
        <tr>
          <td><strong>${escHtml(s.name)}</strong></td>
          <td>${escHtml(s.province || '')}</td>
          <td>${escHtml(s.city || '')}</td>
          <td>${escHtml(s.level || '')}</td>
          <td>${s.total_enrollment ? s.total_enrollment.toLocaleString() : ''}</td>
          <td><button class="btn-primary" onclick="viewSchoolScores(${s.id},'${escHtml(s.name)}')"
                  style="padding:4px 10px;font-size:0.8rem">录取分数</button></td>
        </tr>
      `).join('');
    }

    updatePagination('school', data.total, page, SCHOOL_PAGE_SIZE, searchSchools);
  } catch (e) {
    showError(tbody, e.message);
  }
}

function viewSchoolScores(id, name) {
  $('#score-school-id').value = id;
  // Switch to scores tab
  $$('.tab').forEach(t => t.classList.remove('active'));
  $$('.tab-content').forEach(c => c.classList.remove('active'));
  $$('.tab')[1].classList.add('active');
  $('#tab-scores').classList.add('active');
  searchScores();
}

$('#school-search').addEventListener('click', () => searchSchools(1));
$('#school-keyword').addEventListener('keydown', e => { if (e.key === 'Enter') searchSchools(1); });

/* ============================================================== */
/*  2. ADMISSION SCORES                                            */
/* ============================================================== */

let scorePage = 1;
const SCORE_PAGE_SIZE = 20;

async function searchScores(page = 1) {
  scorePage = page;
  const tbody = $('#score-tbody');
  showLoading(tbody);
  try {
    const params = { page, page_size: SCORE_PAGE_SIZE };
    const schoolId = $('#score-school-id').value.trim();
    const province = $('#score-province').value;
    const year = $('#score-year').value.trim();
    if (schoolId) params.school_id = parseInt(schoolId);
    if (province) params.province = province;
    if (year) params.year = parseInt(year);

    const data = await apiGet('/admission/scores', params);
    $('#score-count').textContent = `共 ${data.total} 条录取记录`;

    if (!data.items || data.items.length === 0) {
      tbody.innerHTML = '<tr><td colspan="9" class="empty">暂无数据</td></tr>';
    } else {
      tbody.innerHTML = data.items.map(s => `
        <tr>
          <td>${escHtml(s.school_name || '')}</td>
          <td>${escHtml(s.major_name || '')}</td>
          <td>${s.year || ''}</td>
          <td>${escHtml(s.province || '')}</td>
          <td>${escHtml(s.batch || '')}</td>
          <td>${s.max_score ?? ''}</td>
          <td><strong>${s.min_score ?? ''}</strong></td>
          <td>${s.avg_score ?? ''}</td>
          <td>${s.min_rank ? s.min_rank.toLocaleString() : ''}</td>
        </tr>
      `).join('');
    }

    updatePagination('score', data.total, page, SCORE_PAGE_SIZE, searchScores);
  } catch (e) {
    showError(tbody, e.message);
  }
}

$('#score-search').addEventListener('click', () => searchScores(1));
$('#score-year').addEventListener('keydown', e => { if (e.key === 'Enter') searchScores(1); });

/* ============================================================== */
/*  3. 冲稳保 RECOMMEND                                             */
/* ============================================================== */

async function recommend() {
  const tbody = $('#rec-tbody');
  showLoading(tbody);
  try {
    const score = parseInt($('#rec-score').value);
    const province = $('#rec-province').value;
    const year = parseInt($('#rec-year').value);
    const subjectType = $('#rec-subject').value;
    const major = $('#rec-major').value.trim();

    if (!score || !province) {
      tbody.innerHTML = '<tr><td colspan="7" class="empty">请填写分数并选择省份</td></tr>';
      return;
    }

    let data;
    if (major) {
      data = await apiPost('/recommend/by-major', {
        score, province, year, subject_type: subjectType, major_name: major, top_n: 30,
      });
    } else {
      data = await apiPost('/recommend/by-score', {
        score, province, year, subject_type: subjectType, top_n: 30,
      });
    }

    $('#rec-count').textContent = `推荐 ${data.total} 个结果（${major ? '含专业：' + major : '不限专业'}）`;

    if (!data.items || data.items.length === 0) {
      tbody.innerHTML = '<tr><td colspan="7" class="empty">未找到相关推荐，请尝试调整分数或省份</td></tr>';
      return;
    }

    tbody.innerHTML = data.items.map(s => {
      const probClass = s.probability === '冲' ? 'prob-chong'
        : s.probability === '稳' ? 'prob-wen'
        : s.probability === '保' ? 'prob-bao' : '';
      return `<tr>
        <td><strong>${escHtml(s.school_name)}</strong></td>
        <td>${escHtml(s.major_name)}</td>
        <td class="${probClass}">${escHtml(s.probability)}</td>
        <td>${s.min_score ?? ''}</td>
        <td>${s.avg_score ?? ''}</td>
        <td>${s.min_rank ? s.min_rank.toLocaleString() : ''}</td>
        <td>${s.year ?? ''}</td>
      </tr>`;
    }).join('');
  } catch (e) {
    showError(tbody, e.message);
  }
}

$('#rec-search').addEventListener('click', recommend);
$('#rec-score').addEventListener('keydown', e => { if (e.key === 'Enter') recommend(); });

/* ============================================================== */
/*  4. 一分一段表 (Rank Score)                                      */
/* ============================================================== */

let rankPage = 1;
const RANK_PAGE_SIZE = 20;

async function searchRank(page = 1) {
  rankPage = page;
  const tbody = $('#rank-tbody');
  const rankResult = $('#rank-result');
  showLoading(tbody);

  try {
    const score = parseInt($('#rank-score').value);
    const province = $('#rank-province').value;
    const year = parseInt($('#rank-year').value);
    const subjectType = $('#rank-subject').value;

    if (!score || !province) {
      tbody.innerHTML = '<tr><td colspan="5" class="empty">请填写分数并选择省份</td></tr>';
      return;
    }

    // Show rank conversion
    try {
      const conv = await apiGet('/rank-score/convert', { score, year, province, subject_type: subjectType });
      if (conv.rank !== null) {
        rankResult.classList.remove('hidden');
        $('#rank-value-display').textContent = conv.rank.toLocaleString();
      } else {
        rankResult.classList.add('hidden');
      }
    } catch {
      rankResult.classList.add('hidden');
    }

    // Show nearby score-rank table entries
    const params = {
      province,
      subject_type: subjectType,
      page,
      page_size: RANK_PAGE_SIZE,
    };
    if (year) params.year = year;
    if (score) params.score = score;

    const data = await apiGet('/rank-score', params);
    $('#rank-count').textContent = `找到 ${data.total} 条记录`;

    if (!data.items || data.items.length === 0) {
      // Try without score filter to show nearby entries
      delete params.score;
      const data2 = await apiGet('/rank-score', params);
      if (!data2.items || data2.items.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" class="empty">该省份暂无一分一段表数据</td></tr>';
        return;
      }
      data.items = data2.items;
      data.total = data2.total;
    }

    tbody.innerHTML = data.items.map(s => `
      <tr>
        <td><strong>${s.score}</strong></td>
        <td>${s.rank ? s.rank.toLocaleString() : ''}</td>
        <td>${s.year}</td>
        <td>${escHtml(s.province)}</td>
        <td>${escHtml(s.subject_type || '')}</td>
      </tr>
    `).join('');

    updatePagination('rank', data.total, page, RANK_PAGE_SIZE, searchRank);
  } catch (e) {
    showError(tbody, e.message);
  }
}

$('#rank-search').addEventListener('click', () => searchRank(1));
$('#rank-score').addEventListener('keydown', e => { if (e.key === 'Enter') searchRank(1); });

/* ============================================================== */
/*  Init                                                           */
/* ============================================================== */

document.addEventListener('DOMContentLoaded', () => {
  loadProvinces();
  checkApiHealth();
});
