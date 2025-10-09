// Configuração da API Backend
const BACKEND_URL = 'https://verificapessoa-api.onrender.com';

// Estado da aplicação
let currentUser = null;
let loading = false;

// AGUARDAR O DOM ESTAR COMPLETAMENTE PRONTO
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', inicializar);
} else {
    inicializar();
}

function inicializar() {
    console.log('✅ DOM pronto, iniciando aplicação...');
    
    const token = localStorage.getItem('verificapessoa_token');
    if (token) {
        console.log('🔑 Token encontrado');
        fetchUserProfile(token);
    }
    
    configurarEventos();
}

function configurarEventos() {
    console.log('⚙️ Configurando eventos...');
    
    // Login
    const loginForm = document.getElementById('login-form');
    if (loginForm) {
        loginForm.onsubmit = handleLogin;
        console.log('✅ Login configurado');
    }
    
    // Registro
    const registerForm = document.getElementById('register-form');
    if (registerForm) {
        registerForm.onsubmit = handleRegister;
        console.log('✅ Registro configurado');
    }
    
    // Busca
    const searchInput = document.getElementById('search-input');
    if (searchInput) {
        searchInput.onkeypress = function(e) {
            if (e.key === 'Enter') handleSearch();
        };
        console.log('✅ Busca configurada');
    }
}

