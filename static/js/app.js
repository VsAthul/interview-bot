
const API = 'http://localhost:8000';

const S = {
  candidateId:    null,
  sessionId:      null,
  interviewId:    null,
  name:           '',
  role:           '',
  experience:     0,
  skills:         [],
  questionNum:    0,
  maxQuestions:   7,
  currentQ:       '',
  currentQId:     null,
  difficulty:     'medium',
  scores:         [],
  recording:      false,
  mediaRecorder:  null,
  audioChunks:    [],
  busy:           false,
  timerInterval:  null,
  elapsed:        0,
  answeredCount:  0,
  interviewEnded: false,
  aiSpeaking:     false,
};

function saveState() {
  const persist = {
    candidateId: S.candidateId, sessionId: S.sessionId,
    interviewId: S.interviewId, name: S.name, role: S.role,
    experience: S.experience, skills: S.skills,
    questionNum: S.questionNum, maxQuestions: S.maxQuestions,
    currentQ: S.currentQ, currentQId: S.currentQId,
    difficulty: S.difficulty, scores: S.scores,
    elapsed: S.elapsed, answeredCount: S.answeredCount,
    _greeting: S._greeting || '',
    _firstQ: S._firstQ || '',
  };
  try {
    sessionStorage.setItem('nexushire', JSON.stringify(persist));
  } catch (e) {
    console.warn('sessionStorage write failed:', e);
  }
}

function loadState() {
  try {
    const raw = sessionStorage.getItem('nexushire');
    if (!raw) return;
    const saved = JSON.parse(raw);
    Object.assign(S, saved);
  } catch { /* ignore */ }
}

function esc(s) {
  return String(s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function showErr(id, msg) {
  const el = document.getElementById(id);
  if (!el) return;
  el.textContent = msg;
  el.className = 'alert alert-err show';
}

function hideErr(id) {
  const el = document.getElementById(id);
  if (el) el.className = 'alert';
}

function goTo(page) {
  saveState();
  window.location.href = page;
}


/* ── Tag / Skill Input ── */
function initTagInput() {
  const tagWrap = document.getElementById('tag-wrap');
  const skillInp = document.getElementById('skill-inp');
  if (!tagWrap || !skillInp) return;

  tagWrap.addEventListener('click', () => skillInp.focus());
  skillInp.addEventListener('focus', () => tagWrap.classList.add('focused'));
  skillInp.addEventListener('blur',  () => tagWrap.classList.remove('focused'));

  skillInp.addEventListener('keydown', e => {
    if ((e.key === 'Enter' || e.key === ',') && skillInp.value.trim()) {
      e.preventDefault();
      addSkill(skillInp.value.trim().replace(/,/g, ''));
      skillInp.value = '';
    }
    if (e.key === 'Backspace' && !skillInp.value && S.skills.length) {
      S.skills.pop();
      renderSkills();
    }
  });
}

function addSkill(s) {
  s = s.trim();
  if (!s || S.skills.includes(s)) return;
  S.skills.push(s);
  renderSkills();
}

function renderSkills() {
  const tagWrap = document.getElementById('tag-wrap');
  const skillInp = document.getElementById('skill-inp');
  if (!tagWrap || !skillInp) return;
  tagWrap.querySelectorAll('.chip').forEach(c => c.remove());
  S.skills.forEach((s, i) => {
    const c = document.createElement('div');
    c.className = 'chip';
    c.innerHTML = `${esc(s)}<button onclick="removeSkill(${i})">×</button>`;
    tagWrap.insertBefore(c, skillInp);
  });
}

function removeSkill(i) {
  S.skills.splice(i, 1);
  renderSkills();
}

/* ── Register ── */
async function handleRegister() {
  hideErr('reg-error');
  const name  = document.getElementById('f-name').value.trim();
  const email = document.getElementById('f-email').value.trim();
  const phone = document.getElementById('f-phone').value.trim();
  const exp   = document.getElementById('f-exp').value;
  const role  = document.getElementById('f-role').value;

  if (!name || !email || !exp || !role) {
    showErr('reg-error', 'Please fill in all required fields.'); return;
  }
  if (S.skills.length === 0) {
    showErr('reg-error', 'Add at least one skill to continue.'); return;
  }

  const btn = document.getElementById('reg-btn');
  btn.disabled = true;
  btn.innerHTML = '<span class="spin"></span> Registering…';

  try {
    const res = await fetch(`${API}/api/candidate/register`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name, email, phone: phone || null,
        role, experience: parseInt(exp), skillset: S.skills,
      }),
    });
    const d = await res.json();
    if (!d.success) throw new Error(d.error || 'Registration failed');

    S.candidateId = d.candidate_id;
    S.name = name; S.role = role; S.experience = parseInt(exp);
    saveState();

    document.getElementById('ready-overlay').classList.add('show');
  } catch (err) {
    showErr('reg-error', err.message);
  } finally {
    btn.disabled = false;
    btn.innerHTML = 'Continue to Interview <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M3 8h10M9 4l4 4-4 4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  }
}

