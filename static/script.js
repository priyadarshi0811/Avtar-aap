const loginPage = document.getElementById('loginPage');
const adminPage = document.getElementById('adminPage');
const logoutBtn = document.getElementById('logoutBtn');
const themeToggle = document.getElementById('themeToggle');

// API base URL
const API_BASE = 'http://localhost:8000/api';

// Initialize the application
document.addEventListener('DOMContentLoaded', function() {
    setupEventListeners();
    loadGeneratedAvatars();
    loadPushedAvatars();
});

function setupEventListeners() {
    // Avatar form submission
    document.getElementById('avatarForm').addEventListener('submit', handleAvatarGeneration);
    
    // Logout button
    logoutBtn.addEventListener('click', () => {
        adminPage.classList.add('hidden');
        loginPage.classList.remove('hidden');
        logoutBtn.classList.add('hidden');
    });

    // Theme toggle
    themeToggle.addEventListener('click', () => {
        const currentTheme = document.body.getAttribute('data-theme');
        if (currentTheme === 'light') {
            document.body.setAttribute('data-theme', 'dark');
            themeToggle.textContent = '☀️';
        } else {
            document.body.setAttribute('data-theme', 'light');
            themeToggle.textContent = '🌙';
        }
    });
}

function login() {
    const username = "admin";
    const password = "admin123";

    const enteredUser = prompt("Enter username:", "");
    const enteredPass = prompt("Enter password:", "");

    if (enteredUser === username && enteredPass === password) {
        loginPage.classList.add('hidden');
        adminPage.classList.remove('hidden');
        logoutBtn.classList.remove('hidden');
        // Load avatars when logging in
        loadGeneratedAvatars();
        loadPushedAvatars();
    } else {
        alert("Invalid credentials!");
    }
}

function showSection(sectionId) {
    const sections = document.querySelectorAll('.section');
    sections.forEach(section => section.classList.add('hidden'));
    document.getElementById(`${sectionId}-section`).classList.remove('hidden');

    const links = document.querySelectorAll('.nav-links a');
    links.forEach(link => link.classList.remove('active'));
    event.currentTarget.classList.add('active');

    // Reload data when switching sections
    if (sectionId === 'generated') {
        loadGeneratedAvatars();
    } else if (sectionId === 'pushed') {
        loadPushedAvatars();
    }
}

