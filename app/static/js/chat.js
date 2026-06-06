class ChatUI {
  constructor(messagesEl) {
    this.el = messagesEl;
  }

  appendUserMessage(text) {
    const div = this._createMessage('user');
    div.querySelector('.bubble').textContent = text;
    this.el.appendChild(div);
    this._scroll();
  }

  startAssistantMessage() {
    const div = this._createMessage('assistant');
    const bubble = div.querySelector('.bubble');
    bubble.classList.add('streaming');
    bubble.textContent = '';
    this.el.appendChild(div);
    this._scroll();
    return bubble;
  }

  appendToken(bubble, token) {
    bubble.textContent += token;
    this._scroll();
  }

  finalizeMessage(bubble) {
    bubble.classList.remove('streaming');
  }

  showError(bubble, text) {
    bubble.classList.remove('streaming');
    bubble.style.color = '#ef5350';
    bubble.textContent = `Error: ${text}`;
  }

  clear() {
    this.el.innerHTML = '';
  }

  _createMessage(role) {
    const div = document.createElement('div');
    div.className = `message ${role}`;
    div.innerHTML = `
      <div class="avatar">${role === 'user' ? '🧑' : '🧠'}</div>
      <div class="bubble"></div>
    `;
    return div;
  }

  _scroll() {
    this.el.scrollTop = this.el.scrollHeight;
  }
}
