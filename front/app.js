// WebSocket connection
let ws = null;
let agents = [];
let selectedAgent = null;

// DOM elements
const agentList = document.getElementById('agent-list');
const newAgentName = document.getElementById('new-agent-name');
const newAgentPort = document.getElementById('new-agent-port');
const createBtn = document.getElementById('create-btn');
const chatInput = document.getElementById('chat-input');
const sendBtn = document.getElementById('send-btn');
const startBtn = document.getElementById('start-btn');
const stopBtn = document.getElementById('stop-btn');
const deleteBtn = document.getElementById('delete-btn');
const contextMessages = document.getElementById('context-messages');
const vncPlaceholder = document.getElementById('vnc-placeholder');
const vncFrame = document.getElementById('vnc-frame');

// Connect to WebSocket
function connect() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(`${protocol}//${window.location.host}/ws`);

    ws.onopen = () => {
        console.log('Connected to server');
    };

    ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        handleMessage(msg);
    };

    ws.onclose = () => {
        console.log('Disconnected, reconnecting in 2s...');
        setTimeout(connect, 2000);
    };

    ws.onerror = (err) => {
        console.error('WebSocket error:', err);
    };
}

// Handle incoming messages
function handleMessage(msg) {
    switch (msg.type) {
        case 'agents':
            agents = msg.agents;
            renderAgentList();
            updateButtons();
            break;

        case 'context':
            if (msg.name === selectedAgent) {
                renderContext(msg.messages);
            }
            break;

        case 'response':
            if (msg.name === selectedAgent) {
                // response received, context will be updated separately
                console.log('Response:', msg.text);
            }
            break;

        case 'error':
            alert('Error: ' + msg.msg);
            break;
    }
}

// Send command to server
function send(cmd) {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify(cmd));
    }
}

// Render agent list
function renderAgentList() {
    agentList.innerHTML = '';
    agents.forEach(agent => {
        const li = document.createElement('li');
        li.innerHTML = `
            <div>${agent.name}</div>
            <div class="status ${agent.running ? 'running' : ''}">
                ${agent.running ? 'running' : 'stopped'} | port ${agent.novnc_port}
            </div>
        `;
        if (agent.name === selectedAgent) {
            li.classList.add('selected');
        }
        li.onclick = () => selectAgent(agent.name);
        agentList.appendChild(li);
    });
}

// Select an agent
function selectAgent(name) {
    selectedAgent = name;
    renderAgentList();
    updateButtons();

    // Get context for this agent
    send({ cmd: 'get_context', name: name });

    // Update VNC viewer
    const agent = agents.find(a => a.name === name);
    if (agent && agent.running) {
        // Connect to noVNC - websockify serves novnc at /vnc.html
        vncFrame.src = `http://localhost:${agent.novnc_port}/vnc.html?autoconnect=true`;
        vncFrame.style.display = 'block';
        vncPlaceholder.style.display = 'none';
    } else {
        vncPlaceholder.textContent = agent ? 'agent not running' : 'select an agent to view';
        vncPlaceholder.style.display = 'block';
        vncFrame.style.display = 'none';
    }
}

// Update button states
function updateButtons() {
    const agent = agents.find(a => a.name === selectedAgent);
    const hasSelection = !!agent;
    const isRunning = agent?.running || false;

    startBtn.disabled = !hasSelection || isRunning;
    stopBtn.disabled = !hasSelection || !isRunning;
    deleteBtn.disabled = !hasSelection;
    sendBtn.disabled = !hasSelection || !isRunning;
}

// Render context messages
function renderContext(messages) {
    contextMessages.innerHTML = '';
    messages.forEach(msg => {
        const div = document.createElement('div');
        div.className = `message ${msg.role}`;

        const roleDiv = document.createElement('div');
        roleDiv.className = 'role';
        roleDiv.textContent = msg.role;

        const contentDiv = document.createElement('div');
        contentDiv.className = 'content';

        // Extract text from content blocks
        let text = '';
        if (msg.content) {
            msg.content.forEach(block => {
                if (block.type === 'text') {
                    text += block.text + '\n';
                } else if (block.type === 'image') {
                    text += '[IMAGE]\n';
                }
            });
        }
        contentDiv.textContent = text.trim();

        div.appendChild(roleDiv);
        div.appendChild(contentDiv);
        contextMessages.appendChild(div);
    });

    // Scroll to bottom
    contextMessages.scrollTop = contextMessages.scrollHeight;
}

// Event listeners
createBtn.onclick = () => {
    const name = newAgentName.value.trim();
    const port = parseInt(newAgentPort.value) || 6080;

    if (!name) {
        alert('Please enter agent name');
        return;
    }

    send({ cmd: 'create', name: name, novnc_port: port });
    newAgentName.value = '';

    // Auto-increment port for next agent
    newAgentPort.value = port + 1;
};

startBtn.onclick = () => {
    if (selectedAgent) {
        send({ cmd: 'start', name: selectedAgent });
    }
};

stopBtn.onclick = () => {
    if (selectedAgent) {
        send({ cmd: 'stop', name: selectedAgent });
    }
};

deleteBtn.onclick = () => {
    if (selectedAgent && confirm(`Delete agent "${selectedAgent}"?`)) {
        send({ cmd: 'delete', name: selectedAgent });
        selectedAgent = null;
        contextMessages.innerHTML = '';
    }
};

sendBtn.onclick = () => {
    const text = chatInput.value.trim();
    if (text && selectedAgent) {
        send({ cmd: 'chat', name: selectedAgent, text: text });
        chatInput.value = '';
    }
};

// Enter to send (Shift+Enter for newline)
chatInput.onkeydown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendBtn.click();
    }
};

// Arrow keys to cycle agents
document.onkeydown = (e) => {
    if (document.activeElement === chatInput) return;

    if (e.key === 'ArrowUp' || e.key === 'ArrowDown') {
        e.preventDefault();
        if (agents.length === 0) return;

        const currentIndex = agents.findIndex(a => a.name === selectedAgent);
        let newIndex;

        if (e.key === 'ArrowUp') {
            newIndex = currentIndex <= 0 ? agents.length - 1 : currentIndex - 1;
        } else {
            newIndex = currentIndex >= agents.length - 1 ? 0 : currentIndex + 1;
        }

        selectAgent(agents[newIndex].name);
    }
};

// Start connection
connect();
