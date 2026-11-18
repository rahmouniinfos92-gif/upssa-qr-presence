/**
 * UPSSA QR Code Attendance Scanner & Management System
 */

(function () {
  'use strict';

  // --- State Variables ---
  let students = [];
  let scansHistory = [];
  let html5QrCode = null;
  let isScanning = false;
  let currentCameraId = null;
  let soundEnabled = true;
  let vibrationEnabled = true;
  let audioCtx = null;
  let lastScannedCode = null;
  let lastScanTimestamp = 0;

  // --- Audio Feedback Engine (Web Audio API) ---
  function getAudioContext() {
    if (!audioCtx) {
      const AudioContext = window.AudioContext || window.webkitAudioContext;
      if (AudioContext) {
        audioCtx = new AudioContext();
      }
    }
    if (audioCtx && audioCtx.state === 'suspended') {
      audioCtx.resume();
    }
    return audioCtx;
  }

  function playSuccessSound() {
    if (!soundEnabled) return;
    try {
      const ctx = getAudioContext();
      if (!ctx) return;
      const now = ctx.currentTime;
      
      const osc1 = ctx.createOscillator();
      const osc2 = ctx.createOscillator();
      const gain = ctx.createGain();

      osc1.type = 'sine';
      osc2.type = 'triangle';

      osc1.frequency.setValueAtTime(587.33, now); // D5
      osc1.frequency.exponentialRampToValueAtTime(880, now + 0.12); // A5

      osc2.frequency.setValueAtTime(880, now + 0.12);
      osc2.frequency.exponentialRampToValueAtTime(1174.66, now + 0.25); // D6

      gain.gain.setValueAtTime(0.2, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.35);

      osc1.connect(gain);
      osc2.connect(gain);
      gain.connect(ctx.destination);

      osc1.start(now);
      osc1.stop(now + 0.15);
      osc2.start(now + 0.12);
      osc2.stop(now + 0.35);
    } catch (e) {
      console.warn('Audio feedback failed:', e);
    }
  }

  function playWarningSound() {
    if (!soundEnabled) return;
    try {
      const ctx = getAudioContext();
      if (!ctx) return;
      const now = ctx.currentTime;
      
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();

      osc.type = 'sawtooth';
      osc.frequency.setValueAtTime(440, now);
      osc.frequency.setValueAtTime(440, now + 0.1);
      osc.frequency.setValueAtTime(350, now + 0.18);

      gain.gain.setValueAtTime(0.18, now);
      gain.gain.linearRampToValueAtTime(0.01, now + 0.3);

      osc.connect(gain);
      gain.connect(ctx.destination);

      osc.start(now);
      osc.stop(now + 0.3);
    } catch (e) {
      console.warn('Audio feedback failed:', e);
    }
  }

  function playErrorSound() {
    if (!soundEnabled) return;
    try {
      const ctx = getAudioContext();
      if (!ctx) return;
      const now = ctx.currentTime;
      
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();

      osc.type = 'square';
      osc.frequency.setValueAtTime(220, now);
      osc.frequency.exponentialRampToValueAtTime(130, now + 0.3);

      gain.gain.setValueAtTime(0.22, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.35);

      osc.connect(gain);
      gain.connect(ctx.destination);

      osc.start(now);
      osc.stop(now + 0.35);
    } catch (e) {
      console.warn('Audio feedback failed:', e);
    }
  }

  function triggerVibrate(pattern) {
    if (vibrationEnabled && navigator.vibrate) {
      navigator.vibrate(pattern);
    }
  }

  // --- Toast Notifications ---
  function showToast(message, type = 'info') {
    const container = document.getElementById('toastContainer');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    
    let icon = 'ℹ️';
    if (type === 'success') icon = '✅';
    if (type === 'warning') icon = '⚠️';
    if (type === 'error') icon = '❌';

    toast.innerHTML = `<span>${icon}</span><span>${message}</span>`;
    container.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(10px)';
      toast.style.transition = 'all 0.3s ease';
      setTimeout(() => toast.remove(), 300);
    }, 3500);
  }

  // --- Persistence & Initialization (SQLite + Local fallback) ---
  async function loadData() {
    if (window.location.protocol.startsWith('http')) {
      try {
        const res = await fetch('/api/students');
        if (res.ok) {
          const data = await res.json();
          if (Array.isArray(data) && data.length > 0) {
            students = data;
            const attendedList = students
              .filter(s => s.attended && s.scanned_time)
              .sort((a, b) => (b.scanned_at || '').localeCompare(a.scanned_at || ''));
            if (attendedList.length > 0) {
              scansHistory = attendedList.map(s => ({
                id: s.id,
                name: s.name,
                pole: s.pole,
                year: s.year,
                time: s.scanned_time,
                timestamp: s.scanned_at
              }));
            }
            saveData();
            updateStats();
            renderStudentsTable();
            renderActivityFeed();
            renderWhatsAppTab();
            return;
          }
        }
      } catch (e) {
        console.warn('API SQLite non joignable, fallback local:', e);
      }
    }

    const stored = localStorage.getItem('upssa_students_data_v2');
    if (stored) {
      try {
        students = JSON.parse(stored);
      } catch (e) {
        console.error('Error parsing stored data:', e);
        students = JSON.parse(JSON.stringify(window.INITIAL_STUDENTS || []));
      }
    } else {
      students = JSON.parse(JSON.stringify(window.INITIAL_STUDENTS || []));
    }

    const storedHistory = localStorage.getItem('upssa_scans_history_v2');
    if (storedHistory) {
      try {
        scansHistory = JSON.parse(storedHistory);
      } catch (e) {
        scansHistory = [];
      }
    } else {
      // Rebuild history from attended students if any
      scansHistory = students
        .filter(s => s.attended && s.scanned_time)
        .map(s => ({
          id: s.id,
          name: s.name,
          pole: s.pole,
          year: s.year,
          time: s.scanned_time,
          timestamp: s.scanned_at || new Date().toISOString()
        }))
        .reverse();
    }
  }

  function saveData() {
    try {
      localStorage.setItem('upssa_students_data_v2', JSON.stringify(students));
      localStorage.setItem('upssa_scans_history_v2', JSON.stringify(scansHistory.slice(0, 50)));
    } catch (e) {
      console.warn('LocalStorage save failed:', e);
    }
  }

  // --- Code Extraction & Normalization ---
  function normalizeCode(rawText) {
    if (!rawText) return '';
    let text = String(rawText).trim();

    // Check if it's a URL like https://.../?id=f14um11i7q or ?student=f14um11i7q
    try {
      if (text.includes('?') && (text.startsWith('http://') || text.startsWith('https://'))) {
        const url = new URL(text);
        const idParam = url.searchParams.get('id') || url.searchParams.get('identifiant') || url.searchParams.get('code');
        if (idParam) return idParam.trim();
      }
    } catch (e) {}

    // Check if it's a JSON string
    if (text.startsWith('{') && text.endsWith('}')) {
      try {
        const parsed = JSON.parse(text);
        if (parsed.id) return String(parsed.id).trim();
        if (parsed.identifiant) return String(parsed.identifiant).trim();
        if (parsed.email) return String(parsed.email).trim();
      } catch (e) {}
    }

    // Prefix format like UPSSA:f14um11i7q
    if (text.toUpperCase().startsWith('UPSSA:')) {
      return text.substring(6).trim();
    }

    return text;
  }

  function findStudent(query) {
    const code = normalizeCode(query).toLowerCase();
    if (!code) return null;

    // 1. Direct 4-digit ID match (ex: 1001)
    let match = students.find(s => s.id && String(s.id).toLowerCase() === code);
    if (match) return match;

    // 1b. Old ID match (for backward compatibility)
    match = students.find(s => s.old_id && String(s.old_id).toLowerCase() === code);
    if (match) return match;

    // 2. Email exact match
    match = students.find(s => s.email && s.email.toLowerCase() === code);
    if (match) return match;

    // 3. Phone match (normalized digits)
    const digitsOnly = code.replace(/\D/g, '');
    if (digitsOnly.length >= 6) {
      match = students.find(s => {
        const sDigits = (s.phone || '').replace(/\D/g, '');
        return sDigits.endsWith(digitsOnly) || digitsOnly.endsWith(sDigits);
      });
      if (match) return match;
    }

    // 4. Name exact match
    match = students.find(s => s.name && s.name.toLowerCase() === code);
    if (match) return match;

    return null;
  }

  // --- Scan Engine & Pointage (Connecté à la Base SQL temps réel) ---
  async function processScan(rawCode, device = 'camera_scanner') {
    const now = Date.now();
    const cleanCode = normalizeCode(rawCode);

    // Évite les déclenchements multiples trop rapides (2 secondes)
    if (lastScannedCode === cleanCode && (now - lastScanTimestamp) < 2000) {
      return;
    }
    lastScannedCode = cleanCode;
    lastScanTimestamp = now;

    let localStudent = findStudent(cleanCode);

    // 1. Enregistrement direct dans l'API SQLite (en ligne sur Fly.io / serveur HTTP)
    if (window.location.protocol.startsWith('http')) {
      try {
        const resp = await fetch('/api/scan', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ code: cleanCode || rawCode, device: device })
        });

        if (resp.ok) {
          const res = await resp.json();

          if (res.status === 'success' && res.student) {
            const s = students.find(item => item.id === res.student.id) || localStudent;
            if (s) {
              s.attended = 1;
              s.scanned_at = res.student.scanned_at;
              s.scanned_time = res.student.scanned_time;
            }

            scansHistory.unshift({
              id: res.student.id,
              name: res.student.name,
              pole: res.student.pole,
              year: res.student.year,
              time: res.student.scanned_time,
              timestamp: res.student.scanned_at
            });
            if (scansHistory.length > 50) scansHistory.pop();

            saveData();
            playSuccessSound();
            triggerVibrate([120]);
            renderSuccessResult(res.student);
            updateStats();
            renderActivityFeed();
            renderStudentsTable();
            showToast(`✅ Présence enregistrée dans la base SQL : ${res.student.name}`, 'success');
            return;
          } else if (res.status === 'duplicate' && res.student) {
            playWarningSound();
            triggerVibrate([150, 100, 150]);
            renderWarningResult(res.student);
            showToast(res.message || `⚠️ Déjà scanné : ${res.student.name}`, 'warning');
            return;
          } else if (res.status === 'not_found') {
            playErrorSound();
            triggerVibrate([300]);
            renderErrorResult(cleanCode || rawCode);
            showToast(`❌ Code inconnu : ${cleanCode || rawCode}`, 'error');
            return;
          }
        }
      } catch (err) {
        console.warn('Erreur appel /api/scan, passage en mode local fallback:', err);
      }
    }

    // 2. Mode Fallback Hors-Ligne (si le backend est injoignable)
    if (!localStudent) {
      playErrorSound();
      triggerVibrate([300]);
      renderErrorResult(cleanCode || rawCode);
      showToast(`Code non reconnu : ${cleanCode || rawCode}`, 'error');
      return;
    }

    if (localStudent.attended) {
      playWarningSound();
      triggerVibrate([150, 100, 150]);
      renderWarningResult(localStudent);
      showToast(`Déjà scanné : ${localStudent.name}`, 'warning');
      return;
    }

    // Success check-in local
    localStudent.attended = 1;
    localStudent.scanned_at = new Date().toISOString();
    localStudent.scanned_time = new Date().toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit', second: '2-digit' });

    scansHistory.unshift({
      id: localStudent.id,
      name: localStudent.name,
      pole: localStudent.pole,
      year: localStudent.year,
      time: localStudent.scanned_time,
      timestamp: localStudent.scanned_at
    });
    if (scansHistory.length > 50) scansHistory.pop();

    saveData();
    playSuccessSound();
    triggerVibrate([120]);
    renderSuccessResult(localStudent);
    updateStats();
    renderActivityFeed();
    renderStudentsTable();
    showToast(`Présence validée (mode local) : ${localStudent.name}`, 'success');
  }

  // --- Render Scan Results in UI ---
  function renderSuccessResult(student) {
    const box = document.getElementById('scanResultBox');
    if (!box) return;

    box.innerHTML = `
      <div class="result-card success">
        <div class="result-banner">
          <div class="result-icon">✓</div>
          <div class="result-status-text">
            <h3 style="color: #065f46;">PRÉSENCE VALIDÉE AVEC SUCCÈS</h3>
            <p>Enregistré à <strong>${student.scanned_time}</strong></p>
          </div>
        </div>

        <div class="student-sheet">
          <div class="student-name-row">
            <div class="student-name">${escapeHtml(student.name)}</div>
            <div class="student-id-tag">ID: ${escapeHtml(student.id)}</div>
          </div>

          <div class="student-meta-grid">
            <div class="meta-box">
              <div class="meta-label">Pôle</div>
              <div class="meta-value">${escapeHtml(student.pole)}</div>
            </div>
            <div class="meta-box">
              <div class="meta-label">Année d'étude</div>
              <div class="meta-value">${escapeHtml(student.year)}</div>
            </div>
            <div class="meta-box">
              <div class="meta-label">Téléphone</div>
              <div class="meta-value">${escapeHtml(student.phone || 'Non renseigné')}</div>
            </div>
            <div class="meta-box">
              <div class="meta-label">Courriel</div>
              <div class="meta-value" style="font-size: 0.8rem; word-break: break-all;">${escapeHtml(student.email || '-')}</div>
            </div>
          </div>

          <div style="margin-top: 0.5rem;">
            <div class="meta-label" style="margin-bottom: 0.35rem;">Prestations & Accès événement</div>
            <div class="event-badges-row">
              <span class="event-badge ${student.gala ? 'badge-yes' : 'badge-no'}">
                ${student.gala ? '🎟️ Gala : OUI' : '🎟️ Gala : Non'}
              </span>
              <span class="event-badge ${student.teambuilding ? 'badge-yes' : 'badge-no'}">
                ${student.teambuilding ? '🏃 Teambuilding : OUI' : '🏃 Teambuilding : Non'}
              </span>
              <span class="event-badge ${student.transport ? 'badge-yes' : 'badge-no'}">
                ${student.transport ? '🚌 Transport UPSSA : OUI' : '🚌 Transport : Non'}
              </span>
            </div>
          </div>

          <div style="margin-top: 1rem; display: flex; justify-content: space-between; align-items: center; border-top: 1px solid rgba(0,0,0,0.06); padding-top: 0.75rem;">
            <button class="btn btn-sm btn-outline" onclick="window.cancelAttendance('${student.id}')">
              ↩ Annuler ce pointage
            </button>
            <button class="btn btn-sm btn-primary" onclick="window.openStudentBadge('${student.id}')">
              🎫 Voir le badge
            </button>
          </div>
        </div>
      </div>
    `;
  }

  function renderWarningResult(student) {
    const box = document.getElementById('scanResultBox');
    if (!box) return;

    box.innerHTML = `
      <div class="result-card warning">
        <div class="result-banner">
          <div class="result-icon">⚠️</div>
          <div class="result-status-text">
            <h3 style="color: #92400e;">ATTENTION : ÉTUDIANT DÉJÀ POINTÉ</h3>
            <p>Présence enregistrée précédemment à <strong>${student.scanned_time || 'Aujourd’hui'}</strong></p>
          </div>
        </div>

        <div class="student-sheet">
          <div class="student-name-row">
            <div class="student-name">${escapeHtml(student.name)}</div>
            <div class="student-id-tag">ID: ${escapeHtml(student.id)}</div>
          </div>

          <div class="student-meta-grid">
            <div class="meta-box">
              <div class="meta-label">Pôle</div>
              <div class="meta-value">${escapeHtml(student.pole)}</div>
            </div>
            <div class="meta-box">
              <div class="meta-label">Année</div>
              <div class="meta-value">${escapeHtml(student.year)}</div>
            </div>
          </div>

          <div class="event-badges-row" style="margin-top: 0.5rem;">
            <span class="event-badge ${student.gala ? 'badge-yes' : 'badge-no'}">
              Gala: ${student.gala ? 'OUI' : 'Non'}
            </span>
            <span class="event-badge ${student.teambuilding ? 'badge-yes' : 'badge-no'}">
              Teambuilding: ${student.teambuilding ? 'OUI' : 'Non'}
            </span>
            <span class="event-badge ${student.transport ? 'badge-yes' : 'badge-no'}">
              Transport: ${student.transport ? 'OUI' : 'Non'}
            </span>
          </div>

          <div style="margin-top: 1rem; display: flex; justify-content: space-between; align-items: center; border-top: 1px solid rgba(0,0,0,0.06); padding-top: 0.75rem;">
            <button class="btn btn-sm btn-rose" onclick="window.cancelAttendance('${student.id}')">
              Annuler la présence
            </button>
            <button class="btn btn-sm btn-outline" onclick="window.openStudentBadge('${student.id}')">
              Voir badge
            </button>
          </div>
        </div>
      </div>
    `;
  }

  function renderErrorResult(code) {
    const box = document.getElementById('scanResultBox');
    if (!box) return;

    box.innerHTML = `
      <div class="result-card error">
        <div class="result-banner">
          <div class="result-icon">✕</div>
          <div class="result-status-text">
            <h3 style="color: #991b1b;">CODE INCONNU / NON INSCRIT</h3>
            <p>Aucune correspondance trouvée dans les 309 inscrits UPSSA</p>
          </div>
        </div>

        <div style="background: white; border: 1px solid var(--gray-200); border-radius: var(--radius-sm); padding: 0.75rem; margin-top: 0.5rem;">
          <div style="font-size: 0.75rem; color: var(--gray-500); text-transform: uppercase;">Valeur scannée détectée :</div>
          <div style="font-family: monospace; font-size: 0.95rem; font-weight: 700; color: #b91c1c; word-break: break-all; margin-top: 0.25rem;">
            ${escapeHtml(code)}
          </div>
        </div>

        <div style="margin-top: 1rem; font-size: 0.85rem; color: var(--gray-600);">
          💡 Conseil : Vérifiez que l'étudiant fait partie de la liste officielle ou effectuez une recherche manuelle par nom/prénom dans l'onglet <strong>Étudiants</strong>.
        </div>
      </div>
    `;
  }

  // --- Manual Attendance Actions ---
  window.cancelAttendance = function (id) {
    const student = students.find(s => s.id === id);
    if (!student) return;

    if (window.location.protocol.startsWith('http')) {
      fetch('/api/toggle-presence', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: id, status: 0 })
      }).catch(e => console.warn('Cancel attendance offline sync error:', e));
    }

    student.attended = false;
    delete student.scanned_at;
    delete student.scanned_time;

    scansHistory = scansHistory.filter(h => h.id !== id);

    saveData();
    updateStats();
    renderActivityFeed();
    renderStudentsTable();
    showToast(`Présence annulée pour ${student.name}`, 'warning');

    const box = document.getElementById('scanResultBox');
    if (box) {
      box.innerHTML = `
        <div class="result-card" style="text-align: center; color: var(--gray-500); padding: 2rem;">
          <div style="font-size: 2.5rem; margin-bottom: 0.5rem;">↩</div>
          <p>Le pointage de <strong>${escapeHtml(student.name)}</strong> a été annulé avec succès.</p>
        </div>
      `;
    }
  };

  window.toggleStudentAttendance = function (id) {
    const student = students.find(s => s.id === id);
    if (!student) return;

    if (student.attended) {
      window.cancelAttendance(id);
    } else {
      processScan(id);
    }
  };

  // --- Camera QR Scanner Implementation ---
  function initScanner() {
    if (typeof Html5Qrcode === 'undefined') {
      console.warn('Html5Qrcode library not loaded yet');
      return;
    }

    if (!html5QrCode) {
      html5QrCode = new Html5Qrcode("reader");
    }

    // Populate camera selector
    Html5Qrcode.getCameras().then(devices => {
      const select = document.getElementById('cameraSelect');
      if (select && devices && devices.length) {
        select.innerHTML = '';
        devices.forEach((dev, idx) => {
          const opt = document.createElement('option');
          opt.value = dev.id;
          opt.text = dev.label || `Caméra ${idx + 1}`;
          select.appendChild(opt);
        });

        // Prefer rear camera if available
        const backCam = devices.find(d => d.label.toLowerCase().includes('back') || d.label.toLowerCase().includes('arrière') || d.label.toLowerCase().includes('environment'));
        currentCameraId = backCam ? backCam.id : devices[0].id;
        select.value = currentCameraId;
      }
    }).catch(err => {
      console.warn('Could not enumerate cameras:', err);
    });
  }

  function startCameraScanner() {
    if (isScanning) return;
    if (typeof Html5Qrcode === 'undefined') {
      showToast('Veuillez patienter, module caméra en chargement...', 'warning');
      return;
    }

    if (!html5QrCode) {
      html5QrCode = new Html5Qrcode("reader");
    }

    const select = document.getElementById('cameraSelect');
    const selectedId = select ? select.value : currentCameraId;

    const config = {
      fps: 15,
      qrbox: (viewfinderWidth, viewfinderHeight) => {
        const minEdge = Math.min(viewfinderWidth, viewfinderHeight);
        const qrboxSize = Math.floor(minEdge * 0.75);
        return { width: Math.max(qrboxSize, 180), height: Math.max(qrboxSize, 180) };
      }
    };

    const cameraMode = selectedId ? { deviceId: { exact: selectedId } } : { facingMode: "environment" };

    const startBtn = document.getElementById('startScanBtn');
    const stopBtn = document.getElementById('stopScanBtn');
    const placeholder = document.getElementById('cameraPlaceholder');
    const reticle = document.getElementById('scannerReticle');

    html5QrCode.start(
      cameraMode,
      config,
      (decodedText) => {
        processScan(decodedText, 'camera_scanner');
      },
      (error) => {
        // Ignored frame scan failures (standard noise)
      }
    ).then(() => {
      isScanning = true;
      if (startBtn) startBtn.style.display = 'none';
      if (stopBtn) stopBtn.style.display = 'inline-flex';
      if (placeholder) placeholder.style.display = 'none';
      if (reticle) reticle.style.display = 'block';
      showToast('Caméra active ! Visez un QR Code', 'info');
    }).catch(err => {
      console.error('Camera start error:', err);
      showToast('Impossible d’accéder à la caméra. Vérifiez les autorisations du navigateur.', 'error');
    });
  }

  function stopCameraScanner() {
    if (!isScanning || !html5QrCode) return;

    html5QrCode.stop().then(() => {
      isScanning = false;
      const startBtn = document.getElementById('startScanBtn');
      const stopBtn = document.getElementById('stopScanBtn');
      const placeholder = document.getElementById('cameraPlaceholder');
      const reticle = document.getElementById('scannerReticle');

      if (startBtn) startBtn.style.display = 'inline-flex';
      if (stopBtn) stopBtn.style.display = 'none';
      if (placeholder) placeholder.style.display = 'block';
      if (reticle) reticle.style.display = 'none';
      showToast('Caméra arrêtée', 'info');
    }).catch(err => {
      console.warn('Stop camera error:', err);
    });
  }

  // --- Statistics & KPI Updates ---
  function updateStats() {
    const total = students.length;
    const attendedCount = students.filter(s => s.attended).length;
    const pctAttended = total > 0 ? ((attendedCount / total) * 100).toFixed(1) : 0;

    // Gala
    const totalGala = students.filter(s => s.gala).length;
    const attendedGala = students.filter(s => s.gala && s.attended).length;
    const pctGala = totalGala > 0 ? ((attendedGala / totalGala) * 100).toFixed(1) : 0;

    // Teambuilding
    const totalTeam = students.filter(s => s.teambuilding).length;
    const attendedTeam = students.filter(s => s.teambuilding && s.attended).length;
    const pctTeam = totalTeam > 0 ? ((attendedTeam / totalTeam) * 100).toFixed(1) : 0;

    // Transport
    const totalTransport = students.filter(s => s.transport).length;
    const attendedTransport = students.filter(s => s.transport && s.attended).length;
    const pctTransport = totalTransport > 0 ? ((attendedTransport / totalTransport) * 100).toFixed(1) : 0;

    // Update Ribbon
    const waSentTotal = students.filter(s => s.whatsapp_status === 'sent').length;
    setText('kpiTotalRibbon', total);
    setText('kpiPresentRibbon', `${attendedCount} (${pctAttended}%)`);
    setText('kpiGalaRibbon', `${attendedGala}/${totalGala}`);
    setText('kpiTeamRibbon', `${attendedTeam}/${totalTeam}`);
    setText('kpiTransportRibbon', `${attendedTransport}/${totalTransport}`);
    setText('kpiWaRibbon', `${waSentTotal}/${total}`);
    setText('tabCountWa', `${waSentTotal}/${total}`);
    setText('heroCheckinCount', `${attendedCount} / ${total} Présents validés`);

    // Update Tab Badges
    setText('tabCountAll', total);
    setText('tabCountPresent', attendedCount);

    // Update Detailed Stat Cards
    setText('statTotalInscrits', total);
    setText('statTotalPresents', attendedCount);
    setText('statTauxPresence', `${pctAttended}%`);
    setBarWidth('barTotalPresence', `${pctAttended}%`);

    setText('statGalaCount', `${attendedGala} / ${totalGala}`);
    setText('statGalaPct', `${pctGala}%`);
    setBarWidth('barGala', `${pctGala}%`);

    setText('statTeamCount', `${attendedTeam} / ${totalTeam}`);
    setText('statTeamPct', `${pctTeam}%`);
    setBarWidth('barTeam', `${pctTeam}%`);

    setText('statTransportCount', `${attendedTransport} / ${totalTransport}`);
    setText('statTransportPct', `${pctTransport}%`);
    setBarWidth('barTransport', `${pctTransport}%`);

    // Pôles Distribution
    updatePoleStats();
  }

  function updatePoleStats() {
    const poles = ['Santé', 'Sciences', 'Audit'];
    poles.forEach(p => {
      const totalP = students.filter(s => s.pole === p).length;
      const attendedP = students.filter(s => s.pole === p && s.attended).length;
      const pctP = totalP > 0 ? ((attendedP / totalP) * 100).toFixed(1) : 0;

      setText(`statPole_${p}_count`, `${attendedP}/${totalP}`);
      setText(`statPole_${p}_pct`, `${pctP}%`);
      setBarWidth(`barPole_${p}`, `${pctP}%`);
    });
  }

  function setText(id, text) {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
  }

  function setBarWidth(id, width) {
    const el = document.getElementById(id);
    if (el) el.style.width = width;
  }

  // --- Activity Feed ---
  function renderActivityFeed() {
    const container = document.getElementById('recentScansList');
    if (!container) return;

    if (scansHistory.length === 0) {
      container.innerHTML = `
        <div style="text-align: center; color: var(--gray-400); padding: 1.5rem; font-size: 0.85rem;">
          Aucun pointage pour l'instant. Les scans récents apparaîtront ici.
        </div>
      `;
      return;
    }

    container.innerHTML = scansHistory.map((item, idx) => `
      <div class="activity-item ${idx === 0 ? 'highlight' : ''}">
        <div class="activity-left">
          <div class="activity-avatar">${(item.name || 'U').charAt(0).toUpperCase()}</div>
          <div>
            <div class="activity-name">${escapeHtml(item.name)}</div>
            <div class="activity-sub">${escapeHtml(item.pole)} • ${escapeHtml(item.year)}</div>
          </div>
        </div>
        <div class="activity-time">${item.time}</div>
      </div>
    `).join('');
  }

  // --- Students Table & Filters ---
  let currentPage = 1;
  const pageSize = 25;

  function getFilteredStudents() {
    const search = (document.getElementById('searchInput')?.value || '').toLowerCase().trim();
    const filterStatus = document.getElementById('filterStatus')?.value || 'all';
    const filterPole = document.getElementById('filterPole')?.value || 'all';
    const filterYear = document.getElementById('filterYear')?.value || 'all';
    const filterEvent = document.getElementById('filterEvent')?.value || 'all';

    return students.filter(s => {
      // Search text
      if (search) {
        const full = `${s.name} ${s.id} ${s.email} ${s.phone}`.toLowerCase();
        if (!full.includes(search)) return false;
      }

      // Status
      if (filterStatus === 'present' && !s.attended) return false;
      if (filterStatus === 'absent' && s.attended) return false;

      // Pole
      if (filterPole !== 'all' && s.pole !== filterPole) return false;

      // Year
      if (filterYear !== 'all' && s.year !== filterYear) return false;

      // Event
      if (filterEvent === 'gala' && !s.gala) return false;
      if (filterEvent === 'teambuilding' && !s.teambuilding) return false;
      if (filterEvent === 'transport' && !s.transport) return false;

      return true;
    });
  }

  function renderStudentsTable() {
    const tbody = document.getElementById('studentsTableBody');
    if (!tbody) return;

    const filtered = getFilteredStudents();
    const totalFiltered = filtered.length;
    setText('filteredCount', totalFiltered);

    const totalPages = Math.ceil(totalFiltered / pageSize) || 1;
    if (currentPage > totalPages) currentPage = totalPages;

    const startIdx = (currentPage - 1) * pageSize;
    const pageItems = filtered.slice(startIdx, startIdx + pageSize);

    if (pageItems.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="7" style="text-align: center; padding: 2rem; color: var(--gray-400);">
            Aucun étudiant ne correspond aux critères de recherche.
          </td>
        </tr>
      `;
      renderPagination(0, 0);
      return;
    }

    tbody.innerHTML = pageItems.map(s => {
      let poleBadgeClass = 'badge-pole-sante';
      if (s.pole === 'Sciences') poleBadgeClass = 'badge-pole-sciences';
      if (s.pole === 'Audit') poleBadgeClass = 'badge-pole-audit';

      return `
        <tr class="${s.attended ? 'scanned-row' : ''}">
          <td>
            <code style="font-weight: 700; color: #1e3a8a;">${escapeHtml(s.id)}</code>
          </td>
          <td>
            <div style="font-weight: 700; color: var(--gray-900);">${escapeHtml(s.name)}</div>
            <div style="font-size: 0.75rem; color: var(--gray-500);">${escapeHtml(s.email || '-')}</div>
          </td>
          <td>
            <span class="event-badge ${poleBadgeClass}">${escapeHtml(s.pole)}</span>
            <div style="font-size: 0.72rem; color: var(--gray-500); margin-top: 2px;">${escapeHtml(s.year)}</div>
          </td>
          <td>
            <div style="display: flex; gap: 0.25rem;">
              <span title="Gala" style="opacity: ${s.gala ? '1' : '0.2'}; font-size: 1.05rem;">🎟️</span>
              <span title="Teambuilding" style="opacity: ${s.teambuilding ? '1' : '0.2'}; font-size: 1.05rem;">🏃</span>
              <span title="Transport" style="opacity: ${s.transport ? '1' : '0.2'}; font-size: 1.05rem;">🚌</span>
            </div>
          </td>
          <td>
            <div style="font-size: 0.8rem; font-family: monospace;">${escapeHtml(s.phone || '-')}</div>
          </td>
          <td>
            ${s.attended 
              ? `<span class="status-pill status-present">✓ Présent (${s.scanned_time || 'OK'})</span>` 
              : `<span class="status-pill status-pending">○ En attente</span>`}
          </td>
          <td>
            <div style="display: flex; gap: 0.35rem; justify-content: flex-end;">
              <button 
                class="btn btn-sm ${s.attended ? 'btn-rose' : 'btn-emerald'}" 
                onclick="window.toggleStudentAttendance('${s.id}')"
                title="${s.attended ? 'Annuler le pointage' : 'Pointer présent'}">
                ${s.attended ? 'Annuler' : '✓ Pointer'}
              </button>
              <button 
                class="btn btn-sm btn-outline" 
                onclick="window.openStudentBadge('${s.id}')" 
                title="Générer / Imprimer Badge & QR">
                🎫
              </button>
              <button 
                class="btn btn-sm btn-whatsapp" 
                style="padding: 0.25rem 0.5rem; font-size: 0.8rem;" 
                onclick="window.openWaDirect('${s.id}')" 
                title="Envoyer confirmation WhatsApp">
                📲
              </button>
            </div>
          </td>
        </tr>
      `;
    }).join('');

    renderPagination(totalFiltered, totalPages);
  }

  function renderPagination(totalCount, totalPages) {
    const container = document.getElementById('tablePagination');
    if (!container) return;

    if (totalCount <= pageSize) {
      container.innerHTML = `<span style="font-size: 0.8rem; color: var(--gray-500);">Affichage de ${totalCount} étudiant(s)</span>`;
      return;
    }

    container.innerHTML = `
      <div style="display: flex; align-items: center; justify-content: space-between; width: 100%;">
        <span style="font-size: 0.8rem; color: var(--gray-500);">
          Page ${currentPage} sur ${totalPages} (${totalCount} résultats)
        </span>
        <div style="display: flex; gap: 0.35rem;">
          <button class="btn btn-sm btn-outline" onclick="window.changePage(${currentPage - 1})" ${currentPage <= 1 ? 'disabled' : ''}>
            Précédent
          </button>
          <button class="btn btn-sm btn-outline" onclick="window.changePage(${currentPage + 1})" ${currentPage >= totalPages ? 'disabled' : ''}>
            Suivant
          </button>
        </div>
      </div>
    `;
  }

  window.changePage = function(page) {
    currentPage = page;
    renderStudentsTable();
  };

  // --- Student Badge & QR Code Modal ---
  window.openStudentBadge = function(id) {
    const student = students.find(s => s.id === id);
    if (!student) return;

    const modal = document.getElementById('badgeModal');
    const modalBody = document.getElementById('badgeModalBody');
    if (!modal || !modalBody) return;

    modalBody.innerHTML = `
      <div class="student-badge-ticket" id="printableTicket">
        <div class="badge-ticket-header">
          <div style="font-size: 0.72rem; letter-spacing: 1px; text-transform: uppercase; opacity: 0.9;">UNIVERSITÉ PRIVÉE DE SANTÉ SOUSS ALMASSIRA</div>
          <h4>ÉVÉNEMENT UPSSA 2026</h4>
          <p>BADGE D'ACCÈS & POINTAGE QR</p>
        </div>

        <div class="badge-ticket-body">
          <div class="badge-qr-box" id="ticketQrTarget"></div>

          <div class="badge-student-name">${escapeHtml(student.name)}</div>
          <div class="badge-student-id">ID: ${escapeHtml(student.id)}</div>

          <div style="font-size: 0.85rem; color: var(--gray-600); margin-bottom: 0.5rem;">
            <strong>Pôle :</strong> ${escapeHtml(student.pole)} • <strong>${escapeHtml(student.year)}</strong>
          </div>

          <div class="badge-access-tags">
            <span class="event-badge ${student.gala ? 'badge-yes' : 'badge-no'}">
              🎟️ Gala: ${student.gala ? 'OUI' : 'Non'}
            </span>
            <span class="event-badge ${student.teambuilding ? 'badge-yes' : 'badge-no'}">
              🏃 Team: ${student.teambuilding ? 'OUI' : 'Non'}
            </span>
            <span class="event-badge ${student.transport ? 'badge-yes' : 'badge-no'}">
              🚌 Transport: ${student.transport ? 'OUI' : 'Non'}
            </span>
          </div>

          <div style="margin-top: 1rem; font-size: 0.75rem; color: var(--gray-400);">
            Présentez ce QR Code au guichet d'accueil
          </div>
        </div>
      </div>
    `;

    modal.classList.add('open');

    // Generate QR Code inside target
    setTimeout(() => {
      const qrTarget = document.getElementById('ticketQrTarget');
      if (qrTarget && window.QRCode) {
        new window.QRCode(qrTarget, {
          text: student.id,
          width: 170,
          height: 170,
          colorDark: "#0b2545",
          colorLight: "#ffffff"
        });
      }
    }, 50);

    // Setup action buttons
    const printBtn = document.getElementById('btnPrintBadge');
    if (printBtn) {
      printBtn.onclick = () => {
        window.print();
      };
    }
  };

  window.closeBadgeModal = function() {
    const modal = document.getElementById('badgeModal');
    if (modal) modal.classList.remove('open');
  };

  // --- Batch Badges Generator (Tab 4) ---
  function renderBatchBadges() {
    const container = document.getElementById('batchBadgesGrid');
    if (!container) return;

    const filtered = getFilteredStudents().slice(0, 60); // render max 60 at a time for smooth performance
    container.innerHTML = filtered.map(s => `
      <div class="student-badge-ticket" style="margin: 0; width: 100%;">
        <div class="badge-ticket-header" style="padding: 0.6rem;">
          <div style="font-size: 0.65rem; opacity: 0.9;">UPSSA ÉVÉNEMENT</div>
          <h4 style="font-size: 0.95rem;">${escapeHtml(s.name)}</h4>
        </div>
        <div class="badge-ticket-body" style="padding: 0.85rem;">
          <div class="badge-qr-box" id="batch_qr_${s.id}" style="margin-bottom: 0.5rem;"></div>
          <div class="badge-student-id" style="margin-bottom: 0.35rem;">ID: ${escapeHtml(s.id)}</div>
          <div style="font-size: 0.75rem; color: var(--gray-600);">${escapeHtml(s.pole)} - ${escapeHtml(s.year)}</div>
          <div class="badge-access-tags" style="margin-top: 0.35rem; font-size: 0.7rem;">
            <span>${s.gala ? '🎟️ Gala' : ''}</span>
            <span>${s.teambuilding ? '🏃 Team' : ''}</span>
            <span>${s.transport ? '🚌 Bus' : ''}</span>
          </div>
        </div>
      </div>
    `).join('');

    // Render QR codes
    setTimeout(() => {
      filtered.forEach(s => {
        const target = document.getElementById(`batch_qr_${s.id}`);
        if (target && window.QRCode) {
          new window.QRCode(target, {
            text: s.id,
            width: 120,
            height: 120,
            colorDark: "#0b2545",
            colorLight: "#ffffff"
          });
        }
      });
    }, 60);
  }

  // --- CSV Export (UTF-8 BOM compatible with Excel) ---
  function exportAttendanceCSV() {
    const headers = [
      'Identifiant',
      'Prénom / Nom',
      'Courriel',
      'Fiche étudiant',
      'Pôle',
      'Année',
      'Téléphone',
      'Participe Gala',
      'Participe Teambuilding',
      'Transport UPSSA',
      'Statut Présence',
      'Heure de Pointage',
      'Horodatage ISO'
    ];

    const rows = students.map(s => [
      `"${(s.id || '').replace(/"/g, '""')}"`,
      `"${(s.name || '').replace(/"/g, '""')}"`,
      `"${(s.email || '').replace(/"/g, '""')}"`,
      `"${(s.file_status || '').replace(/"/g, '""')}"`,
      `"${(s.pole || '').replace(/"/g, '""')}"`,
      `"${(s.year || '').replace(/"/g, '""')}"`,
      `"${(s.phone || '').replace(/"/g, '""')}"`,
      s.gala ? '1' : '0',
      s.teambuilding ? '1' : '0',
      s.transport ? 'Oui' : 'Non',
      s.attended ? 'PRÉSENT' : 'ABSENT',
      `"${s.scanned_time || ''}"`,
      `"${s.scanned_at || ''}"`
    ]);

    const csvContent = '\uFEFF' + [headers.join(','), ...rows.map(r => r.join(','))].join('\r\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');

    const dateStr = new Date().toISOString().slice(0, 10);
    link.setAttribute('href', url);
    link.setAttribute('download', `UPSSA_Presences_Scannees_${dateStr}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);

    showToast('Fichier Excel / CSV exporté avec succès !', 'success');
  }

  // --- Reset Functions ---
  function resetAllAttendance() {
    if (!confirm('Êtes-vous sûr de vouloir réinitialiser TOUS les pointages de présence ? Cette action effacera les scans actuels.')) {
      return;
    }

    students.forEach(s => {
      s.attended = false;
      delete s.scanned_at;
      delete s.scanned_time;
    });

    scansHistory = [];
    saveData();
    updateStats();
    renderActivityFeed();
    renderStudentsTable();

    const box = document.getElementById('scanResultBox');
    if (box) {
      box.innerHTML = `
        <div class="result-card" style="text-align: center; color: var(--gray-500); padding: 2.5rem;">
          <div style="font-size: 2.5rem; margin-bottom: 0.5rem;">🔄</div>
          <h3 style="color: var(--gray-800); margin-bottom: 0.25rem;">Pointages réinitialisés</h3>
          <p>Tous les étudiants sont maintenant marqués comme en attente.</p>
        </div>
      `;
    }

    showToast('Toutes les présences ont été remises à zéro', 'warning');
  }

  // --- Test / Demo Random Scan ---
  function testRandomScan() {
    if (students.length === 0) return;
    const randomStudent = students[Math.floor(Math.random() * students.length)];
    processScan(randomStudent.id);
  }

  // --- Setup Event Listeners ---
  function setupEvents() {
    // Nav Tabs
    document.querySelectorAll('.tab-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const targetTab = btn.getAttribute('data-tab');
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));

        btn.classList.add('active');
        const pane = document.getElementById(targetTab);
        if (pane) pane.classList.add('active');

        if (targetTab === 'tabBadges') {
          renderBatchBadges();
        }
        if (targetTab === 'tabWhatsApp') {
          renderWhatsAppTab();
        }
      });
    });

    // Camera Controls
    const startScanBtn = document.getElementById('startScanBtn');
    const stopScanBtn = document.getElementById('stopScanBtn');
    if (startScanBtn) startScanBtn.addEventListener('click', startCameraScanner);
    if (stopScanBtn) stopScanBtn.addEventListener('click', stopCameraScanner);

    const cameraSelect = document.getElementById('cameraSelect');
    if (cameraSelect) {
      cameraSelect.addEventListener('change', () => {
        if (isScanning) {
          stopCameraScanner();
          setTimeout(startCameraScanner, 300);
        }
      });
    }

    // Manual Input Form & 4-Digit Auto Check-in
    const manualForm = document.getElementById('manualScanForm');
    const manualInput = document.getElementById('manualCodeInput');
    const autoSubmitCheck = document.getElementById('autoSubmitCheck');

    if (manualForm && manualInput) {
      manualForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const val = manualInput.value.trim();
        if (val) {
          processScan(val, 'manual_input');
          manualInput.value = '';
          manualInput.focus();
        }
      });

      // Auto-validation immédiate dès que 4 chiffres sont tapés
      manualInput.addEventListener('input', () => {
        const val = manualInput.value.trim();
        if (autoSubmitCheck && autoSubmitCheck.checked) {
          if (/^\d{4}$/.test(val)) {
            processScan(val, 'touch_numpad');
            manualInput.value = '';
          }
        }
      });
    }

    // Toggle Touch Numpad
    const btnToggleNumpad = document.getElementById('btnToggleNumpad');
    const touchNumpad = document.getElementById('touchNumpad');
    if (btnToggleNumpad && touchNumpad) {
      btnToggleNumpad.addEventListener('click', () => {
        touchNumpad.style.display = touchNumpad.style.display === 'none' ? 'grid' : 'none';
      });
    }

    // Touch Numpad keys
    document.querySelectorAll('.num-key[data-key]').forEach(btn => {
      btn.addEventListener('click', () => {
        const digit = btn.getAttribute('data-key');
        if (manualInput) {
          manualInput.value += digit;
          manualInput.dispatchEvent(new Event('input'));
        }
      });
    });

    const btnNumClear = document.getElementById('btnNumClear');
    if (btnNumClear && manualInput) {
      btnNumClear.addEventListener('click', () => {
        manualInput.value = '';
        manualInput.focus();
      });
    }

    const btnNumEnter = document.getElementById('btnNumEnter');
    if (btnNumEnter && manualForm) {
      btnNumEnter.addEventListener('click', () => {
        manualForm.dispatchEvent(new Event('submit'));
      });
    }

    // Drag & Drop Image Scanner
    const dropZone = document.getElementById('dragDropZone');
    const fileInput = document.getElementById('qrFileInput');
    if (dropZone && fileInput) {
      dropZone.addEventListener('click', () => fileInput.click());

      dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('dragover');
      });

      dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));

      dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('dragover');
        if (e.dataTransfer.files && e.dataTransfer.files[0]) {
          scanImageFile(e.dataTransfer.files[0]);
        }
      });

      fileInput.addEventListener('change', () => {
        if (fileInput.files && fileInput.files[0]) {
          scanImageFile(fileInput.files[0]);
        }
      });
    }

    // Table Search & Filters
    ['searchInput', 'filterStatus', 'filterPole', 'filterYear', 'filterEvent'].forEach(id => {
      const el = document.getElementById(id);
      if (el) {
        el.addEventListener('input', () => {
          currentPage = 1;
          renderStudentsTable();
        });
      }
    });

    // WhatsApp Search & Filters
    ['waSearchInput', 'waFilterStatus', 'waFilterPole', 'waFilterTransport'].forEach(id => {
      const el = document.getElementById(id);
      if (el) {
        el.addEventListener('input', () => {
          waCurrentPage = 1;
          renderWhatsAppTab();
        });
      }
    });

    const btnOpenTemplate = document.getElementById('btnOpenMsgTemplate');
    if (btnOpenTemplate) {
      btnOpenTemplate.addEventListener('click', () => {
        window.previewWa(students[0]?.id || '');
      });
    }

    const waModal = document.getElementById('waModal');
    if (waModal) {
      waModal.addEventListener('click', (e) => {
        if (e.target === waModal) window.closeWaModal();
      });
    }

    // Test Scan Button
    const testScanBtn = document.getElementById('testScanBtn');
    if (testScanBtn) testScanBtn.addEventListener('click', testRandomScan);

    // Export CSV Button
    const exportBtn = document.getElementById('exportCsvBtn');
    if (exportBtn) exportBtn.addEventListener('click', exportAttendanceCSV);

    // Reset Attendance Button
    const resetBtn = document.getElementById('resetAttendanceBtn');
    if (resetBtn) resetBtn.addEventListener('click', resetAllAttendance);

    // Modal close on backdrop click
    const badgeModal = document.getElementById('badgeModal');
    if (badgeModal) {
      badgeModal.addEventListener('click', (e) => {
        if (e.target === badgeModal) window.closeBadgeModal();
      });
    }
  }

  function scanImageFile(file) {
    if (!window.Html5Qrcode) {
      showToast('Module de scan d’image indisponible', 'error');
      return;
    }

    const scanner = new Html5Qrcode("qrImageReaderTemp");
    showToast('Analyse de l’image du QR code en cours...', 'info');

    scanner.scanFile(file, true)
      .then(decodedText => {
        processScan(decodedText, 'image_file');
        scanner.clear();
      })
      .catch(err => {
        console.warn('Image QR scan failed:', err);
        showToast('Aucun QR code lisible détecté sur cette image.', 'error');
        scanner.clear();
      });
  }

  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  // --- Startup ---
  window.addEventListener('DOMContentLoaded', () => {
    loadData();
    setupEvents();
    updateStats();
    renderActivityFeed();
    renderStudentsTable();

    // Check Html5Qrcode availability
    if (typeof Html5Qrcode !== 'undefined') {
      initScanner();
    } else {
      // Retry once CDN loads
      window.addEventListener('load', () => {
        if (typeof Html5Qrcode !== 'undefined') initScanner();
      });
    }
  });


  // =========================================================================
  // WHATSAPP BROADCAST & DISPATCH ENGINE
  // =========================================================================
  let waCurrentPage = 1;
  const waPageSize = 25;
  let expressPendingIndex = 0;

  function formatWaPhone(raw) {
    if (!raw) return '';
    let s = String(raw).replace(/[^\d+]/g, '').trim();
    if (s.startsWith('+')) s = s.substring(1);
    if (s.startsWith('00')) s = s.substring(2);
    if (s.startsWith('0') && s.length === 10) return '212' + s.substring(1);
    if (s.length === 9 && (s.startsWith('6') || s.startsWith('7') || s.startsWith('5'))) return '212' + s;
    return s;
  }

  function getWaMessageText(s) {
    const name = s.name || 'étudiant(e)';
    const id = s.id || '';
    const transportLine = s.transport 
      ? 'Rendez-vous à 11h30 au campus pour un départ à 12h précises, pour les étudiants ayant réservé le transport.'
      : 'Non réservé (accès direct par vos propres moyens au Hyatt Place Taghazout).';
    const origin = window.location.origin.includes('localhost') ? window.location.origin : window.location.origin;
    const ticketUrl = `${origin}/ticket?id=${id}`;

    return `🎉 *UPSSA ONBOARD | CONFIRMATION OFFICIELLE*

Cher(e) ${name},

Nous avons le plaisir de vous confirmer votre inscription à la journée *UPSSA ONBOARD – Team Building & Soirée*, qui se tiendra *mercredi 18 novembre 2026, au Hyatt Place Taghazout !* 🎉

✨ Une journée exceptionnelle vous attend, entre challenges, esprit d'équipe, rencontres et ambiance festive !

🎟️ *Votre QR Code personnel est joint à ce message.* Il devra obligatoirement être présenté et scanné à votre arrivée pour accéder à l'événement.
*(Code d'accès : ${id})*

⚠️ *Important :* Votre inscription est valable pour l'ensemble du programme (Team Building + Soirée). L'accès uniquement à la soirée ne sera pas autorisé.

🚌 *Transport UPSSA :* ${transportLine}

🔗 *Lien direct vers votre e-Billet & QR Code :*
${ticketUrl}

Nous comptons sur votre présence et votre ponctualité pour faire de cette journée un moment inoubliable !

See you 🚀

*UPSSA Student Life*`;
  }

  function getWaLinks(s) {
    const phone = s.phone_wa || formatWaPhone(s.phone);
    const msg = getWaMessageText(s);
    const encoded = encodeURIComponent(msg);
    return {
      phone,
      msg,
      wa_me: `https://wa.me/${phone}?text=${encoded}`,
      web_wa: `https://web.whatsapp.com/send?phone=${phone}&text=${encoded}`,
      app_wa: `whatsapp://send?phone=${phone}&text=${encoded}`
    };
  }

  function getFilteredWaStudents() {
    const search = (document.getElementById('waSearchInput')?.value || '').toLowerCase().trim();
    const filterStatus = document.getElementById('waFilterStatus')?.value || 'all';
    const filterPole = document.getElementById('waFilterPole')?.value || 'all';
    const filterTransport = document.getElementById('waFilterTransport')?.value || 'all';

    return students.filter(s => {
      if (search) {
        const full = `${s.name} ${s.id} ${s.phone} ${s.phone_wa || ''} ${s.pole}`.toLowerCase();
        if (!full.includes(search)) return false;
      }
      if (filterStatus === 'sent' && s.whatsapp_status !== 'sent') return false;
      if (filterStatus === 'pending' && s.whatsapp_status === 'sent') return false;
      if (filterPole !== 'all' && s.pole !== filterPole) return false;
      if (filterTransport === '1' && !s.transport) return false;
      if (filterTransport === '0' && s.transport) return false;
      return true;
    });
  }

  function renderWhatsAppTab() {
    const total = students.length;
    const sentCount = students.filter(s => s.whatsapp_status === 'sent').length;
    const pendingCount = total - sentCount;
    const pct = total > 0 ? Math.round((sentCount / total) * 100) : 0;

    // Update Ribbon & Badges
    setText('kpiWaRibbon', `${sentCount}/${total}`);
    setText('tabCountWa', `${sentCount}/${total}`);
    setText('waSentVal', `${sentCount} / ${total}`);
    setText('waSentPct', `${pct}% des messages envoyés`);
    setText('waPendingVal', pendingCount);

    const bar = document.getElementById('waProgressBar');
    if (bar) bar.style.width = `${pct}%`;

    // Express Queue Card: find first pending student
    const pendingStudents = students.filter(s => s.whatsapp_status !== 'sent');
    const expressCard = document.getElementById('waExpressCard');
    if (expressCard) {
      if (pendingStudents.length === 0) {
        expressCard.innerHTML = `
          <div style="text-align: center; width: 100%; padding: 1.25rem; color: #15803d; font-weight: 800; font-size: 1.15rem;">
            🎉 Félicitations ! Tous les messages WhatsApp ont été envoyés avec succès (309/309) !
          </div>
        `;
      } else {
        if (expressPendingIndex >= pendingStudents.length) expressPendingIndex = 0;
        const cur = pendingStudents[expressPendingIndex];
        const phoneFmt = cur.phone_wa || formatWaPhone(cur.phone);
        
        setText('expressAvatar', (cur.name || 'U').charAt(0).toUpperCase());
        setText('expressName', cur.name);
        setText('expressPhone', `📞 +${phoneFmt}`);
        setText('expressPole', `Pôle ${cur.pole} • ${cur.year}`);
        
        const transEl = document.getElementById('expressTransport');
        if (transEl) {
          transEl.innerText = cur.transport ? '🚌 Transport UPSSA (11h30)' : 'Sans transport';
          transEl.style.color = cur.transport ? '#1d4ed8' : '#64748b';
        }

        const qrThumb = document.getElementById('expressQrThumb');
        if (qrThumb) {
          qrThumb.src = `/qrcodes/${cur.id}.png`;
          qrThumb.onclick = () => window.openStudentBadge(cur.id);
        }

        const btnSend = document.getElementById('btnExpressSend');
        if (btnSend) {
          btnSend.onclick = () => window.sendExpressWa(cur.id);
        }

        const btnSkip = document.getElementById('btnExpressSkip');
        if (btnSkip) {
          btnSkip.onclick = () => {
            expressPendingIndex = (expressPendingIndex + 1) % pendingStudents.length;
            renderWhatsAppTab();
          };
        }
      }
    }

    // Render Table
    const tbody = document.getElementById('waTableBody');
    if (!tbody) return;

    const filtered = getFilteredWaStudents();
    const totalFiltered = filtered.length;
    setText('waTableCount', totalFiltered);

    const totalPages = Math.ceil(totalFiltered / waPageSize) || 1;
    if (waCurrentPage > totalPages) waCurrentPage = totalPages;

    const startIdx = (waCurrentPage - 1) * waPageSize;
    const pageItems = filtered.slice(startIdx, startIdx + waPageSize);

    if (pageItems.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="8" style="text-align: center; padding: 2rem; color: var(--gray-400);">
            Aucun étudiant ne correspond aux filtres de diffusion.
          </td>
        </tr>
      `;
      renderWaPagination(0, 0);
      return;
    }

    tbody.innerHTML = pageItems.map(s => {
      const isSent = s.whatsapp_status === 'sent';
      const phoneFmt = s.phone_wa || formatWaPhone(s.phone);
      const isFrance = phoneFmt.startsWith('33');
      const flag = isFrance ? '🇫🇷' : '🇲🇦';

      return `
        <tr>
          <td><code style="font-weight: 700; color: #0c2340;">${escapeHtml(s.id)}</code></td>
          <td>
            <div style="font-weight: 700; color: var(--gray-900);">${escapeHtml(s.name)}</div>
            <div style="font-size: 0.75rem; color: var(--gray-500);">${escapeHtml(s.email || '-')}</div>
          </td>
          <td>
            <span class="event-badge badge-pole-${s.pole === 'Santé' ? 'sante' : (s.pole === 'Sciences' ? 'sciences' : 'audit')}">${escapeHtml(s.pole)}</span>
            <div style="font-size: 0.72rem; color: var(--gray-500); margin-top: 2px;">${escapeHtml(s.year)}</div>
          </td>
          <td>
            <div style="font-size: 0.85rem; font-family: monospace; font-weight: 600;">
              ${flag} +${escapeHtml(phoneFmt)}
            </div>
            <div style="font-size: 0.72rem; color: var(--gray-400);">Orig: ${escapeHtml(s.phone)}</div>
          </td>
          <td>
            ${s.transport 
              ? `<span style="color: #1d4ed8; font-weight: 700; font-size: 0.8rem;">🚌 Oui (11h30)</span>` 
              : `<span style="color: #94a3b8; font-size: 0.8rem;">Non</span>`}
          </td>
          <td>
            <div style="display: flex; gap: 6px; align-items: center;">
              <img src="/qrcodes/${s.id}.png" class="qr-thumb-preview" alt="QR" title="Cliquer pour voir le QR Code" onclick="window.openStudentBadge('${s.id}')">
              <a href="/ticket?id=${s.id}" target="_blank" title="Ouvrir le e-Billet" style="font-size: 1.15rem; text-decoration: none;">🎫</a>
            </div>
          </td>
          <td>
            ${isSent 
              ? `<span class="badge-wa-sent">✓ Envoyé</span>` 
              : `<span class="badge-wa-pending">⏳ En attente</span>`}
          </td>
          <td>
            <div style="display: flex; gap: 0.35rem; justify-content: flex-end; align-items: center;">
              <button 
                class="btn-whatsapp" 
                style="padding: 0.35rem 0.65rem; font-size: 0.8rem;" 
                onclick="window.openWaDirect('${s.id}')" 
                title="Ouvrir la conversation WhatsApp Web">
                📲 Envoyer
              </button>
              <button 
                class="btn btn-sm btn-outline" 
                onclick="window.previewWa('${s.id}')" 
                title="Voir le message formaté">
                💬
              </button>
              <button 
                class="btn btn-sm ${isSent ? 'btn-rose' : 'btn-emerald'}" 
                onclick="window.toggleWaStatus('${s.id}')" 
                title="${isSent ? 'Marquer comme non envoyé' : 'Marquer comme envoyé'}">
                ${isSent ? '✕' : '✓'}
              </button>
            </div>
          </td>
        </tr>
      `;
    }).join('');

    renderWaPagination(totalFiltered, totalPages);
  }

  function renderWaPagination(totalCount, totalPages) {
    const container = document.getElementById('waPagination');
    if (!container) return;

    if (totalCount <= waPageSize) {
      container.innerHTML = `<span style="font-size: 0.8rem; color: var(--gray-500);">Affichage de ${totalCount} étudiant(s)</span>`;
      return;
    }

    container.innerHTML = `
      <div style="display: flex; align-items: center; justify-content: space-between; width: 100%;">
        <span style="font-size: 0.8rem; color: var(--gray-500);">
          Page ${waCurrentPage} sur ${totalPages} (${totalCount} résultats)
        </span>
        <div style="display: flex; gap: 0.35rem;">
          <button class="btn btn-sm btn-outline" onclick="window.changeWaPage(${waCurrentPage - 1})" ${waCurrentPage <= 1 ? 'disabled' : ''}>
            Précédent
          </button>
          <button class="btn btn-sm btn-outline" onclick="window.changeWaPage(${waCurrentPage + 1})" ${waCurrentPage >= totalPages ? 'disabled' : ''}>
            Suivant
          </button>
        </div>
      </div>
    `;
  }

  window.changeWaPage = function(page) {
    waCurrentPage = page;
    renderWhatsAppTab();
  };

  window.openWaDirect = function(stId) {
    const s = students.find(st => st.id === stId);
    if (!s) return;
    const links = getWaLinks(s);
    window.open(links.web_wa, '_blank');
    window.toggleWaStatus(stId, 'sent');
  };

  window.toggleWaStatus = async function(stId, forcedStatus = null) {
    const s = students.find(st => st.id === stId);
    if (!s) return;
    const newStatus = forcedStatus || (s.whatsapp_status === 'sent' ? 'pending' : 'sent');
    s.whatsapp_status = newStatus;
    s.whatsapp_sent_at = newStatus === 'sent' ? new Date().toISOString() : null;

    if (window.location.protocol.startsWith('http')) {
      try {
        await fetch('/api/whatsapp-status', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ id: stId, status: newStatus })
        });
      } catch (e) {
        console.warn('Backend sync failed:', e);
      }
    }

    saveData();
    renderWhatsAppTab();
    showToast(`${s.name} : Statut WhatsApp (${newStatus === 'sent' ? 'Envoyé' : 'En attente'})`, 'info');
  };

  window.sendExpressWa = function(stId) {
    window.openWaDirect(stId);
  };

  window.previewWa = function(stId) {
    const s = students.find(st => st.id === stId) || students[0];
    if (!s) return;
    const links = getWaLinks(s);
    const bubble = document.getElementById('waModalBubble');
    const openBtn = document.getElementById('btnOpenWaModal');
    const copyBtn = document.getElementById('btnCopyWaModal');

    if (bubble) bubble.innerText = links.msg;
    if (openBtn) {
      openBtn.href = links.web_wa;
      openBtn.onclick = () => {
        window.toggleWaStatus(s.id, 'sent');
        window.closeWaModal();
      };
    }
    if (copyBtn) {
      copyBtn.onclick = () => {
        navigator.clipboard.writeText(links.msg).then(() => {
          showToast('Message officiel copié dans le presse-papiers !', 'success');
        });
      };
    }

    const modal = document.getElementById('waModal');
    if (modal) modal.classList.add('open');
  };

  window.closeWaModal = function() {
    const modal = document.getElementById('waModal');
    if (modal) modal.classList.remove('open');
  };

})();

