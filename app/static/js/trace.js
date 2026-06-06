class AgentTraceUI {
  constructor(bodyEl) {
    this.el = bodyEl;
    this._cards = {};
  }

  reset() {
    this.el.innerHTML = '<div class="trace-empty">Agent trace will appear here…</div>';
    this._cards = {};
  }

  addAntCard(ant_type, summary) {
    // Remove empty state
    const empty = this.el.querySelector('.trace-empty');
    if (empty) empty.remove();

    const card = document.createElement('div');
    card.className = `ant-card running`;
    card.innerHTML = `
      <div class="ant-card-header">
        <span class="ant-badge ${ant_type}">${ant_type}</span>
        <span class="ant-status running" id="status-${ant_type}">running</span>
      </div>
      <div class="ant-task" style="font-size:12px;color:#aaa;margin-bottom:6px">${this._esc(summary)}</div>
      <div class="ant-output" id="output-${ant_type}"></div>
      <div class="ant-meta" id="meta-${ant_type}"></div>
    `;
    this.el.appendChild(card);
    this._cards[ant_type] = card;
    this.el.scrollTop = this.el.scrollHeight;
    return card;
  }

  updateAntCard(ant_type, token) {
    const out = this.el.querySelector(`#output-${ant_type}`);
    if (out) {
      out.textContent += token;
      out.scrollTop = out.scrollHeight;
    }
  }

  completeAntCard(ant_type, metadata) {
    const card = this._cards[ant_type];
    if (!card) return;
    card.classList.remove('running');
    card.classList.add('completed');
    const status = card.querySelector(`#status-${ant_type}`);
    if (status) { status.textContent = 'done'; status.className = 'ant-status'; }
    const meta = card.querySelector(`#meta-${ant_type}`);
    if (meta && metadata?.tokens) meta.textContent = `${metadata.tokens} tokens`;
  }

  failAntCard(ant_type) {
    const card = this._cards[ant_type];
    if (!card) return;
    card.classList.remove('running');
    card.classList.add('failed');
    const status = card.querySelector(`#status-${ant_type}`);
    if (status) { status.textContent = 'failed'; status.className = 'ant-status'; }
  }

  _esc(str) {
    return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  }
}
