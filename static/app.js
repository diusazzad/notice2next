/**
 * Notice2Next - Frontend Application Logic
 * Interactive Checklist, 1-Click Sample Loaders, CSV/Markdown Export, and Live Benchmark Modal
 */

document.addEventListener('DOMContentLoaded', () => {
  // DOM Elements
  const themeToggleBtn = document.getElementById('themeToggleBtn');
  const themeIcon = document.getElementById('themeIcon');
  const themeLabel = document.getElementById('themeLabel');
  
  const noticeInput = document.getElementById('noticeInput');
  const charCount = document.getElementById('charCount');
  const lineCount = document.getElementById('lineCount');
  const btnClearInput = document.getElementById('btnClearInput');
  const btnExtract = document.getElementById('btnExtract');
  const btnRunBenchmark = document.getElementById('btnRunBenchmark');
  
  const samplePills = document.querySelectorAll('.sample-pill');
  
  const traceBar = document.getElementById('traceBar');
  const traceEngineText = document.getElementById('traceEngineText');
  const traceLatency = document.getElementById('traceLatency');
  const traceGrounding = document.getElementById('traceGrounding');
  const traceIndicator = document.getElementById('traceIndicator');
  
  const emptyState = document.getElementById('emptyState');
  const loadingState = document.getElementById('loadingState');
  const infoZeroState = document.getElementById('infoZeroState');
  const checklistContainer = document.getElementById('checklistContainer');
  const itemsList = document.getElementById('itemsList');
  const summaryBadge = document.getElementById('summaryBadge');
  const summaryText = document.getElementById('summaryText');
  const exportActions = document.getElementById('exportActions');
  const evidenceDisclaimer = document.getElementById('evidenceDisclaimer');
  
  const btnDownloadCSV = document.getElementById('btnDownloadCSV');
  const btnCopyMarkdown = document.getElementById('btnCopyMarkdown');
  
  const benchmarkModal = document.getElementById('benchmarkModal');
  const benchmarkModalBody = document.getElementById('benchmarkModalBody');
  const btnCloseModal = document.getElementById('btnCloseModal');

  // Application State
  let currentItems = [];
  let samplesCache = {};

  // ==========================================
  // 1. THEME MANAGEMENT (Light / Dark)
  // ==========================================
  function updateThemeUI(theme) {
    if (theme === 'dark') {
      themeIcon.textContent = '☀️';
      themeLabel.textContent = 'Light Mode';
      themeToggleBtn.setAttribute('aria-label', 'Switch to Light Mode');
    } else {
      themeIcon.textContent = '🌙';
      themeLabel.textContent = 'Dark Mode';
      themeToggleBtn.setAttribute('aria-label', 'Switch to Dark Mode');
    }
  }

  const initialTheme = document.documentElement.getAttribute('data-theme') || 'light';
  updateThemeUI(initialTheme);

  themeToggleBtn.addEventListener('click', () => {
    const current = document.documentElement.getAttribute('data-theme') || 'light';
    const next = current === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('notice2next_theme', next);
    updateThemeUI(next);
  });

  // ==========================================
  // 2. TEXTAREA COUNTERS
  // ==========================================
  function updateCounters() {
    const text = noticeInput.value;
    charCount.textContent = `${text.length} characters`;
    const lines = text.length === 0 ? 0 : text.split('\n').length;
    lineCount.textContent = `${lines} lines`;
  }

  noticeInput.addEventListener('input', updateCounters);

  btnClearInput.addEventListener('click', () => {
    noticeInput.value = '';
    updateCounters();
    resetChecklistView();
    samplePills.forEach(p => p.classList.remove('active'));
  });

  // ==========================================
  // 3. SAMPLE LOADER & CACHE
  // ==========================================
  async function loadSamples() {
    try {
      const res = await fetch('/api/samples');
      if (res.ok) {
        const data = await res.json();
        data.samples.forEach(s => {
          samplesCache[s.id] = s;
        });

        // Set Case 1 as default initial text
        if (samplesCache['case_1_complete'] && !noticeInput.value.trim()) {
          noticeInput.value = samplesCache['case_1_complete'].text;
          updateCounters();
        }
      }
    } catch (err) {
      console.warn('Could not fetch samples dynamically:', err);
    }
  }

  loadSamples();

  samplePills.forEach(pill => {
    pill.addEventListener('click', () => {
      samplePills.forEach(p => p.classList.remove('active'));
      pill.classList.add('active');

      const sampleId = pill.getAttribute('data-sample');
      if (samplesCache[sampleId]) {
        noticeInput.value = samplesCache[sampleId].text;
        updateCounters();
        runExtraction();
      }
    });
  });

  // ==========================================
  // 4. ACTION EXTRACTION & RENDERING
  // ==========================================
  function resetChecklistView() {
    emptyState.style.display = 'block';
    loadingState.style.display = 'none';
    infoZeroState.style.display = 'none';
    checklistContainer.style.display = 'none';
    exportActions.style.display = 'none';
    evidenceDisclaimer.style.display = 'none';
    traceEngineText.textContent = 'Engine: Ready';
    traceLatency.textContent = 'Latency: —';
    traceGrounding.textContent = 'Grounding: —';
    traceIndicator.style.color = '#94a3b8';
    currentItems = [];
  }

  async function runExtraction() {
    const text = noticeInput.value.trim();
    if (!text) {
      alert('Please enter or select a school circular to extract actions.');
      return;
    }

    // UI Loading State
    emptyState.style.display = 'none';
    infoZeroState.style.display = 'none';
    checklistContainer.style.display = 'none';
    exportActions.style.display = 'none';
    evidenceDisclaimer.style.display = 'none';
    loadingState.style.display = 'block';

    btnExtract.disabled = true;
    btnExtract.innerHTML = `<span class="btn-icon">⏳</span> Parsing with Gemma 2...`;

    try {
      const res = await fetch('/api/extract', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, verify_quotes: true })
      });

      if (!res.ok) {
        throw new Error(`Server returned status ${res.status}`);
      }

      const data = await res.json();
      loadingState.style.display = 'none';
      btnExtract.disabled = false;
      btnExtract.innerHTML = `<span class="btn-icon">⚡</span> Extract Action Checklist`;

      // Update Trace Bar
      if (data.live_model_called) {
        traceEngineText.innerHTML = `<strong>Engine:</strong> <span style="color: #9333ea; font-weight: 700;">⚡ ${escapeHtml(data.engine)}</span>`;
        traceIndicator.style.color = '#a855f7';
      } else {
        traceEngineText.innerHTML = `<strong>Engine:</strong> <span style="color: #059669; font-weight: 700;">🛡️ ${escapeHtml(data.engine)}</span>`;
        traceIndicator.style.color = '#10b981';
      }
      traceLatency.textContent = `Latency: ${data.latency_ms}ms`;
      traceGrounding.textContent = `Verbatim Grounding: ${data.summary.grounding_rate}%`;

      currentItems = data.items || [];

      if (currentItems.length === 0) {
        // Purely informational notice
        infoZeroState.style.display = 'block';
        return;
      }

      // Render Items
      renderChecklist(currentItems, data.summary);
    } catch (err) {
      loadingState.style.display = 'none';
      btnExtract.disabled = false;
      btnExtract.innerHTML = `<span class="btn-icon">⚡</span> Extract Action Checklist`;
      alert(`Error during extraction: ${err.message}. Please check server health.`);
      emptyState.style.display = 'block';
    }
  }

  function renderChecklist(items, summary) {
    itemsList.innerHTML = '';

    summaryText.textContent = `${summary.total_items} action(s) extracted • Verbatim quotes verified for ${summary.verified_count} of ${summary.total_items} item(s) (${summary.flagged_count} flagged for review)`;

    items.forEach((it, index) => {
      const card = document.createElement('div');
      card.className = `task-item-card ${it.is_completed ? 'completed' : ''}`;
      card.id = `item-card-${index}`;

      const isDeadlineNotStated = it.deadline.toUpperCase().includes('NOT STATED');
      const isQuoteVerified = it.quote_verified && it.validation_status === 'VERIFIED_QUOTE_GROUNDED';
      const badgeText = it.validation_badge_text || (isQuoteVerified ? '✓ Verbatim Quote Found' : '⚠️ Flagged for Review');

      card.innerHTML = `
        <div class="task-item-header">
          <input type="checkbox" class="task-checkbox" data-index="${index}" ${it.is_completed ? 'checked' : ''} aria-label="Mark task complete">
          <div class="task-title-group">
            <input type="text" class="task-title-input" data-index="${index}" value="${escapeHtml(it.action)}" title="Click to edit task description">
          </div>
        </div>

        <div class="task-meta-row">
          <span class="meta-pill meta-assignee" title="Responsible Group in Circular">
            👤 ${escapeHtml(it.assignee)}
          </span>
          <span class="meta-pill meta-deadline ${isDeadlineNotStated ? 'not-stated' : ''}" title="Extracted Task Deadline">
            📅 ${escapeHtml(it.deadline)}
          </span>
          ${it.fee_or_docs && it.fee_or_docs !== 'NOT STATED' ? `
            <span class="meta-pill meta-fee-docs" title="Required Document or Fee">
              📄 ${escapeHtml(it.fee_or_docs)}
            </span>
          ` : ''}
          <span class="meta-pill ${isQuoteVerified ? 'meta-status-verified' : 'meta-status-warning'}" title="${escapeHtml(it.validation_notes)}">
            ${escapeHtml(badgeText)}
          </span>
          <span class="meta-pill meta-action-review" title="Exact quote confirms text presence; semantic alignment requires teacher verification.">
            🔍 Action Intent (Teacher Review Needed)
          </span>
        </div>

        <div class="quote-box">
          <div class="quote-label">
            <span>❝</span> Verbatim Evidence Quote
          </div>
          <div class="quote-text">"${escapeHtml(it.source_quote)}"</div>
          <div class="validation-note">${escapeHtml(it.validation_notes)}</div>
        </div>
      `;

      itemsList.appendChild(card);
    });

    // Attach Event Listeners to Checkboxes and Editable Title
    document.querySelectorAll('.task-checkbox').forEach(cb => {
      cb.addEventListener('change', (e) => {
        const idx = parseInt(e.target.getAttribute('data-index'), 10);
        currentItems[idx].is_completed = e.target.checked;
        const card = document.getElementById(`item-card-${idx}`);
        if (e.target.checked) {
          card.classList.add('completed');
        } else {
          card.classList.remove('completed');
        }
      });
    });

    document.querySelectorAll('.task-title-input').forEach(inp => {
      inp.addEventListener('input', (e) => {
        const idx = parseInt(e.target.getAttribute('data-index'), 10);
        currentItems[idx].action = e.target.value;
      });
    });

    checklistContainer.style.display = 'block';
    exportActions.style.display = 'flex';
    evidenceDisclaimer.style.display = 'flex';
  }

  btnExtract.addEventListener('click', runExtraction);

  // ==========================================
  // 5. EXPORT UTILITIES (CSV & Markdown)
  // ==========================================
  btnDownloadCSV.addEventListener('click', async () => {
    if (currentItems.length === 0) return;

    try {
      const res = await fetch('/api/export/csv', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ items: currentItems })
      });

      if (!res.ok) throw new Error('Failed to export CSV');

      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'notice2next_action_checklist.csv';
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      alert(`Could not download CSV: ${err.message}`);
    }
  });

  btnCopyMarkdown.addEventListener('click', () => {
    if (currentItems.length === 0) return;

    let md = '# 📋 School Circular Action Checklist\n';
    md += '| Status | Action Item | Assigned To | Deadline | Evidence Quote |\n';
    md += '| :---: | :--- | :--- | :--- | :--- |\n';

    currentItems.forEach(it => {
      const check = it.is_completed ? '[x]' : '[ ]';
      const action = it.action.replace(/\|/g, '-');
      const assignee = it.assignee.replace(/\|/g, '-');
      const deadline = it.deadline.replace(/\|/g, '-');
      const quote = it.source_quote.replace(/\|/g, '-').replace(/\n/g, ' ');
      md += `| ${check} | **${action}** | \`${assignee}\` | **${deadline}** | *"${quote}"* |\n`;
    });

    navigator.clipboard.writeText(md).then(() => {
      const origText = btnCopyMarkdown.innerHTML;
      btnCopyMarkdown.innerHTML = '✓ Copied!';
      setTimeout(() => {
        btnCopyMarkdown.innerHTML = origText;
      }, 2000);
    });
  });

  // ==========================================
  // 6. LIVE BENCHMARK MODAL
  // ==========================================
  btnRunBenchmark.addEventListener('click', async () => {
    benchmarkModal.style.display = 'flex';
    benchmarkModalBody.innerHTML = `
      <div class="spinner"></div>
      <p style="text-align: center; margin-top: 1rem;">Executing live benchmark pipeline across 6 synthetic test cases...</p>
    `;

    try {
      const res = await fetch('/api/benchmark');
      if (!res.ok) throw new Error(`Benchmark returned status ${res.status}`);

      const data = await res.json();

      const isLive = data.live_model_called;
      let tableHtml = `
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem; flex-wrap: wrap; gap: 0.5rem;">
          <div>
            <strong>Pass Rate:</strong> <span style="font-size: 1.15rem; color: #10b981; font-weight: 800;">${data.pass_rate_percentage}%</span>
            (${data.passed_cases}/${data.total_test_cases} cases passed)
          </div>
          <div style="font-size: 0.8rem; color: var(--text-subtle);">
            <strong>Engine Evaluated:</strong> <span style="font-weight: 700; color: ${isLive ? '#9333ea' : '#059669'};">${isLive ? '⚡ ' : '🛡️ '}${escapeHtml(data.engine_evaluated)}</span>
          </div>
        </div>
        <div style="font-size: 0.78rem; color: var(--text-muted); margin-bottom: 1rem;">
          Evaluating exact task counts, role grounding, explicit NOT STATED enforcement, and date-trap rejections.
        </div>

        <table class="benchmark-table">
          <thead>
            <tr>
              <th>Scenario ID</th>
              <th>Language</th>
              <th>Result</th>
              <th>Tasks Found</th>
              <th>Grounding</th>
              <th>Evaluation Notes</th>
            </tr>
          </thead>
          <tbody>
      `;

      data.test_results.forEach(r => {
        tableHtml += `
          <tr>
            <td><strong>${escapeHtml(r.case_id)}</strong></td>
            <td><code>${escapeHtml(r.language)}</code></td>
            <td class="${r.passed ? 'benchmark-pass' : 'benchmark-fail'}">
              ${r.passed ? '✓ PASSED' : '✗ FAILED'}
            </td>
            <td>${r.items_extracted} (exp: ${r.expected_count})</td>
            <td><code>${escapeHtml(r.grounding_rate)}</code></td>
            <td style="font-size: 0.78rem; color: var(--text-muted);">${escapeHtml(r.notes)}</td>
          </tr>
        `;
      });

      tableHtml += `
          </tbody>
        </table>

        <div style="margin-top: 1.25rem; font-size: 0.8rem; color: var(--text-subtle); line-height: 1.5; border-top: 1px solid var(--border-color); padding-top: 0.85rem;">
          <em>${escapeHtml(data.transparency_statement)}</em>
        </div>
      `;

      benchmarkModalBody.innerHTML = tableHtml;
    } catch (err) {
      benchmarkModalBody.innerHTML = `<p style="color: #ef4444;">Failed to run benchmark: ${err.message}</p>`;
    }
  });

  btnCloseModal.addEventListener('click', () => {
    benchmarkModal.style.display = 'none';
  });

  benchmarkModal.addEventListener('click', (e) => {
    if (e.target === benchmarkModal) {
      benchmarkModal.style.display = 'none';
    }
  });

  // Helper
  function escapeHtml(str) {
    if (!str) return '';
    return str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }
});