function closePopup() {
  document.getElementById('ready-overlay').classList.remove('show');
}

/* ── Start Interview — navigate to interview.html ── */
async function handleStart() {
  const btn = document.getElementById('start-btn');
  btn.disabled = true;
  btn.innerHTML = '<span class="spin"></span> Starting…';

  try {
    // 1. Create session
    const sRes = await fetch(`${API}/api/interview/session`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ candidate_id: S.candidateId }),
    });
    const sD = await sRes.json();
    if (!sD.success) throw new Error(sD.error);
    S.sessionId  = sD.session_id;
    S.interviewId = sD.interview_id;

    // 2. Start → greeting + first question
    const iRes = await fetch(`${API}/api/interview/start`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: S.sessionId, interview_id: S.interviewId }),
    });
    const iD = await iRes.json();
    if (!iD.success) throw new Error(iD.error);

    S.currentQ    = iD.question;
    S.currentQId  = iD.question_id;
    S.questionNum = 1;

    // persist greeting + first question so interview page can pick them up
    S._greeting   = iD.greeting_message;
    S._firstQ     = iD.question;

    saveState();
    window.location.href = '/interview';

  } catch (err) {
    alert('Could not start interview: ' + err.message);
    btn.disabled = false;
    btn.innerHTML = 'Start Interview';
  }
}


let ttsAudio = null;

function initInterview() {
  loadState();
  if (!S.sessionId) { window.location.href = '/'; return; }

  // populate sidebar
  document.getElementById('iv-av').textContent   = S.name[0].toUpperCase();
  document.getElementById('iv-name').textContent = S.name;
  document.getElementById('iv-role').textContent = S.role;
  document.getElementById('iv-exp').textContent  = `⏱ ${S.experience} yr${S.experience !== 1 ? 's' : ''}`;

  const sc = document.getElementById('iv-skills');
  if (sc) sc.innerHTML = S.skills.map(s => `<div class="skill-chip">${esc(s)}</div>`).join('');

  buildQDots();
  updateProgress();
  startTimer();

  // render greeting + first question that were fetched on index.html
  const greeting = S._greeting || '';
  const firstQ   = S._firstQ   || S.currentQ;

  if (greeting) addMsg('agent', greeting);
  setTimeout(() => {
    addMsg('agent', firstQ, true);
    ttsPlay(greeting ? greeting + ' ' + firstQ : firstQ);
    enableInput();
  }, 400);
}

/* ── Progress dots ── */
function buildQDots() {
  const track = document.getElementById('q-track');
  if (!track) return;
  track.innerHTML = '';
  for (let i = 0; i < S.maxQuestions; i++) {
    const d = document.createElement('div');
    d.className = 'q-dot'; d.id = `qd-${i}`;
    track.appendChild(d);
  }
}

function updateProgress() {
  const lbl = document.getElementById('q-label');
  if (lbl) lbl.textContent = `Q ${S.questionNum} / ${S.maxQuestions}`;
  for (let i = 0; i < S.maxQuestions; i++) {
    const d = document.getElementById(`qd-${i}`);
    if (!d) continue;
    d.className = 'q-dot ' + (
      i < S.questionNum - 1 ? 'done' :
      i === S.questionNum - 1 ? 'active' : ''
    );
  }
  const tag = document.getElementById('diff-tag');
  if (tag) {
    tag.textContent = S.difficulty.charAt(0).toUpperCase() + S.difficulty.slice(1);
    tag.className   = `diff-tag diff-${S.difficulty}`;
  }
}

/* ── Timer ── */
function startTimer() {
  S.timerInterval = setInterval(() => {
    S.elapsed++;
    const m = String(Math.floor(S.elapsed / 60)).padStart(2, '0');
    const s = String(S.elapsed % 60).padStart(2, '0');
    const el = document.getElementById('timer');
    if (el) el.textContent = `${m}:${s}`;
  }, 1000);
}

