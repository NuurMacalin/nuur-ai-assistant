(() => {
  'use strict';
  const config = window.NUUR_CONFIG;
  const thread = document.getElementById('chatThread');
  const form = document.getElementById('chatForm');
  const input = document.getElementById('messageInput');
  const send = document.getElementById('sendBtn');
  const badge = document.getElementById('modeBadge');
  const notice = document.getElementById('chatNotice');
  const newChat = document.getElementById('newChatBtn');
  const initialThread = Array.from(thread.children, node => node.cloneNode(true));
  const menuBtn = document.getElementById('menuBtn');
  const header = document.querySelector('.site-header');
  const createSessionId = () => (typeof crypto !== 'undefined' && crypto.randomUUID) ? crypto.randomUUID() : `nuur-${Date.now()}-${Math.random().toString(36).slice(2)}`;
  let sessionId = createSessionId();
  let busy = false;
  document.getElementById('year').textContent = new Date().getFullYear();
  if (config.useApi) {
    badge.textContent = 'AI chat'; badge.classList.replace('demo', 'api');
    notice.textContent = "Grounded in Nuur's knowledge base. AI can make mistakes.";
  }
  menuBtn.addEventListener('click', () => { const isOpen = header.classList.toggle('nav-open'); menuBtn.setAttribute('aria-expanded', String(isOpen)); });
  document.querySelectorAll('.main-nav a').forEach(a => a.addEventListener('click', () => { document.querySelectorAll('.main-nav a').forEach(link => link.classList.toggle('active', link === a)); header.classList.remove('nav-open'); menuBtn.setAttribute('aria-expanded', 'false'); }));
  document.addEventListener('keydown', event => { if (event.key === 'Escape') { header.classList.remove('nav-open'); menuBtn.setAttribute('aria-expanded', 'false'); } });
  document.querySelectorAll('a[href="#chat"]').forEach(link => link.addEventListener('click', () => { header.classList.remove('nav-open'); menuBtn.setAttribute('aria-expanded', 'false'); input.focus({preventScroll:true}); }));
  const timeNow = () => new Date().toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'});
  const scrollBottom = () => { thread.scrollTop = thread.scrollHeight; };
  function addMessage(role, message) {
    const wrapper = document.createElement('div'); wrapper.className = `message ${role}`;
    if (role === 'assistant') { const avatar = document.createElement('div'); avatar.className = 'avatar'; avatar.textContent = 'N'; wrapper.appendChild(avatar); }
    const body = document.createElement('div'); body.className = 'bubble';
    const p = document.createElement('p'); p.textContent = message; body.appendChild(p); wrapper.appendChild(body);
    const stamp = document.createElement('time'); stamp.textContent = timeNow(); body.appendChild(stamp);
    thread.appendChild(wrapper); scrollBottom(); return wrapper;
  }
  function setBusy(value) { busy = value; send.disabled = value; input.disabled = value; newChat.disabled = value; thread.setAttribute('aria-busy', String(value)); }
  newChat.addEventListener('click', () => { if (busy) return; thread.replaceChildren(...initialThread.map(node => node.cloneNode(true))); sessionId = createSessionId(); document.getElementById('suggestions').classList.remove('used'); input.value = ''; input.style.height = ''; input.focus({preventScroll:true}); });
  function demoAnswer(question) {
    const q = question.toLowerCase();
    if (/who|about|nuur|yourself|kuma|yaa tahay/.test(q)) return 'Nuur Macalin Isaaq Caddow is a Somali software developer, co-founder of Mudnaan Technology and a developer at Raed Innovation ICT. He has approximately 2.5 years of overall software development experience and graduated from university in 2024.';
    if (/skill|technology|stack|aqoon|xirfad/.test(q)) return 'His technologies include Python, FastAPI, PHP, CodeIgniter 4, MySQL, SQLModel, Flutter and Dart, with Django/DRF fundamentals. He is also exploring Generative AI, LLMs, RAG, Qdrant and agentic workflows.';
    if (/mudnaan|founder|company|shirkad/.test(q)) return 'Nuur is a co-founder of Mudnaan Technology. His work focuses on planning and developing practical digital solutions, including exploring AI-enhanced applications.';
    if (/raed|work|job|experience|khibrad/.test(q)) return 'Nuur currently works as a developer at Raed Innovation ICT. His approximately 2.5 years of experience covers his broader software development journey, not only his current employer.';
    if (/github|project|portfolio|repo/.test(q)) return 'You can see his public repositories at github.com/NuurMacalin, including FastAPI work and Flutter projects. Employer-owned systems are not presented as his personal repositories.';
    if (/ai|llm|agent|qdrant|rag/.test(q)) return 'Nuur explores practical AI applications using LLMs, retrieval-augmented generation (RAG), vector databases such as Qdrant, and agent-style workflows. Connect the real API for answers grounded in his knowledge base.';
    return 'Thanks for asking! This page is currently in demo mode. Connect your FastAPI + Qdrant endpoint in config.js to answer specific questions using Nuur’s knowledge-base PDF.';
  }
  async function apiAnswer(message) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), config.timeoutMs ?? 45000);
    try {
      const response = await fetch(config.endpoint, {
        method: 'POST', headers: {'Content-Type':'application/json'},
        body: JSON.stringify(config.buildRequest(message, sessionId)), signal: controller.signal
      });
      if (!response.ok) { let details = ''; try { const error = await response.json(); details = error.detail ? ` — ${typeof error.detail === 'string' ? error.detail : JSON.stringify(error.detail)}` : ''; } catch {} throw new Error(`HTTP ${response.status}${details}`); }
      const data = await response.json();
      const answer = config.readAnswer(data);
      if (typeof answer !== 'string') throw new Error('API response is missing a text answer. Update readAnswer in config.js.');
      const returnedId = config.readSessionId(data);
      if (returnedId) sessionId = String(returnedId);
      return answer;
    } finally { clearTimeout(timeout); }
  }
  async function ask(question) {
    const text = String(question ?? '').trim(); if (!text || busy) return;
    document.getElementById('suggestions').classList.add('used');
    addMessage('user', text); input.value = ''; input.style.height = ''; setBusy(true);
    const loading = addMessage('assistant', 'Thinking…'); loading.classList.add('loading-message');
    try {
      const answer = config.useApi ? await apiAnswer(text) : await new Promise(resolve => setTimeout(() => resolve(demoAnswer(text)), 580));
      loading.remove(); addMessage('assistant', answer);
    } catch (error) {
      loading.remove();
      const explanation = error.name === 'AbortError' ? 'The request timed out.' : error.message;
      addMessage('assistant', `Sorry, I couldn't get an answer. ${explanation} Please try again shortly.`);
    } finally { setBusy(false); input.focus({preventScroll:true}); }
  }
  form.addEventListener('submit', e => { e.preventDefault(); ask(input.value); });
  input.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); ask(input.value); } });
  input.addEventListener('input', () => { input.style.height = 'auto'; input.style.height = `${Math.min(input.scrollHeight, 125)}px`; });
  document.querySelectorAll('[data-question]').forEach(btn => btn.addEventListener('click', () => ask(btn.dataset.question)));
})();
