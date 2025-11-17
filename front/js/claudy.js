import { marked } from '../node_modules/marked/lib/marked.esm.js';

console.log(`claudy.js loaded`);

// chat input box

document.querySelectorAll('.claudy-input').forEach(element =>{
    element.addEventListener('keydown', function(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        //TODO: get the target claudy name from the button that was clicked
        const claudyName = element.closest('.card.claudy').dataset.claudy;
        const content = element.value.trim();
        if (!content) return;
        CREATE_message(claudyName, {role: 'user', content: content});
        element.value = '';
    }
    });
});

document.querySelectorAll('.claudy-input').forEach(element =>{
    element.addEventListener('input', function() {
        element.style.height = '50px';
        element.style.height = element.scrollHeight + 'px';
    });
});

// claudy buttons start, stop, summarize
document.querySelectorAll('.card.claudy').forEach(card => {
    const claudyName = card.dataset.claudy;

    card.querySelector('.claudy-button.start')
        .addEventListener('click', () => {
            console.log(`START_agent: ${claudyName}`);
            ws.send(JSON.stringify({
                request_type: 'START_agent',
                claudy_name: claudyName,
            }));
        });

    card.querySelector('.claudy-button.stop')
        .addEventListener('click', () => {
            ws.send(JSON.stringify({
                request_type: 'STOP_agent',
                claudy_name: claudyName,
            }));
        });

    // For summarize later:
    card.querySelector('.claudy-button.summarize')
        .addEventListener('click', () => {
            ws.send(JSON.stringify({
                request_type: 'SUMMARIZE_agent',
                claudy_name: claudyName,
            }));
        });
});


// render messages to screen
function renderMessage(claudyName, message) {
    const claudyCard = document.querySelector(`.card.claudy[data-claudy="${claudyName}"]`);
    const messagesContainer = claudyCard.querySelector('.claudy-messages');
    const div = document.createElement('div');
    div.className = `message-${message.role}`;
    div.innerHTML = marked.parse(message.content);
    messagesContainer.appendChild(div);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

function renderMessages(claudyName, messages) {
    console.log(claudyName)
    const claudyCard = document.querySelector(`.card.claudy[data-claudy="${claudyName}"]`);
    const messagesContainer = claudyCard.querySelector('.claudy-messages');
    messagesContainer.innerHTML = '';
    messages.forEach(message => {
        renderMessage(claudyName, message);
    });
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}


// web socket
const ws = new WebSocket('ws://localhost:8000/ws');

async function READ_messages(claudyName) {
    console.log(`READ_messages: ${claudyName}`);
    ws.send(JSON.stringify({
        request_type: 'READ_messages',
        claudy_name: claudyName
    }));
}

async function CREATE_message(claudyName, message) {
    console.log(`CREATE_message: ${claudyName}`);

    renderMessage(claudyName, message);

    ws.send(JSON.stringify({
        request_type: 'CREATE_message',
        claudy_name: claudyName,
        user_message: message
    }));
}

ws.onmessage = (event) => {
    const data_dict = JSON.parse(event.data);
    switch (data_dict.response_type) {
        case 'READ_message':
            renderMessage(data_dict.claudy_name, data_dict.message);
            break;
        case 'READ_messages':
            renderMessages(data_dict.claudy_name, data_dict.messages);
            break;
    }
};


// on start up
ws.onopen = () => {
    console.log(`ws connected`);
    document.querySelectorAll('.card.claudy').forEach(card => {
        console.log(`on start up loading all chats`);
        const claudyName = card.dataset.claudy;
        READ_messages(claudyName);
    });
};
