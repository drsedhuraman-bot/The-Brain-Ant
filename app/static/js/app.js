class BrainAntApp {
  constructor() {
    this.chat = new ChatUI(document.getElementById('messages'));
    this.trace = new AgentTraceUI(document.getElementById('trace-body'));
    this.currentSessionId = null;
    this.currentWs = null;
    this.sending = false;
  }

  async init() {
    document.getElementById('new-session-btn').onclick = () => this.newSession();
    document.getElementById('send-btn').onclick = () => this.sendMessage();
    document.getElementById('user-input').addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); this.sendMessage(); }
    });

    await this.loadSessions();
  }

  async loadSessions() {
    try {
      const sessions = await API.listSessions();
      this._renderSessionList(sessions);
      if (sessions.length > 0) {
        await this.selectSession(sessions[0].id);
      } else {
        await this.newSession();
      }
    } catch (err) {
      console.error('Failed to load sessions:', err);
    }
  }

  async newSession() {
    try {
      const session = await API.createSession('New Chat');
      await this.loadSessions();
      await this.selectSession(session.id);
    } catch (err) {
      console.error('Failed to create session:', err);
    }
  }

  async selectSession(sessionId) {
    this.currentSessionId = sessionId;
    this.chat.clear();
    this.trace.reset();

    // Highlight active item
    document.querySelectorAll('.session-item').forEach(el => {
      el.classList.toggle('active', el.dataset.id === sessionId);
    });

    try {
      const data = await API.getSession(sessionId);
      document.getElementById('chat-header').textContent = data.session?.title || 'Chat';

      // Replay messages
      for (const msg of data.messages || []) {
        if (msg.role === 'user') {
          this.chat.appendUserMessage(msg.content);
        } else if (msg.role === 'assistant') {
          const bubble = this.chat.startAssistantMessage();
          bubble.textContent = msg.content;
          this.chat.finalizeMessage(bubble);
        }
      }
    } catch (err) {
      console.error('Failed to load session:', err);
    }
  }

  async sendMessage() {
    if (this.sending || !this.currentSessionId) return;
    const input = document.getElementById('user-input');
    const text = input.value.trim();
    if (!text) return;

    this.sending = true;
    input.value = '';
    this._setSendDisabled(true);

    this.chat.appendUserMessage(text);
    this.trace.reset();
    const bubble = this.chat.startAssistantMessage();

    try {
      const { task_id } = await API.submitTask(this.currentSessionId, text);

      if (this.currentWs) { try { this.currentWs.close(); } catch {} }

      this.currentWs = API.connectStream(task_id, {
        onBrainThinking: (msg) => {
          if (msg.content) this.chat.appendToken(bubble, msg.content);
        },
        onAntStarted: (msg) => {
          this.trace.addAntCard(msg.ant_type, msg.content || '');
        },
        onAntStreaming: (msg) => {
          this.trace.updateAntCard(msg.ant_type, msg.content || '');
        },
        onAntCompleted: (msg) => {
          this.trace.completeAntCard(msg.ant_type, msg.metadata);
        },
        onTextDelta: (msg) => {
          if (msg.content) this.chat.appendToken(bubble, msg.content);
        },
        onTaskCompleted: () => {
          this.chat.finalizeMessage(bubble);
          this._setSendDisabled(false);
          this.sending = false;
          this.loadSessions(); // refresh sidebar (updated_at)
        },
        onTaskFailed: (msg) => {
          this.chat.showError(bubble, msg.content || 'Unknown error');
          this._setSendDisabled(false);
          this.sending = false;
        },
        onError: () => {
          this.chat.showError(bubble, 'Connection error');
          this._setSendDisabled(false);
          this.sending = false;
        },
      });
    } catch (err) {
      this.chat.showError(bubble, err.message);
      this._setSendDisabled(false);
      this.sending = false;
    }
  }

  _renderSessionList(sessions) {
    const list = document.getElementById('session-list');
    list.innerHTML = '';
    for (const s of sessions) {
      const item = document.createElement('div');
      item.className = 'session-item';
      item.dataset.id = s.id;
      item.innerHTML = `
        <div class="s-title">${this._esc(s.title)}</div>
        <div class="s-date">${new Date(s.updated_at).toLocaleDateString()}</div>
      `;
      item.onclick = () => this.selectSession(s.id);
      list.appendChild(item);
    }
  }

  _setSendDisabled(disabled) {
    document.getElementById('send-btn').disabled = disabled;
    document.getElementById('user-input').disabled = disabled;
  }

  _esc(str) {
    return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  }
}

window.addEventListener('DOMContentLoaded', () => {
  const app = new BrainAntApp();
  app.init();
});
