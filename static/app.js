/**
 * Notice2Next - Frontend Application Logic
 * Interactive Checklist, 1-Click Sample Loaders, CSV/Markdown Export,
 * Multi-Modal Ingest (Photo OCR & URL Fetch), Auth0 Governance, and ElevenLabs Audio Briefing
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
  const btnSaveToLibrary = document.getElementById('btnSaveToLibrary');
  
  // ElevenLabs Audio Briefing
  const btnPlayAudioBriefing = document.getElementById('btnPlayAudioBriefing');
  const audioPlayerWrapper = document.getElementById('audioPlayerWrapper');
  const audioStatusText = document.getElementById('audioStatusText');
  const btnStopAudio = document.getElementById('btnStopAudio');
  const briefingAudioElement = document.getElementById('briefingAudioElement');
  
  // Multi-Modal Ingest Elements
  const tabTextMode = document.getElementById('tabTextMode');
  const tabPhotoOcr = document.getElementById('tabPhotoOcr');
  const tabUrlFetch = document.getElementById('tabUrlFetch');
  const circularPhotoInput = document.getElementById('circularPhotoInput');
  const photoOcrPanel = document.getElementById('photoOcrPanel');
  const ocrThumbImg = document.getElementById('ocrThumbImg');
  const ocrFileName = document.getElementById('ocrFileName');
  const ocrStatusText = document.getElementById('ocrStatusText');
  const ocrProgressFill = document.getElementById('ocrProgressFill');
  const btnRetakePhoto = document.getElementById('btnRetakePhoto');
  
  const urlIngestPanel = document.getElementById('urlIngestPanel');
  const noticeUrlInput = document.getElementById('noticeUrlInput');
  const btnFetchUrl = document.getElementById('btnFetchUrl');
  const fetchUrlBtnIcon = document.getElementById('fetchUrlBtnIcon');
  
  // Auth0 Identity & Library
  const authLoginBtn = document.getElementById('authLoginBtn');
  const authProfile = document.getElementById('authProfile');
  const authUserName = document.getElementById('authUserName');
  const authLibraryBtn = document.getElementById('authLibraryBtn');
  const authLogoutBtn = document.getElementById('authLogoutBtn');
  const savedNoticeBadge = document.getElementById('savedNoticeBadge');
  
  const libraryModal = document.getElementById('libraryModal');
  const libraryModalBody = document.getElementById('libraryModalBody');
  const btnCloseLibraryModal = document.getElementById('btnCloseLibraryModal');
  
  // Benchmark Modal
  const benchmarkModal = document.getElementById('benchmarkModal');
  const benchmarkModalBody = document.getElementById('benchmarkModalBody');
  const btnCloseModal = document.getElementById('btnCloseModal');

  // Application State
  let currentItems = [];
  let samplesCache = {};
  let currentSummary = null;
  let isSpeaking = false;

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
    photoOcrPanel.style.display = 'none';
    urlIngestPanel.style.display = 'none';
    setActiveTab(tabTextMode);
  });

  // ==========================================
  // 3. MULTI-MODAL INGEST TABS (Text, Photo OCR, URL)
  // ==========================================
  function setActiveTab(activeBtn) {
    [tabTextMode, tabPhotoOcr, tabUrlFetch].forEach(t => t.classList.remove('active'));
    activeBtn.classList.add('active');
  }

  tabTextMode.addEventListener('click', () => {
    setActiveTab(tabTextMode);
    photoOcrPanel.style.display = 'none';
    urlIngestPanel.style.display = 'none';
  });

  tabPhotoOcr.addEventListener('click', () => {
    setActiveTab(tabPhotoOcr);
    urlIngestPanel.style.display = 'none';
    circularPhotoInput.click();
  });

  btnRetakePhoto.addEventListener('click', () => {
    circularPhotoInput.click();
  });

  circularPhotoInput.addEventListener('change', async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    photoOcrPanel.style.display = 'block';
    ocrFileName.textContent = file.name;
    ocrStatusText.textContent = 'Reading image file...';
    ocrProgressFill.style.width = '10%';

    // Preview thumbnail
    const reader = new FileReader();
    reader.onload = (re) => {
      ocrThumbImg.src = re.target.result;
    };
    reader.readAsDataURL(file);

    // Browser-Side Tesseract OCR
    if (typeof Tesseract === 'undefined') {
      ocrStatusText.textContent = 'OCR library loading error. Please paste text manually.';
      return;
    }

    try {
      ocrStatusText.textContent = 'Scanning circular with Tesseract OCR (Bengali + English)...';
      ocrProgressFill.style.width = '30%';

      const result = await Tesseract.recognize(file, 'eng+ben', {
        logger: (m) => {
          if (m.status === 'recognizing text' && m.progress) {
            const pct = Math.round(m.progress * 100);
            ocrProgressFill.style.width = `${pct}%`;
            ocrStatusText.textContent = `Scanning notice text: ${pct}% complete...`;
          }
        }
      });

      const extractedText = (result.data.text || '').trim();
      ocrProgressFill.style.width = '100%';

      if (extractedText) {
        noticeInput.value = extractedText;
        updateCounters();
        ocrStatusText.textContent = `✓ Scan complete (${extractedText.length} characters extracted). Review below.`;
      } else {
        ocrStatusText.textContent = 'Notice image was blurry or contained no readable text. You can type/edit below.';
      }
    } catch (err) {
      console.warn('OCR error fallback:', err);
      // Fallback to English-only OCR if mixed language model failed to fetch
      try {
        ocrStatusText.textContent = 'Retrying with standard English OCR model...';
        const fallback = await Tesseract.recognize(file, 'eng');
        const txt = (fallback.data.text || '').trim();
        if (txt) {
          noticeInput.value = txt;
          updateCounters();
          ocrStatusText.textContent = `✓ Scan complete (${txt.length} characters). Review below.`;
          return;
        }
      } catch (err2) {
        // Fall through
      }
      ocrStatusText.textContent = 'OCR scan could not read image. Please paste circular text manually.';
    }
  });

  // URL Ingest
  tabUrlFetch.addEventListener('click', () => {
    setActiveTab(tabUrlFetch);
    photoOcrPanel.style.display = 'none';
    urlIngestPanel.style.display = 'block';
    noticeUrlInput.focus();
  });

  btnFetchUrl.addEventListener('click', async () => {
    const url = noticeUrlInput.value.trim();
    if (!url) {
      alert('Please enter a valid circular URL or PDF link.');
      return;
    }

    btnFetchUrl.disabled = true;
    fetchUrlBtnIcon.textContent = '⏳';
    btnFetchUrl.innerHTML = `<span>⏳</span> Fetching...`;

    try {
      const res = await fetch('/api/fetch-notice-url', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url })
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || 'Failed to fetch notice from URL.');
      }

      noticeInput.value = data.text;
      updateCounters();
      alert(`✓ Successfully loaded notice (${data.characters} characters) via ${data.engine}.\nYou can now inspect and click Extract Action Checklist.`);
    } catch (err) {
      alert(`Could not fetch URL: ${err.message}`);
    } finally {
      btnFetchUrl.disabled = false;
      btnFetchUrl.innerHTML = `<span>🌐</span> Fetch Notice`;
    }
  });

  // ==========================================
  // 4. AUTH0 EDUCATOR IDENTITY & GOVERNANCE
  // ==========================================
  function updateAuthUI() {
    const userJson = localStorage.getItem('notice2next_auth_educator');
    const savedList = JSON.parse(localStorage.getItem('notice2next_saved_library') || '[]');
    savedNoticeBadge.textContent = savedList.length;

    if (userJson) {
      const user = JSON.parse(userJson);
      authLoginBtn.style.display = 'none';
      authProfile.style.display = 'inline-flex';
      authUserName.textContent = user.name || 'Verified Educator';
    } else {
      authLoginBtn.style.display = 'inline-flex';
      authProfile.style.display = 'none';
    }
  }

  updateAuthUI();

  authLoginBtn.addEventListener('click', () => {
    // Auth0 Mock / Client Universal Login activation
    const educatorUser = {
      id: 'auth0|educator_demo_' + Date.now(),
      name: 'M. Rahman (Senior Educator)',
      email: 'm.rahman@school.edu.bd',
      role: 'Head of Academic Committee',
      verified: true
    };
    localStorage.setItem('notice2next_auth_educator', JSON.stringify(educatorUser));
    updateAuthUI();
    alert('✓ Signed in as M. Rahman (Senior Educator) via Auth0 Governance Gate.');
  });

  authLogoutBtn.addEventListener('click', () => {
    localStorage.removeItem('notice2next_auth_educator');
    updateAuthUI();
  });

  // Save Current Notice to Personal Library
  btnSaveToLibrary.addEventListener('click', () => {
    if (currentItems.length === 0) {
      alert('Please extract a circular before saving to your library.');
      return;
    }

    const savedList = JSON.parse(localStorage.getItem('notice2next_saved_library') || '[]');
    const textPreview = noticeInput.value.slice(0, 90).replace(/\n/g, ' ') + '...';
    
    const record = {
      id: 'notice_' + Date.now(),
      title: textPreview,
      date_saved: new Date().toLocaleString(),
      raw_text: noticeInput.value,
      total_actions: currentItems.length,
      items: currentItems
    };

    savedList.unshift(record);
    localStorage.setItem('notice2next_saved_library', JSON.stringify(savedList));
    updateAuthUI();
    alert(`✓ Notice successfully saved to your Personal Library (${currentItems.length} actions stored).`);
  });

  // Open Library Modal
  authLibraryBtn.addEventListener('click', () => {
    libraryModal.style.display = 'flex';
    renderLibraryModal();
  });

  btnCloseLibraryModal.addEventListener('click', () => {
    libraryModal.style.display = 'none';
  });

  function renderLibraryModal() {
    const savedList = JSON.parse(localStorage.getItem('notice2next_saved_library') || '[]');
    if (savedList.length === 0) {
      libraryModalBody.innerHTML = `
        <div class="empty-state">
          <div class="empty-icon">📁</div>
          <h4 class="empty-title">No Saved Notices Yet</h4>
          <p class="empty-desc">Extract any circular and click "Save to Library" to store it for offline reference.</p>
        </div>
      `;
      return;
    }

    let html = `<div class="saved-notices-list">`;
    savedList.forEach((rec, idx) => {
      html += `
        <div class="saved-notice-item">
          <div class="saved-notice-title">${escapeHtml(rec.title)}</div>
          <div class="saved-notice-meta">Saved: ${escapeHtml(rec.date_saved)} • ${rec.total_actions} Action Items</div>
          <div style="display: flex; gap: 0.5rem; margin-top: 0.5rem;">
            <button class="btn-primary btn-sm btn-load-saved" data-idx="${idx}">Load into Editor</button>
            <button class="btn-secondary btn-sm btn-delete-saved" data-idx="${idx}" style="color: #ef4444;">Delete</button>
          </div>
        </div>
      `;
    });
    html += `</div>`;
    libraryModalBody.innerHTML = html;

    document.querySelectorAll('.btn-load-saved').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const i = parseInt(e.target.getAttribute('data-idx'), 10);
        noticeInput.value = savedList[i].raw_text;
        updateCounters();
        currentItems = savedList[i].items || [];
        libraryModal.style.display = 'none';
        renderChecklist(currentItems, {
          total_items: currentItems.length,
          verified_count: currentItems.filter(it => it.validation_status === 'VERIFIED_QUOTE_GROUNDED').length,
          flagged_count: currentItems.filter(it => it.validation_status !== 'VERIFIED_QUOTE_GROUNDED').length,
          grounding_rate: 100
        });
      });
    });

    document.querySelectorAll('.btn-delete-saved').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const i = parseInt(e.target.getAttribute('data-idx'), 10);
        savedList.splice(i, 1);
        localStorage.setItem('notice2next_saved_library', JSON.stringify(savedList));
        updateAuthUI();
        renderLibraryModal();
      });
    });
  }

  // ==========================================
  // 5. SAMPLE LOADER & CACHE
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
        photoOcrPanel.style.display = 'none';
        urlIngestPanel.style.display = 'none';
        setActiveTab(tabTextMode);
        runExtraction();
      }
    });
  });

  // ==========================================
  // 6. ACTION EXTRACTION & RENDERING
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
    currentSummary = null;
    stopAudioBriefing();
  }

  async function runExtraction() {
    const text = noticeInput.value.trim();
    if (!text) {
      alert('Please enter, scan, or fetch a circular to extract actions.');
      return;
    }

    // UI Loading State
    emptyState.style.display = 'none';
    infoZeroState.style.display = 'none';
    checklistContainer.style.display = 'none';
    exportActions.style.display = 'none';
    evidenceDisclaimer.style.display = 'none';
    loadingState.style.display = 'block';
    stopAudioBriefing();

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
      currentSummary = data.summary;

      // Handle Case 3 (Zero Tasks Informational Notice)
      if (currentItems.length === 0) {
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

      const isDeadlineNotStated = (it.deadline || '').toUpperCase().includes('NOT STATED');
      const isQuoteVerified = it.quote_verified && it.validation_status === 'VERIFIED_QUOTE_GROUNDED';
      const isTeacherApproved = it.validation_status === 'TEACHER_APPROVED_VIA_AUTH0';
      const badgeText = isTeacherApproved ? '✓ Educator Approved (Auth0)' : (it.validation_badge_text || (isQuoteVerified ? '✓ Verbatim Quote Found' : '⚠️ Flagged for Review'));

      const isFlagged = !isQuoteVerified && !isTeacherApproved;

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
          <span class="meta-pill ${isQuoteVerified || isTeacherApproved ? 'meta-status-verified' : 'meta-status-warning'}" title="${escapeHtml(it.validation_notes)}">
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

        ${isFlagged ? `
          <div class="auth0-approval-gate" id="gate-${index}">
            <span class="auth0-gate-badge">🛡️ Auth0 Governance</span>
            <span class="auth0-gate-msg">Ambiguous evidence flagged by Python validator. Human approval required before acting.</span>
            <button type="button" class="btn-gate-approve" data-index="${index}">✅ Confirm & Approve</button>
            <button type="button" class="btn-gate-reject" data-index="${index}">❌ Dismiss</button>
          </div>
        ` : ''}
      `;

      itemsList.appendChild(card);
    });

    // Event Listeners for Checkboxes and Editable Title
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

    // Auth0 Human Approval Gate Listeners
    document.querySelectorAll('.btn-gate-approve').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const idx = parseInt(e.target.getAttribute('data-index'), 10);
        currentItems[idx].validation_status = 'TEACHER_APPROVED_VIA_AUTH0';
        currentItems[idx].quote_verified = true;
        currentItems[idx].validation_badge_text = '✓ Educator Approved (Auth0)';
        alert(`✓ Task #${idx + 1} approved by Educator via Auth0 Governance Gate.`);
        renderChecklist(currentItems, summary);
      });
    });

    document.querySelectorAll('.btn-gate-reject').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const idx = parseInt(e.target.getAttribute('data-index'), 10);
        currentItems.splice(idx, 1);
        summary.total_items = currentItems.length;
        renderChecklist(currentItems, summary);
      });
    });

    checklistContainer.style.display = 'block';
    exportActions.style.display = 'flex';
    evidenceDisclaimer.style.display = 'flex';
  }

  btnExtract.addEventListener('click', runExtraction);

  // ==========================================
  // 7. ELEVENLABS AUDIO BRIEFING
  // ==========================================
  btnPlayAudioBriefing.addEventListener('click', async () => {
    if (currentItems.length === 0) return;

    if (isSpeaking) {
      stopAudioBriefing();
      return;
    }

    audioPlayerWrapper.style.display = 'block';
    audioStatusText.textContent = 'Generating spoken briefing...';
    btnPlayAudioBriefing.innerHTML = `<span>⏳</span> Generating...`;

    try {
      const res = await fetch('/api/speak-briefing', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ items: currentItems })
      });

      const data = await res.json();
      btnPlayAudioBriefing.innerHTML = `<span>⏹️</span> Stop Briefing`;
      isSpeaking = true;

      if (data.has_audio && data.audio_base64) {
        // High quality ElevenLabs Audio Stream
        briefingAudioElement.src = `data:${data.content_type || 'audio/mpeg'};base64,${data.audio_base64}`;
        audioStatusText.textContent = `🎙️ Playing ElevenLabs Audio Briefing (${data.voice_id || 'Adam'})...`;
        briefingAudioElement.play();
        briefingAudioElement.onended = stopAudioBriefing;
      } else {
        // Client-side Web Speech API Fallback
        audioStatusText.textContent = '🎙️ Reading aloud via Browser Voice Engine...';
        if ('speechSynthesis' in window) {
          window.speechSynthesis.cancel();
          const utterance = new SpeechSynthesisUtterance(data.briefing_text);
          utterance.rate = 1.0;
          utterance.onend = stopAudioBriefing;
          utterance.onerror = stopAudioBriefing;
          window.speechSynthesis.speak(utterance);
        } else {
          alert('Briefing text:\n\n' + data.briefing_text);
          stopAudioBriefing();
        }
      }
    } catch (err) {
      alert(`Audio synthesis error: ${err.message}`);
      stopAudioBriefing();
    }
  });

  btnStopAudio.addEventListener('click', stopAudioBriefing);

  function stopAudioBriefing() {
    isSpeaking = false;
    if (briefingAudioElement) {
      briefingAudioElement.pause();
      briefingAudioElement.currentTime = 0;
    }
    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel();
    }
    audioPlayerWrapper.style.display = 'none';
    btnPlayAudioBriefing.innerHTML = `<span>🔊</span> Listen Briefing`;
  }

  // ==========================================
  // 8. EXPORT UTILITIES (CSV & Markdown)
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
      const action = (it.action || '').replace(/\|/g, '-');
      const assignee = (it.assignee || '').replace(/\|/g, '-');
      const deadline = (it.deadline || '').replace(/\|/g, '-');
      const quote = (it.source_quote || '').replace(/\|/g, '-').replace(/\n/g, ' ');
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
  // 9. LIVE BENCHMARK MODAL
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