async function handleAvatarGeneration(event) {
    event.preventDefault();
    
    const audioFile = document.getElementById('audioFile').files[0];
    const mediaFile = document.getElementById('mediaFile').files[0];
    const generateBtn = document.getElementById('generateBtn');
    const statusDiv = document.getElementById('generationStatus');
    const statusMessage = document.getElementById('statusMessage');
    
    if (!audioFile || !mediaFile) {
        alert('Please select both audio and media files');
        return;
    }
    
    // Show loading state
    generateBtn.disabled = true;
    generateBtn.textContent = 'Generating...';
    statusDiv.classList.remove('hidden');
    statusMessage.textContent = 'Uploading files and generating avatar...';
    
    try {
        const formData = new FormData();
        formData.append('audio_file', audioFile);
        formData.append('media_file', mediaFile);
        
        const response = await fetch(`${API_BASE}/generate-avatar`, {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        
        if (result.success) {
            statusMessage.textContent = 'Avatar generated successfully!';
            setTimeout(() => {
                statusDiv.classList.add('hidden');
                document.getElementById('avatarForm').reset();
                loadGeneratedAvatars();
                // Switch to generated avatars section
                showSection('generated');
            }, 2000);
        } else {
            throw new Error(result.message || 'Generation failed');
        }
        
    } catch (error) {
        console.error('Error generating avatar:', error);
        statusMessage.textContent = `Error: ${error.message}`;
        setTimeout(() => {
            statusDiv.classList.add('hidden');
        }, 3000);
    } finally {
        generateBtn.disabled = false;
        generateBtn.textContent = '🚀 Generate Avatar';
    }
}

async function loadGeneratedAvatars() {
    try {
        const response = await fetch(`${API_BASE}/generated-avatars`);
        const result = await response.json();
        
        const container = document.getElementById('generatedAvatars');
        const noAvatarsMessage = document.getElementById('noGeneratedAvatars');
        
        if (result.success && result.avatars.length > 0) {
            container.innerHTML = result.avatars.map(avatar => createAvatarCard(avatar, 'generated')).join('');
            container.classList.remove('hidden');
            noAvatarsMessage.classList.add('hidden');
        } else {
            container.classList.add('hidden');
            noAvatarsMessage.classList.remove('hidden');
        }
    } catch (error) {
        console.error('Error loading generated avatars:', error);
    }
}

async function loadPushedAvatars() {
    try {
        const response = await fetch(`${API_BASE}/pushed-avatars`);
        const result = await response.json();
        
        const container = document.getElementById('pushedAvatars');
        const noAvatarsMessage = document.getElementById('noPushedAvatars');
        
        if (result.success && result.avatars.length > 0) {
            container.innerHTML = result.avatars.map(avatar => createAvatarCard(avatar, 'pushed')).join('');
            container.classList.remove('hidden');
            noAvatarsMessage.classList.add('hidden');
        } else {
            container.classList.add('hidden');
            noAvatarsMessage.classList.remove('hidden');
        }
    } catch (error) {
        console.error('Error loading pushed avatars:', error);
    }
}

function createAvatarCard(avatar, type) {
    const createdDate = new Date(avatar.created_at).toLocaleDateString();
    const createdTime = new Date(avatar.created_at).toLocaleTimeString();
    
    return `
        <div class="avatar-card">
            <video controls>
                <source src="${avatar.url}" type="video/mp4">
                Your browser does not support the video tag.
            </video>
            <div class="avatar-info">
                <h4>Avatar ${avatar.id.slice(0, 8)}</h4>
                <p><strong>Audio:</strong> ${avatar.original_audio}</p>
                <p><strong>Media:</strong> ${avatar.original_media}</p>
                <p><strong>Created:</strong> ${createdDate} ${createdTime}</p>
                ${avatar.pushed_at ? `<p><strong>Pushed:</strong> ${new Date(avatar.pushed_at).toLocaleDateString()}</p>` : ''}
                <div class="avatar-actions">
                    ${type === 'generated' ? 
                        `<button class="btn btn-success btn-small" onclick="pushAvatar('${avatar.id}')">
                            📤 Push Avatar
                        </button>` 
                        : ''
                    }
                    <button class="btn btn-danger btn-small" onclick="deleteAvatar('${avatar.id}')">
                        🗑️ Delete
                    </button>
                </div>
            </div>
        </div>
    `;
}

async function pushAvatar(avatarId) {
    try {
        const response = await fetch(`${API_BASE}/push-avatar/${avatarId}`, {
            method: 'POST'
        });
        
        const result = await response.json();
        
        if (result.success) {
            alert('Avatar pushed successfully!');
            loadGeneratedAvatars();
            loadPushedAvatars();
        } else {
            throw new Error(result.message || 'Push failed');
        }
    } catch (error) {
        console.error('Error pushing avatar:', error);
        alert(`Error pushing avatar: ${error.message}`);
    }
}

async function deleteAvatar(avatarId) {
    if (!confirm('Are you sure you want to delete this avatar?')) {
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/avatar/${avatarId}`, {
            method: 'DELETE'
        });
        
        const result = await response.json();
        
        if (result.success) {
            alert('Avatar deleted successfully!');
            loadGeneratedAvatars();
            loadPushedAvatars();
        } else {
            throw new Error(result.message || 'Delete failed');
        }
    } catch (error) {
        console.error('Error deleting avatar:', error);
        alert(`Error deleting avatar: ${error.message}`);
    }
}