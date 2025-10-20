import { marked } from '../node_modules/marked/lib/marked.esm.js';


console.log('Script loaded');
console.log('Gotten:', document.getElementById('companion-chat-btn'));



document.getElementById('companion-chat-btn').addEventListener('click', toggleChat);

function toggleChat() {
  const chatPopup = document.querySelector('.chat-popup');
  chatPopup.classList.toggle('active');
  if (chatPopup.classList.contains('active')) {
    document.querySelector('#chat-input-box').focus();
    loadChat();
  }
}

document.querySelector('#chat-input-box').addEventListener('input', function() {
  this.style.height = '70px';
  this.style.height = this.scrollHeight + 'px';
});

document.querySelector('#chat-input-box').addEventListener('keydown', function(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    send();
  }
});

async function loadChat(target_claudy_name = "companion") {
    addTempMessage('assistant', 'Loading...');
    const response = await fetch(`http://localhost:8000/chat/${target_claudy_name}`);
    const data = await response.json();
    renderMessages(data.messages);
}

async function send(target_claudy_name = "companion") {
  const text = document.querySelector('#chat-input-box').value.trim();
  if (!text) return;
  const user_message = {role: 'user', content: text};
  document.querySelector('#chat-input-box').value = '';
  document.querySelector('#chat-input-box').style.height = '70px';

  // temporarily display a user message and waiting message
  addTempMessage('user', text);
  addTempMessage('assistant', 'inferencing...');
  
  // get response from backend and render all messages
  const response = await fetch(`http://localhost:8000/chat/${target_claudy_name}`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(user_message)
  }).then(response => response.json()).then(data => {
    renderMessages(data.messages);
  });
}

function addTempMessage(role, content) {
  const messagesContainer = document.getElementById('messages');
  const div = document.createElement('div');
  div.className = `message-${role}`;
  div.innerHTML = marked.parse(content);
  messagesContainer.appendChild(div);
  messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

function renderMessages(messages) {
  const messagesContainer = document.getElementById('messages');
  messagesContainer.innerHTML = '';
  messages.forEach(message => {
    const div = document.createElement('div');
    div.className = `message-${message.role}`;
    div.innerHTML = marked.parse(message.content);
    messagesContainer.appendChild(div);
  });
  messagesContainer.scrollTop = messagesContainer.scrollHeight;
}