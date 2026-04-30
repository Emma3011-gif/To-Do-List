let currentFilter = 'all';
let selectedCategory = null;
let tasks = [];
let userProfile = null;
let notificationPermission = false;
let notifiedTasks = new Set();

document.addEventListener('DOMContentLoaded', () => {
    loadProfile();
    loadTasks();
    setupEventListeners();
    requestNotificationPermission();
    startTaskDueChecker();
});

async function loadProfile() {
    try {
        const res = await fetch('/api/profile');
        if (res.ok) {
            userProfile = await res.json();
            document.getElementById('profile-name').textContent = 
                userProfile.first_name ? `${userProfile.first_name} ${userProfile.last_name || ''}`.trim() : 'User';
            document.getElementById('profile-email').textContent = userProfile.email;
        }
    } catch (err) {
        console.error('Failed to load profile', err);
    }
}

function setupEventListeners() {
    document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentFilter = btn.dataset.filter;
            renderTasks();
        });
    });

    document.getElementById('fab').addEventListener('click', openModal);
    document.getElementById('modal-overlay').addEventListener('click', closeModal);

    document.getElementById('task-form').addEventListener('submit', handleCreateTask);

    document.querySelectorAll('#category-pills .pill').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('#category-pills .pill').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            selectedCategory = btn.dataset.category;
        });
    });

    document.getElementById('task-modal').addEventListener('click', (e) => {
        if (e.target === e.currentTarget) closeModal();
    });

    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', () => {
            document.querySelectorAll('.nav-item').forEach(i => {
                i.classList.remove('active');
                i.classList.add('text-gray-400');
            });
            item.classList.add('active');
            item.classList.remove('text-gray-400');
            
            const nav = item.dataset.nav;
            if (nav === 'profile') {
                showProfile();
            } else if (nav === 'home' || nav === 'tasks') {
                hideProfile();
            }
        });
    });
}

async function loadTasks() {
    try {
        const res = await fetch('/api/tasks');
        tasks = await res.json();
        updateStats();
        updateProfileStats();
        renderTasks();
    } catch (err) {
        showToast('Failed to load tasks', 'error');
    }
}

function renderTasks() {
    const list = document.getElementById('task-list');
    const empty = document.getElementById('empty-state');
    let filtered = tasks;

    if (currentFilter === 'active') filtered = tasks.filter(t => !t.completed);
    if (currentFilter === 'completed') filtered = tasks.filter(t => t.completed);

    if (filtered.length === 0) {
        list.innerHTML = '';
        empty.classList.remove('hidden');
        return;
    }

    empty.classList.add('hidden');
    list.innerHTML = filtered.map(task => `
        <div class="glass-card task-card ${task.completed ? 'completed' : ''}" data-id="${task.id}">
            <div class="flex items-start gap-4">
                <button class="task-checkbox ${task.completed ? 'checked' : ''}" onclick="toggleTask(${task.id})">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
                        <polyline points="20 6 9 17 4 12"></polyline>
                    </svg>
                </button>
                <div class="flex-1 min-w-0">
                    <p class="task-title font-semibold text-lg ${task.completed ? 'text-gray-400' : 'text-white'}">${escapeHtml(task.title)}</p>
                    ${task.description ? `<p class="text-gray-400 text-sm mt-1 truncate">${escapeHtml(task.description)}</p>` : ''}
                    <div class="task-meta">
                        ${task.due_date ? `<span>
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="display:inline;vertical-align:middle;margin-right:0.25rem;width:12px;height:12px;">
                                <rect x="3" y="4" width="18" height="18" rx="2"></rect>
                                <line x1="16" y1="2" x2="16" y2="6"></line>
                                <line x1="8" y1="2" x2="8" y2="6"></line>
                                <line x1="3" y1="10" x2="21" y2="10"></line>
                            </svg>
                            ${task.due_date}
                        </span>` : ''}
                        ${task.category_id ? `<span class="cat-badge">${task.category_id}</span>` : ''}
                    </div>
                </div>
                <button class="task-delete" onclick="deleteTask(${task.id})">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:16px;height:16px;">
                        <line x1="18" y1="6" x2="6" y2="18"></line>
                        <line x1="6" y1="6" x2="18" y2="18"></line>
                    </svg>
                </button>
            </div>
        </div>
    `).join('');
}

async function toggleTask(id) {
    try {
        const res = await fetch(`/api/tasks/${id}/toggle`, { method: 'PATCH' });
        if (res.ok) {
            const task = tasks.find(t => t.id === id);
            if (task) {
                task.completed = !task.completed;
                if (task.completed) notifiedTasks.delete(task.id);
            }
            renderTasks();
            updateStats();
        }
    } catch (err) {
        showToast('Failed to update task', 'error');
    }
}

