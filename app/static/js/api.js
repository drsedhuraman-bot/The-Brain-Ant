const API = {
  async request(method, path, body) {
    const res = await fetch(path, {
      method,
      headers: body ? { 'Content-Type': 'application/json' } : {},
      body: body ? JSON.stringify(body) : undefined,
    });
    if (!res.ok) {
      const err = await res.text();
      throw new Error(`${method} ${path} → ${res.status}: ${err}`);
    }
    return res.json();
  },

  createSession: (title = 'New Session') =>
    API.request('POST', '/api/sessions', { title }),

  listSessions: () => API.request('GET', '/api/sessions'),

  getSession: (id) => API.request('GET', `/api/sessions/${id}`),

  submitTask: (session_id, user_input) =>
    API.request('POST', '/api/tasks', { session_id, user_input }),

  getTask: (id) => API.request('GET', `/api/tasks/${id}`),

  getTaskRuns: (id) => API.request('GET', `/api/tasks/${id}/runs`),

  connectStream(task_id, callbacks) {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    const ws = new WebSocket(`${proto}://${location.host}/ws/${task_id}`);

    ws.onmessage = (event) => {
      let msg;
      try { msg = JSON.parse(event.data); } catch { return; }
      const type = msg.type;
      const handler = {
        brain_thinking:  callbacks.onBrainThinking,
        ant_started:     callbacks.onAntStarted,
        ant_streaming:   callbacks.onAntStreaming,
        ant_completed:   callbacks.onAntCompleted,
        text_delta:      callbacks.onTextDelta,
        task_completed:  callbacks.onTaskCompleted,
        task_failed:     callbacks.onTaskFailed,
      }[type];
      if (handler) handler(msg);
    };

    ws.onerror = (e) => callbacks.onError && callbacks.onError(e);
    ws.onclose = () => callbacks.onClose && callbacks.onClose();

    return ws;
  },
};
