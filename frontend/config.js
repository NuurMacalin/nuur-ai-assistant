/* CONFIGURATION — edit this file to connect your FastAPI / Qdrant backend. */
window.NUUR_CONFIG = {
  // Use false for an interactive local preview. Set true to call your real API.
  useApi: true,
  endpoint: '/chat',
  // Your backend should support POST JSON: { message: string, session_id: string }
  timeoutMs: 60000,
  // If your endpoint uses a different format, adapt buildRequest / readAnswer below.
  buildRequest: (message, sessionId) => ({ message, session_id: sessionId }),
  readAnswer: (data) => data.answer ?? data.response ?? data.reply ?? data.message ?? data.result?.answer ?? null,
  readSessionId: (data) => data.session_id ?? data.conversation_id ?? null,
};