async function deleteTask(id) {
    const card = document.querySelector(`[data-id="${id}"]`);
    if (card) card.classList.add('removing');
    setTimeout(async () => {
        try {
            const res = await fetch(`/api/tasks/${id}`, { method: 'DELETE' });
            if (res.ok) {
                tasks = tasks.filter(t => t.id !== id);
                renderTasks();
                updateStats();
                showToast('Task deleted');
            }
        } catch (err) {
            showToast('Failed to delete task', 'error');
        }
    }, 300);
}

async function handleCreateTask(e) {
    e.preventDefault();
    const title = document.getElementById('task-title').value.trim();
    if (!title) return;

    const date = document.getElementById('task-date').value;
    const time = document.getElementById('task-time').value;
    let due_date = null;
    if (date) {
        due_date = time ? `${date}T${time}:00` : `${date}T00:00:00`;
    }

    const data = {
        title,
        description: document.getElementById('task-description').value.trim(),
        due_date: due_date,
        category_id: selectedCategory
    };

    try {
        const res = await fetch('/api/tasks', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });

        if (res.ok) {
            const newTask = await res.json();
            tasks.unshift(newTask);
            renderTasks();
            updateStats();
            closeModal();
            showToast('Task created!');
            document.getElementById('task-form').reset();
            selectedCategory = null;
            document.querySelectorAll('#category-pills .pill').forEach(b => b.classList.remove('active'));
        }
    } catch (err) {
        showToast('Failed to create task', 'error');
    }
}

function openModal() {
    const modal = document.getElementById('task-modal');
    modal.classList.remove('hidden');
    document.getElementById('task-title').focus();
}

function closeModal() {
    const modal = document.getElementById('task-modal');
    modal.classList.add('hidden');
}

function showProfile() {
    const taskList = document.getElementById('task-list');
    const emptyState = document.getElementById('empty-state');
    const profileSection = document.getElementById('profile-section');
    taskList.classList.add('hidden');
    emptyState.classList.add('hidden');
    profileSection.classList.remove('hidden');
}

function hideProfile() {
    const taskList = document.getElementById('task-list');
    const profileSection = document.getElementById('profile-section');
    taskList.classList.remove('hidden');
    profileSection.classList.add('hidden');
    renderTasks(); // Re-render to show/hide empty state
}

function updateStats() {
    const total = tasks.length;
    const completed = tasks.filter(t => t.completed).length;
    const active = total - completed;
    document.getElementById('task-count').textContent = `${active} active`;
    document.getElementById('task-stats').textContent = `${active} active · ${completed} completed`;
}

function updateProfileStats() {
    const total = tasks.length;
    const completed = tasks.filter(t => t.completed).length;
    const active = total - completed;
    document.getElementById('stat-total').textContent = total;
    document.getElementById('stat-active').textContent = active;
    document.getElementById('stat-completed').textContent = completed;
}

function exportTasks() {
    const dataStr = JSON.stringify(tasks, null, 2);
    const blob = new Blob([dataStr], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'tasks.json';
    a.click();
    URL.revokeObjectURL(url);
    showToast('Tasks exported!');
}

async function clearCompleted() {
    const completedTasks = tasks.filter(t => t.completed);
    if (completedTasks.length === 0) {
        showToast('No completed tasks to clear', 'error');
        return;
    }
    
    if (!confirm(`Clear ${completedTasks.length} completed task(s)?`)) return;
    
    for (const task of completedTasks) {
        await fetch(`/api/tasks/${task.id}`, { method: 'DELETE' });
    }
    
    tasks = tasks.filter(t => !t.completed);
    renderTasks();
    updateStats();
    showToast('Completed tasks cleared!');
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function showToast(message, type = 'success') {
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.style.background = type === 'success' ? 'rgba(0,212,170,0.9)' : 'rgba(255,107,107,0.9)';
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
}

if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/sw.js').catch(() => {});
}

function logout() {
    window.location.href = '/logout';
}

function requestNotificationPermission() {
    if ('Notification' in window && Notification.permission === 'default') {
        if (confirm('Enable notifications for due tasks?')) {
            Notification.requestPermission().then(permission => {
                notificationPermission = permission === 'granted';
                if (permission === 'granted') showToast('Notifications enabled!');
            });
        }
    } else if ('Notification' in window && Notification.permission === 'granted') {
        notificationPermission = true;
    }
}

function startTaskDueChecker() {
    setInterval(() => {
        const now = new Date();
        tasks.forEach(task => {
            if (task.completed || !task.due_date || notifiedTasks.has(task.id)) return;
            const dueDate = new Date(task.due_date);
            const diff = dueDate - now;
            if (diff > 0 && diff <= 60000) {
                notifyTaskDue(task);
            }
        });
    }, 30000);
}

function notifyTaskDue(task) {
    notifiedTasks.add(task.id);
    const message = `Task "${task.title}" is due now!`;
    if (notificationPermission) {
        new Notification('Task Due', { body: message, icon: '/static/icon.png' });
    }
    showToast(message, 'error');
    playNotificationSound();
}

function playNotificationSound() {
    try {
        const audio = new Audio('/static/notification.mp3');
        audio.play();
    } catch (e) {}
}