/* ── Messages ── */
function addMsg(role, text) {
  const wrap = document.getElementById('chat-msgs');
  if (!wrap) return;
  const time  = new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' });
  const avTxt = role === 'agent' ? 'AI' : (S.name ? S.name[0].toUpperCase() : 'U');

  const row = document.createElement('div');
  row.className = `msg-row ${role}`;
  row.innerHTML = `
    <div class="msg-av">${avTxt}</div>
    <div class="msg-body">
      <div class="msg-bubble">${esc(text)}</div>
      <div class="msg-meta">${time}</div>
    </div>`;
  wrap.appendChild(row);
  wrap.scrollTop = wrap.scrollHeight;
}

function showTyping() {
  const wrap = document.getElementById('chat-msgs');
  if (!wrap) return;
  const el = document.createElement('div');
  el.className = 'msg-row agent'; el.id = 'typing-row';
  el.innerHTML = `<div class="msg-av">AI</div><div class="msg-body"><div class="typing-bubble"><div class="t-dot"></div><div class="t-dot"></div><div class="t-dot"></div></div></div>`;
  wrap.appendChild(el);
  wrap.scrollTop = wrap.scrollHeight;
}

function hideTyping() {
  const el = document.getElementById('typing-row');
  if (el) el.remove();
}

/* ── Input enable / disable ── */
function enableInput() {
  S.busy = false;
  const mic = document.getElementById('mic-btn');
  const st  = document.getElementById('mic-status');
  if (mic) mic.disabled = false;
  if (st)  { st.textContent = 'Click 🎤 to record your answer'; st.className = 'mic-status'; }
}

function disableInput() {
  S.busy = true;
  const mic = document.getElementById('mic-btn');
  const sub = document.getElementById('sub-btn');
  if (mic) mic.disabled = true;
  if (sub) sub.disabled = true;
}

/* ── Mic / Recording ── */
async function toggleMic() {
  if (S.busy) return;
  S.recording ? stopRec() : await startRec();
}

async function startRec() {
  if (S.aiSpeaking) { console.log('AI speaking — recording blocked'); return; }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    S.audioChunks  = [];
    S.mediaRecorder = new MediaRecorder(stream);
    S.mediaRecorder.ondataavailable = e => S.audioChunks.push(e.data);
    S.mediaRecorder.onstop = processAudio;
    S.mediaRecorder.start();
    S.recording = true;

    const mb  = document.getElementById('mic-btn');
    const st  = document.getElementById('mic-status');
    const box = document.getElementById('transcript');
    if (mb)  { mb.classList.add('recording'); mb.textContent = '⏹'; }
    if (st)  { st.textContent = '🔴 Recording… click to stop'; st.className = 'mic-status recording'; }
    if (box) { box.textContent = 'Recording in progress…'; box.classList.remove('filled'); }
  } catch {
    alert('Microphone access denied. Please allow microphone in your browser settings.');
  }
}

function stopRec() {
  if (S.mediaRecorder && S.recording) {
    S.mediaRecorder.stop();
    S.mediaRecorder.stream.getTracks().forEach(t => t.stop());
    S.recording = false;
    const mb = document.getElementById('mic-btn');
    const st = document.getElementById('mic-status');
    if (mb) { mb.classList.remove('recording'); mb.textContent = '🎤'; }
    if (st) { st.textContent = 'Processing audio…'; st.className = 'mic-status processing'; }
  }
}

async function processAudio() {
  const blob = new Blob(S.audioChunks, { type: 'audio/wav' });
  const b64  = await toBase64(blob);
  try {
    const res = await fetch(`${API}/api/stt/transcribe`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: S.sessionId, interview_id: S.interviewId,
        question_id: S.currentQId, audio_file: b64,
      }),
    });
    const d = await res.json();
    if (!d.success) throw new Error(d.error);

    const txt = d.answer_text || '';
    const box = document.getElementById('transcript');
    const sub = document.getElementById('sub-btn');
    const st  = document.getElementById('mic-status');

    if (box) { box.textContent = txt || '(No speech detected — try again)'; box.classList.toggle('filled', !!txt); }
    if (sub) sub.disabled = !txt;
    if (st)  { st.textContent = txt ? 'Transcript ready — submit or re-record' : 'Nothing detected'; st.className = 'mic-status'; }
  } catch (err) {
    const box = document.getElementById('transcript');
    const st  = document.getElementById('mic-status');
    if (box) box.textContent = 'STT error: ' + err.message;
    if (st)  st.textContent = '';
  }
}

