const chatContainer = document.getElementById('chatContainer');
const welcomeScreen = document.getElementById('welcomeScreen');
const userTime = document.getElementById('userTime');
const promptInput = document.getElementById('promptInput');
const sendBtn = document.getElementById('sendBtn');
// const fileBtn = document.getElementById('fileBtn'); // УБРАНО - кнопки больше нет
const fileInput = document.getElementById('fileInput');
const modeFast = document.getElementById('modeFast');
const modeThinking = document.getElementById('modeThinking');
let currentMode = 'fast';
let activeChatId = null;

function addMessageCopyButton(msgDiv, textToCopy) {
    if (msgDiv.querySelector('.msg-copy-wrapper')) return;
    const wrapper = document.createElement('div');
    wrapper.className = 'msg-copy-wrapper';

    const btn = document.createElement('button');
    btn.className = 'btn-msg-copy';
    btn.title = 'Copy message text';
    btn.innerHTML = `<img src="../icons/copy.png" alt="Copy"> <span>Copy</span>`;

    btn.addEventListener('click', (e) => {
        e.stopPropagation();
        navigator.clipboard.writeText(textToCopy).then(() => {
            const label = btn.querySelector('span');
            label.textContent = 'Copied!';
            setTimeout(() => label.textContent = 'Copy', 2000);
        });
    });

    wrapper.appendChild(btn);
    msgDiv.appendChild(wrapper);
}

function updateTime() {
    const now = new Date();
    userTime.textContent = now.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
}

updateTime();
setInterval(updateTime, 60000);

modeFast.addEventListener('click', () => {
    currentMode = 'fast';
    modeFast.classList.add('active');
    modeThinking.classList.remove('active');
});

modeThinking.addEventListener('click', () => {
    currentMode = 'thinking';
    modeThinking.classList.add('active');
    modeFast.classList.remove('active');
});

// fileBtn.addEventListener('click', () => fileInput.click()); // УБРАНО - кнопки нет

promptInput.addEventListener('input', function () {
    this.style.height = 'auto';
    this.style.height = (this.scrollHeight) + 'px';
});

function appendMessage(role, text) {
    if (welcomeScreen && chatContainer.contains(welcomeScreen)) {
        welcomeScreen.remove();
        const adContainer = document.querySelector('.ad-container-fixed');
        if (adContainer) {
            adContainer.style.display = 'none';
        }
    }

    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${role}`;

    if (role === 'assistant') {
        if (text) {
            let html = marked.parse(text);
            html = html.replace(/<pre><code(.*?)>([\s\S]*?)<\/code><\/pre>/g, (match, attrs, code) => {
                return `<div class="code-block"><button class="copy-btn" onclick="copyCode(this)">Copy</button><pre><code${attrs}>${code}</code></pre></div>`;
            });
            msgDiv.innerHTML = html;
            addMessageCopyButton(msgDiv, text);
        }
    } else {
        msgDiv.textContent = text;
        addMessageCopyButton(msgDiv, text);
    }

    chatContainer.appendChild(msgDiv);
    chatContainer.scrollTop = chatContainer.scrollHeight;
    return msgDiv;
}

function copyCode(btn) {
    const codeBlock = btn.closest('.code-block').querySelector('code');
    const text = codeBlock.textContent;
    navigator.clipboard.writeText(text).then(() => {
        const oldText = btn.textContent;
        btn.textContent = 'Copied!';
        setTimeout(() => btn.textContent = oldText, 2000);
    });
}

async function handleSendMessage() {
    const content = promptInput.value.trim();
    if (!content) return;
    
    const userId = localStorage.getItem('mewai_user_id');
    if (!userId) {
        alert('Please log in first');
        return;
    }

    if (!activeChatId) {
        try {
            const chatRes = await fetch('http://localhost:7860/chats', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id: userId, title: content.substring(0, 24) })
            });
            const newChat = await chatRes.json();
            activeChatId = newChat.id;
        } catch (err) {
            console.error("Chat initialization failed: ", err);
            appendMessage('assistant', "Database synchronization error. Please try again.");
            return;
        }
    }

    appendMessage('user', content);
    promptInput.value = '';
    promptInput.style.height = 'auto';

    const aiMessageElement = appendMessage('assistant', '');

    try {
        const response = await fetch('http://localhost:7860/chat/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user_id: userId,
                chat_id: activeChatId,
                content: content,
                mode: currentMode,
                stream: true
            })
        });

        if (!response.ok) throw new Error("Generation endpoint offline");

        const reader = response.body.getReader();
        const decoder = new TextDecoder('utf-8');
        let buffer = '';
        let fullResponseText = '';

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop();

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const jsonData = JSON.parse(line.replace('data: ', ''));
                        if (jsonData.chunk) {
                            fullResponseText += jsonData.chunk;
                            let parsedHtml = marked.parse(fullResponseText);
                            parsedHtml = parsedHtml.replace(/<pre><code(.*?)>([\s\S]*?)<\/code><\/pre>/g, (match, attrs, code) => {
                                return `<div class="code-block"><button class="copy-btn" onclick="copyCode(this)">Copy</button><pre><code${attrs}>${code}</code></pre></div>`;
                            });
                            aiMessageElement.innerHTML = parsedHtml;
                            chatContainer.scrollTop = chatContainer.scrollHeight;
                        }
                    } catch (e) {
                        // Пропускаем ошибки парсинга
                    }
                }
            }
        }

        addMessageCopyButton(aiMessageElement, fullResponseText);
    } catch (error) {
        console.error("Streaming failed: ", error);
        aiMessageElement.textContent = "Error: Failed to stream response from Ollama cloud instance.";
    }
}

sendBtn.addEventListener('click', handleSendMessage);

// Enter - отправка, Shift+Enter - новая строка
promptInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSendMessage();
    }
});

window.addEventListener('message', async (event) => {
    if (event.data.type === 'LOAD_CHAT_HISTORY' && event.data.chatId) {
        activeChatId = event.data.chatId;
        chatContainer.innerHTML = '';
        try {
            const historyRes = await fetch(`http://localhost:7860/chat/history/${activeChatId}`);
            const history = await historyRes.json();

            if (history && history.length > 0) {
                history.forEach(msg => {
                    appendMessage(msg.role, msg.content);
                });
            }
        } catch (err) {
            console.error("History recovery error:", err);
            appendMessage('assistant', "Failed to load conversation history from Supabase.");
        }
    }
});