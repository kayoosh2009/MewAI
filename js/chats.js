const chatContainer = document.getElementById('chatContainer');
const welcomeScreen = document.getElementById('welcomeScreen');
const userTime = document.getElementById('userTime');
const promptInput = document.getElementById('promptInput');
const sendBtn = document.getElementById('sendBtn');
const fileBtn = document.getElementById('fileBtn');
const fileInput = document.getElementById('fileInput');

const modeFast = document.getElementById('modeFast');
const modeThinking = document.getElementById('modeThinking');

let currentMode = 'fast';
let activeChatId = null;

function addMessageCopyButton(msgDiv, textToCopy) {
    // Чтобы не дублировать, если кнопка уже есть
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
// Показ точного времени пользователя над строкой ввода
function updateTime() {
    const now = new Date();
    userTime.textContent = now.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
}
updateTime();
setInterval(updateTime, 60000);

// Интерактивное переключение режимов генерации (fast \ thinking) по клику
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

// Вызов скрытого системного окна выбора файлов
fileBtn.addEventListener('click', () => fileInput.click());

// Динамический расчет высоты строки ввода под объем текста
promptInput.addEventListener('input', function () {
    this.style.height = 'auto';
    this.style.height = (this.scrollHeight) + 'px';
});

// Добавление блоков сообщений на экран
function appendMessage(role, text) {
    if (welcomeScreen && chatContainer.contains(welcomeScreen)) {
        welcomeScreen.remove();
    }

    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${role}`;

    if (role === 'assistant') {
        if (text) { // Если текст не пустой (для истории)
            let html = marked.parse(text);
            html = html.replace(/<pre><code(.*?)>([\s\S]*?)<\/code><\/pre>/g, (match, attrs, code) => {
                return `<div class="code-block"><button class="copy-btn" onclick="copyCode(this)">Copy</button><pre><code${attrs}>${code}</code></pre></div>`;
            });
            msgDiv.innerHTML = html;
            // Добавляем кнопку копирования всего ответа ИИ
            addMessageCopyButton(msgDiv, text);
        }
    } else {
        msgDiv.textContent = text;
        // Добавляем кнопку копирования для сообщения пользователя
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

// Логика взаимодействия с FastAPI бэкендом (генерация со стримингом)
async function handleSendMessage() {
    const content = promptInput.value.trim();
    if (!content) return;

    const userId = localStorage.getItem('mewai_user_id');
    if (!userId) {
        alert('Please log in first');
        // Перенаправить на страницу входа или показать ошибку
        return;
    }

    // Автоматическое создание чата в Supabase при первой реплике
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
            console.error("Chat initialization failed:", err);
            appendMessage('assistant', "Database synchronization error. Please try again.");
            return;
        }
    }

    // Рендерим сообщение пользователя
    appendMessage('user', content);
    promptInput.value = '';
    promptInput.style.height = 'auto';

    // Создаем пустой контейнер под ответ для вывода чанками (Streaming)
    const aiMessageElement = appendMessage('assistant', '');

    try {
        // Запрос к роуту /chat/generate из твоего py/main.py
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

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop(); // Сохраняем незавершенную строку

            // Перед циклом while создаем переменную для накопления сырого текста
            let fullResponseText = "";

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
                                // 1. Копим сырой текст
                                fullResponseText += jsonData.chunk;

                                // 2. Парсим ВЕСЬ текст целиком через marked
                                let parsedHtml = marked.parse(fullResponseText);

                                // 3. Оборачиваем блоки кода в рамки (как у тебя было задумано)
                                parsedHtml = parsedHtml.replace(/<pre><code(.*?)>([\s\S]*?)<\/code><\/pre>/g, (match, attrs, code) => {
                                    return `<div class="code-block"><button class="copy-btn" onclick="copyCode(this)">Copy</button><pre><code${attrs}>${code}</code></pre></div>`;
                                });

                                // 4. Записываем готовый HTML в элемент
                                aiMessageElement.innerHTML = parsedHtml;
                                chatContainer.scrollTop = chatContainer.scrollHeight;
                            }
                        } catch (e) {
                            // Пропускаем ошибки парсинга пустых строк
                        }
                    }
                }
            }

            // Когда стрим ПОЛНОСТЬЮ завершился, добавляем кнопку "Скопировать всё сообщение" вниз пузыря
            addMessageCopyButton(aiMessageElement, fullResponseText);
        }
    } catch (error) {
        console.error("Streaming failed:", error);
        aiMessageElement.textContent = "Error: Failed to stream response from Ollama cloud instance.";
    }
}

// Триггеры на кнопку отправки и на клавишу Enter (без Shift)
sendBtn.addEventListener('click', handleSendMessage);
promptInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSendMessage();
    }
});

// Прием событий переключения истории из левого меню main.html
window.addEventListener('message', async (event) => {
    if (event.data.type === 'LOAD_CHAT_HISTORY' && event.data.chatId) {
        activeChatId = event.data.chatId;
        chatContainer.innerHTML = ''; // Сброс текущих сообщений

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