function toBase64(blob) {
  return new Promise(res => {
    const r = new FileReader();
    r.onloadend = () => res(r.result.split(',')[1]);
    r.readAsDataURL(blob);
  });
}

/* ── Submit Answer — graph-driven via /submit-answer ── */
async function submitAnswer() {
  const box = document.getElementById('transcript');
  const txt = box ? box.textContent.trim() : '';
  if (!txt || S.busy) return;

  disableInput();
  addMsg('candidate', txt);

  if (box) { box.textContent = 'Your answer will appear here after you record…'; box.classList.remove('filled'); }
  const sub = document.getElementById('sub-btn');
  const st  = document.getElementById('mic-status');
  if (sub) sub.disabled = true;
  if (st)  st.textContent = '';

  showTyping();

  try {
    // Single call to graph-driven endpoint.
    // The backend runs: evaluate_answer → check_completion →
    //   generate_question (if more) OR generate_report (if done)
    const res = await fetch(`${API}/api/interview/submit-answer`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id:  S.sessionId,
        question_id: S.currentQId,
        answer_text: txt,
      }),
    });
    const d = await res.json();
    hideTyping();

    if (!d.success) throw new Error(d.error || 'Submission failed');

    // Collect per-question score returned by the graph
    if (d.last_score !== null && d.last_score !== undefined) {
      S.scores.push({
        question: d.last_question || S.currentQ,
        score:    Math.round(d.last_score / 10),  // graph stores 0-100, display as /10
      });
    }
    S.answeredCount++;

    if (d.is_complete) {
  // Interview already completed by graph
  S.interviewEnded = true;

  if (ttsAudio) {
    ttsAudio.pause();
    ttsAudio.currentTime = 0;
    ttsAudio.src = '';
    ttsAudio = null;
  }

  clearInterval(S.timerInterval);

  saveState();

  window.location.href = '/report';
  return;
}

    // Next question returned from graph
    S.currentQ    = d.question;
    S.currentQId  = d.question_id;
    S.difficulty  = d.difficulty_level || S.difficulty;
    S.questionNum = d.question_number  || S.questionNum + 1;
    saveState();

    addMsg('agent', d.question);
    await ttsPlay(d.question);
    updateProgress();
    enableInput();

  } catch (err) {
    console.error('Submit answer error:', err);
    hideTyping();
    addMsg('agent', 'I had trouble processing your answer. Please try again.');
    enableInput();
  }
}

/* ── TTS ── */
async function ttsPlay(text) {
  if (S.interviewEnded) return;
  try {
    const res = await fetch(`${API}/api/tts/generate`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, voice_type: 'female_en', speed: 1.0 }),
    });
    const d = await res.json();
    if (!d.success || !d.audio_url) return;

    if (ttsAudio) { ttsAudio.pause(); ttsAudio.currentTime = 0; }

    S.aiSpeaking = true;
    const micBtn = document.getElementById('mic-btn');
    if (micBtn) { micBtn.disabled = true; micBtn.classList.add('disabled'); }

    ttsAudio = new Audio(`${API}${d.audio_url}`);
    ttsAudio.preload = 'auto';

    ttsAudio.onerror = () => {
      S.aiSpeaking = false;
      if (micBtn) { micBtn.disabled = false; micBtn.classList.remove('disabled'); }
    };
    ttsAudio.onended = () => {
      S.aiSpeaking = false;
      if (micBtn) { micBtn.disabled = false; micBtn.classList.remove('disabled'); }
    };

    if (!S.interviewEnded) await ttsAudio.play();
  } catch (err) { console.error('TTS error:', err); }
}

/* ── End Interview ── */
function confirmEnd() {
  if (confirm('End the interview now and generate your report?')) endAndReport();
}

async function endAndReport() {
  if (ttsAudio) { ttsAudio.pause(); ttsAudio.currentTime = 0; ttsAudio.src = ''; ttsAudio = null; }
  S.aiSpeaking     = false;
  S.interviewEnded = true;
  clearInterval(S.timerInterval);
  disableInput();
  addMsg('agent', 'Thank you for your time! Generating your performance report now…');
  showTyping();

  try {
    // POST /end — graph runs generate_report node and marks session completed
    const endRes = await fetch(`${API}/api/interview/end`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: S.sessionId }),
    });
    const endD = await endRes.json();
    hideTyping();
    if (!endD.success) throw new Error(endD.error || 'Failed to end interview');

    // Report is now in DB — report page will fetch it via GET /report/:id
    saveState();
    window.location.href = '/report';
  } catch (err) {
    hideTyping();
    addMsg('agent', 'Error ending interview: ' + err.message);
    enableInput();
  }
}


