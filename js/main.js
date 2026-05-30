const menuToggleBtn = document.getElementById('menuToggleBtn');
const leftSidebar = document.getElementById('leftSidebar');
const screenOverlay = document.getElementById('screenOverlay');
const chatsListWrapper = document.getElementById('chatsListWrapper');
const chatIframe = document.getElementById('chatIframe');

// Открытие левого меню при клике на бургер (слева вверху)
menuToggleBtn.addEventListener('click', () => {
    leftSidebar.classList.add('active');
    screenOverlay.classList.add('active');
});

// Закрытие по клику на overlay
screenOverlay.addEventListener('click', () => {
    leftSidebar.classList.remove('active');
    screenOverlay.classList.remove('active');
});

// Загрузка данных из FastAPI бэкенда
async function loadUserChats() {
    const userId = localStorage.getItem('mewai_user_id');
    if (!userId) {
        chatsListWrapper.innerHTML = '<div class="no-chats" style="color: #ff8888;">Please log in first</div>';
        return;
    }

    try {
        const response = await fetch(`http://localhost:7860/chats/${userId}`);
        if (!response.ok) throw new Error("Database offline");

        const chats = await response.json();

        if (chats && chats.length > 0) {
            chatsListWrapper.innerHTML = '';

            chats.forEach(chat => {
                const chatBtn = document.createElement('div');
                chatBtn.className = 'chat-link';
                chatBtn.textContent = chat.title || 'Untitled Chat';

                chatBtn.addEventListener('click', () => {
                    if (chatIframe.contentWindow) {
                        chatIframe.contentWindow.postMessage({
                            type: 'LOAD_CHAT_HISTORY',
                            chatId: chat.id
                        }, '*');
                    }
                    leftSidebar.classList.remove('active');
                    screenOverlay.classList.remove('active');
                });
                chatsListWrapper.appendChild(chatBtn);
            });
        } else {
            chatsListWrapper.innerHTML = '<div class="no-chats">No chats saved yet</div>';
        }
    } catch (error) {
        console.error("FastAPI Error:", error);
        chatsListWrapper.innerHTML = '<div class="no-chats" style="color: #ff8888;">Failed to load chats</div>';
    }
}

window.addEventListener('DOMContentLoaded', loadUserChats);

document.getElementById('logoutBtn').addEventListener('click', () => {
    localStorage.removeItem('mewai_user_id');
    localStorage.removeItem('mewai_user_hash');
    window.location.href = '/';
});