async function fetchUserProfile(token) {
    try {
        const response = await fetch(`${BACKEND_URL}/api/user/profile`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        
        if (response.ok) {
            const userData = await response.json();
            setCurrentUser(userData);
        } else {
            localStorage.removeItem('verificapessoa_token');
        }
    } catch (error) {
        console.error('Erro ao buscar perfil:', error);
        localStorage.removeItem('verificapessoa_token');
    }
}

async function handleLogin(e) {
    e.preventDefault();
    console.log('🔐 Login...');
    
    if (loading) return;
    loading = true;
    
    const email = document.getElementById('login-email').value;
    const password = document.getElementById('login-password').value;
    
    try {
        const response = await fetch(`${BACKEND_URL}/api/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password })
        });

        const data = await response.json();

        if (response.ok) {
            localStorage.setItem('verificapessoa_token', data.token);
            setCurrentUser(data.user);
            closeModals();
            document.getElementById('login-form').reset();
        } else {
            showError('login-error', data.detail || 'Erro no login');
        }
    } catch (error) {
        showError('login-error', 'Erro de conexão');
    } finally {
        loading = false;
    }
}

async function handleRegister(e) {
    e.preventDefault();
    console.log('📝 Registro iniciado!');
    
    if (loading) {
        alert('Aguarde...');
        return;
    }
    
    loading = true;
    
    const email = document.getElementById('register-email').value;
    const password = document.getElementById('register-password').value;
    const confirmPassword = document.getElementById('register-confirm').value;
    const acceptTerms = document.getElementById('accept-terms').checked;
    
    console.log('Email:', email);
    console.log('Termos:', acceptTerms);
    
    if (password !== confirmPassword) {
        showError('register-error', 'Senhas não coincidem');
        loading = false;
        return;
    }
    
    if (!acceptTerms) {
        showError('register-error', 'Aceite os termos para continuar');
        loading = false;
        return;
    }

    try {
        console.log('Enviando requisição...');
        
        const response = await fetch(`${BACKEND_URL}/api/auth/register`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password })
        });

        console.log('Status:', response.status);
        const data = await response.json();

        if (response.ok) {
            console.log('✅ Sucesso!');
            alert('Conta criada com sucesso! Faça login.');
            closeModals();
            showLoginModal();
            document.getElementById('register-form').reset();
        } else {
            showError('register-error', data.detail || 'Erro no cadastro');
        }
    } catch (error) {
        console.error('Erro:', error);
        showError('register-error', 'Erro de conexão');
    } finally {
        loading = false;
    }
}

async function handleSearch() {
    const searchQuery = document.getElementById('search-input').value.trim();
    
    if (!searchQuery) {
        alert('Digite o nome da pessoa');
        return;
    }

    if (!currentUser) {
        alert('Faça login primeiro');
        showLoginModal();
        return;
    }

    if (currentUser.credits < 1) {
        alert('Créditos insuficientes');
        document.getElementById('pricing').scrollIntoView({ behavior: 'smooth' });
        return;
    }

    showSearchProgress();

    try {
        const token = localStorage.getItem('verificapessoa_token');
        const response = await fetch(`${BACKEND_URL}/api/search`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({ name: searchQuery })
        });

        const results = await response.json();

        if (response.ok) {
            hideSearchProgress();
            displaySearchResults(results);
            currentUser.credits -= 1;
            updateUserDisplay();
        } else {
            throw new Error(results.detail);
        }
    } catch (error) {
        hideSearchProgress();
        alert('Erro: ' + error.message);
    }
}

async function handlePurchase(packageType, amount, credits) {
    if (!currentUser) {
        alert('Faça login primeiro');
        showLoginModal();
        return;
    }

    try {
        const token = localStorage.getItem('verificapessoa_token');
        const response = await fetch(`${BACKEND_URL}/api/purchase`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({ package_type: packageType, amount, credits })
        });

        const data = await response.json();

        if (response.ok) {
            showPaymentModal({
                transaction_id: data.transaction_id,
                package_name: getPackageName(packageType),
                amount, credits,
                pix_info: data.pix_info
            });
        } else {
            alert('Erro: ' + data.detail);
        }
    } catch (error) {
        alert('Erro: ' + error.message);
    }
}

function setCurrentUser(user) {
    currentUser = user;
    updateUserDisplay();
}

function updateUserDisplay() {
    const userInfo = document.getElementById('user-info');
    const loginBtn = document.getElementById('login-btn');
    const userEmail = document.getElementById('user-email');
    const userCredits = document.getElementById('user-credits');
    
    if (currentUser) {
        userEmail.textContent = currentUser.email;
        userCredits.textContent = `${currentUser.credits} créditos`;
        userInfo.style.display = 'flex';
        loginBtn.style.display = 'none';
    } else {
        userInfo.style.display = 'none';
        loginBtn.style.display = 'block';
    }
}

function logout() {
    localStorage.removeItem('verificapessoa_token');
    currentUser = null;
    updateUserDisplay();
}

function getPackageName(packageType) {
    const packages = {
        'individual': 'Pesquisa Única',
        'pack10': 'Pacote 10 Créditos',
        'pack20': 'Pacote 20 Créditos',
        'pack50': 'Pacote 50 Créditos'
    };
    return packages[packageType] || packageType;
}

function showLoginModal() {
    closeModals();
    document.getElementById('login-modal').classList.add('active');
}

function showRegisterModal() {
    closeModals();
    document.getElementById('register-modal').classList.add('active');
}

function showPaymentModal(paymentData) {
    const modal = document.createElement('div');
    modal.className = 'modal active';
    modal.innerHTML = `
        <div class=\"modal-content\">
            <button class=\"close-btn\" onclick=\"this.parentElement.parentElement.remove()\">×</button>
            <h3>💳 Pagamento</h3>
            <p><strong>Produto:</strong> ${paymentData.package_name}</p>
            <p><strong>Valor:</strong> R$ ${paymentData.amount.toFixed(2).replace('.', ',')}</p>
            <p><strong>Créditos:</strong> ${paymentData.credits}</p>
            <div class=\"pix-container\">
                <h4>🔑 Pagamento PIX</h4>
                <div class=\"pix-info\">${paymentData.pix_info.key}</div>
                <button class=\"btn-secondary\" onclick=\"copyToClipboard('${paymentData.pix_info.key}')\">📋 Copiar Chave PIX</button>
                <p style=\"color: #999; font-size: 0.9rem; margin: 1rem 0;\">
                    Favorecido: ${paymentData.pix_info.name}<br />
                    Valor: R$ ${paymentData.amount.toFixed(2).replace('.', ',')}
                </p>
            </div>
            <p style=\"color: #666; font-size: 0.8rem; margin: 1rem 0; text-align: center;\">
                Após o pagamento, envie o comprovante para silas@contabsf.com.br
            </p>
        </div>
    `;
    document.body.appendChild(modal);
}

function showSearchProgress() {
    const modal = document.createElement('div');
    modal.id = 'search-progress-modal';
    modal.className = 'modal active';
    modal.innerHTML = `
        <div class=\"modal-content\" style=\"max-width: 500px;\">
            <h3>🔍 Pesquisa em Andamento</h3>
            <div style=\"text-align: center; padding: 2rem;\">
                <div class=\"loading-spinner\"></div>
                <div id=\"search-progress-text\" style=\"margin: 1rem 0; color: #fff;\">Iniciando busca...</div>
            </div>
        </div>
    `;
    document.body.appendChild(modal);
    
    const steps = [
        '🔍 Consultando Jusbrasil...',
        '🏢 Verificando Receita Federal...',
        '🏛️ Buscando portais públicos...',
        '📱 Analisando redes sociais...',
        '✅ Finalizando relatório...'
    ];
    
    let step = 0;
    const interval = setInterval(() => {
        const text = document.getElementById('search-progress-text');
        if (text && step < steps.length) {
            text.textContent = steps[step++];
        } else {
            clearInterval(interval);
        }
    }, 2000);
}

function hideSearchProgress() {
    const modal = document.getElementById('search-progress-modal');
    if (modal) modal.remove();
}

function displaySearchResults(results) {
    const modal = document.createElement('div');
    modal.className = 'modal active';
    modal.innerHTML = `
        <div class=\"modal-content search-results-modal\">
            <button class=\"close-btn\" onclick=\"this.parentElement.parentElement.remove()\">×</button>
            <h3>🔍 Relatório - ${results.name}</h3>
            <div class=\"disclaimer-box\">
                <strong style=\"color: #4ade80;\">✅ INFORMAÇÕES 100% PÚBLICAS</strong><br>
                <span style=\"font-size: 0.9rem; color: #ccc;\">${results.disclaimer}</span>
            </div>
            <div class=\"summary-box\">
                <strong>📊 Resumo:</strong><br>
                • ${results.profiles_found} perfis encontrados<br>
                • ${results.sources_searched} fontes consultadas<br>
                • Confiança: ${results.confidence_score}%
            </div>
            ${generateResultsSections(results)}
            <div class=\"important-notice\">
                <strong>⚠️ IMPORTANTE</strong><br>
                Verificação cruzada obrigatória. <a href=\"termos.html\" target=\"_blank\" style=\"color: #4ade80;\">Termos</a>
            </div>
        </div>
    `;
    document.body.appendChild(modal);
}

function generateResultsSections(results) {
    let html = '';
    
    if (results.social_media?.length) {
        html += `<div class=\"results-section\"><h4>📱 Redes Sociais</h4>`;
        results.social_media.forEach(p => {
            html += `<div class=\"result-item\"><strong>${p.platform}</strong><br>${p.status}</div>`;
        });
        html += `</div>`;
    }
    
    if (results.professional?.length) {
        html += `<div class=\"results-section\"><h4>💼 Profissional</h4>`;
        results.professional.forEach(i => {
            html += `<div class=\"result-item\"><strong>${i.type}</strong><br>Fonte: ${i.source}</div>`;
        });
        html += `</div>`;
    }
    
    if (results.public_records?.length) {
        html += `<div class=\"results-section\"><h4>🏛️ Registros Públicos</h4>`;
        results.public_records.forEach(r => {
            html += `<div class=\"result-item\"><strong>${r.type}</strong><br>Fonte: ${r.source}</div>`;
        });
        html += `</div>`;
    }
    
    return html;
}

function closeModals() {
    document.querySelectorAll('.modal').forEach(m => m.classList.remove('active'));
    document.querySelectorAll('.error').forEach(e => e.style.display = 'none');
}

function showError(id, msg) {
    const el = document.getElementById(id);
    if (el) {
        el.textContent = msg;
        el.style.display = 'block';
        setTimeout(() => el.style.display = 'none', 5000);
    }
}

function copyToClipboard(text) {
    if (navigator.clipboard) {
        navigator.clipboard.writeText(text).then(() => alert('Chave PIX copiada!'));
    } else {
        const ta = document.createElement('textarea');
        ta.value = text;
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        document.body.removeChild(ta);
        alert('Chave PIX copiada!');
    }
}

document.addEventListener('click', function(e) {
    if (e.target.classList.contains('modal')) closeModals();
});

console.log('✅ Script carregado!');