/* ═══════════════════════════════════════════════════════════════
   REPORT.HTML — INTERVIEW REPORT
═══════════════════════════════════════════════════════════════ */

function initReport() {
  loadState();
  if (!S.sessionId) { window.location.href = '/'; return; }
  fetchAndRenderReport();
}

async function fetchAndRenderReport() {
  try {
    // Fetch existing report (GET) + conversation in parallel
    // NOTE: report/generate (POST) is only called once in endAndReport().
    //       Here we use GET /report/:id to read what's already in the DB —
    //       avoids creating a duplicate Report row on every page load.
    const [rRes, cRes] = await Promise.all([
      fetch(`${API}/api/interview/report/${S.sessionId}`),
      fetch(`${API}/api/interview/conversation/${S.sessionId}`),
    ]);

    const rD = await rRes.json();
    const cD = await cRes.json();

    console.log('[Report] report data:', rD);
    console.log('[Report] conversation data:', cD);
    console.log('[Report] scores:', S.scores);

    const r            = rD.success ? rD : {};
    const conversation = cD.conversation || [];

    // header
    document.getElementById('rpt-name').textContent    = S.name;
    document.getElementById('rpt-meta').textContent    = `${S.role} · ${S.experience} yr${S.experience !== 1 ? 's' : ''} experience`;
    document.getElementById('rpt-overall').textContent = r.overall_score       ?? '—';
    document.getElementById('rpt-tech').textContent    = r.technical_score     ?? '—';
    document.getElementById('rpt-comm').textContent    = r.communication_score ?? '—';

    const rec   = (r.recommendation || '').toLowerCase();
    const badge = document.getElementById('rpt-rec');
    badge.textContent = r.recommendation || 'On Hold';
    badge.className   = `rec-pill ${rec === 'selected' ? 'rec-selected' : rec === 'rejected' ? 'rec-rejected' : 'rec-onhold'}`;

    // strengths / improvements
    document.getElementById('rpt-strengths').innerHTML =
      (r.strengths    || []).map(s => `<li>${esc(s)}</li>`).join('') || '<li>—</li>';
    document.getElementById('rpt-improve').innerHTML   =
      (r.improvements || []).map(s => `<li>${esc(s)}</li>`).join('') || '<li>—</li>';

    // conversation — normalise speaker field (API may return 'agent'/'candidate'/'user'/'ai' etc.)
    const convHtml = conversation.map(m => {
      const isAgent = ['agent', 'ai', 'interviewer', 'system'].includes((m.speaker || '').toLowerCase());
      const speakerClass = isAgent ? 'agent' : 'candidate';
      const speakerLabel = isAgent ? '🤖 AI Interviewer' : '👤 ' + esc(S.name);
      const msgText = esc(m.message || m.text || m.content || '');
      const msgTime = m.timestamp ? new Date(m.timestamp).toLocaleTimeString() : '';
      return `
      <div class="conv-item ${speakerClass}">
        <div class="conv-speaker">${speakerLabel}</div>
        <div class="conv-text">${msgText}</div>
        ${msgTime ? `<div class="conv-time">${msgTime}</div>` : ''}
      </div>`;
    }).join('');
    document.getElementById('conv-list').innerHTML =
      convHtml || '<p style="color:var(--muted2);font-size:.88rem;padding:.5rem 0">No conversation recorded.</p>';

    // question-wise scores (from sessionStorage — small data, safe)
    document.getElementById('question-scores').innerHTML =
      S.scores.length
        ? S.scores.map((item, i) => `
            <div class="q-score-item">
              <div class="q-score-question"><strong>Q${i + 1}.</strong> ${esc(item.question)}</div>
              <div class="q-score-mark">${item.score}/10</div>
            </div>`).join('')
        : '<p style="color:var(--muted2);font-size:.88rem;padding:.5rem 0">No scores recorded.</p>';

  } catch (err) {
    console.error('[Report] fetch error:', err);
    document.getElementById('rpt-name').textContent = 'Error loading report';
    document.getElementById('rpt-meta').textContent = err.message;
  }
}

/* ── Tabs ── */
function switchTab(name, el) {
  document.querySelectorAll('.tab-item').forEach(b => b.classList.remove('on'));
  document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('on'));
  el.classList.add('on');
  document.getElementById(`pane-${name}`).classList.add('on');
}

/* ── New Interview ── */
function newInterview() {
  sessionStorage.removeItem('nexushire');
  window.location.href = '/';
}