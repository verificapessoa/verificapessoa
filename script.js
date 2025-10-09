// Configuração da API Backend 
const BACKEND_URL = 'https://verificapessoa-api.onrender.com';

// Estado da aplicação
let currentUser = null;
let loading = false;

// Verificar se usuário está logado ao carregar a página
document.addEventListener('DOMContentLoaded', function() {
    console.log('✅ DOM carregado, iniciando aplicação...');
    const token = localStorage.getItem('verificapessoa_token');
    if (token) {
        console.log('🔑 Token encontrado, buscando perfil...');
        fetchUserProfile(token);
    }
    
    // Event listeners
    setupEventListeners();
});

function setupEventListeners() {
    console.log('⚙️ Configurando event listeners...');
    
    // Formulário de login
    const loginForm = document.getElementById('login-form');
    if (loginForm) {
        loginForm.addEventListener('submit', handleLogin);
        console.log('✅ Login form listener adicionado');
    } else {
        console.warn('❌ Login form não encontrado');
    }
    
    // Formulário de registro
    const registerForm = document.getElementById('register-form');
    if (registerForm) {
        registerForm.addEventListener('submit', handleRegister);
        console.log('✅ Register form listener adicionado');
    } else {
        console.warn('❌ Register form não encontrado');
    }
    
    // Enter no campo de busca
    const searchInput = document.getElementById('search-input');
    if (searchInput) {
        searchInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                handleSearch();
            }
        });
        console.log('✅ Search input listener adicionado');
    } else {
        console.warn('❌ Search input não encontrado');
    }
}

// Funções de autenticação
async function fetchUserProfile(token) {
    try {
        console.log(`🌐 Buscando perfil em: ${BACKEND_URL}/api/user/profile`);
        const response = await fetch(`${BACKEND_URL}/api/user/profile`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        if (response.ok) {
            const userData = await response.json();
            console.log('✅ Perfil carregado:', userData);
            setCurrentUser(userData);
        } else {
            console.log('❌ Erro ao buscar perfil, removendo token');
            localStorage.removeItem('verificapessoa_token');
        }
    } catch (error) {
        console.error('❌ Erro ao buscar perfil:', error);
        localStorage.removeItem('verificapessoa_token');
    }
}

async function handleLogin(e) {
    e.preventDefault();
    console.log('🔐 Tentando fazer login...');
    
    if (loading) return;
    loading = true;
    
    const email = document.getElementById('login-email').value;
    const password = document.getElementById('login-password').value;
    
    try {
        console.log(`🌐 POST ${BACKEND_URL}/api/auth/login`);
        const response = await fetch(`${BACKEND_URL}/api/auth/login`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ email, password })
        });

        const data = await response.json();

        if (response.ok) {
            console.log('✅ Login bem-sucedido!');
            localStorage.setItem('verificapessoa_token', data.token);
            setCurrentUser(data.user);
            closeModals();
            document.getElementById('login-form').reset();
        } else {
            console.log('❌ Erro no login:', data.detail);
            showError('login-error', data.detail || 'Erro no login');
        }
    } catch (error) {
        console.error('❌ Erro de conexão:', error);
        showError('login-error', 'Erro de conexão. Tente novamente.');
    } finally {
        loading = false;
    }
}

async function handleRegister(e) {
    e.preventDefault();
    console.log('📝 Tentando registrar...');
    
    if (loading) {
        console.log('⏳ Já está processando...');
        return;
    }
    loading = true;
    
    const emailInput = document.getElementById('register-email');
    const passwordInput = document.getElementById('register-password');
    const confirmPasswordInput = document.getElementById('register-confirm');
    const acceptTermsInput = document.getElementById('accept-terms');
    
    if (!emailInput || !passwordInput || !confirmPasswordInput || !acceptTermsInput) {
        console.error('❌ Campos do formulário não encontrados!');
        alert('Erro: Campos do formulário não encontrados. Recarregue a página.');
        loading = false;
        return;
    }
    
    const email = emailInput.value;
    const password = passwordInput.value;
    const confirmPassword = confirmPasswordInput.value;
    const acceptTerms = acceptTermsInput.checked;
    
    console.log('📧 Email:', email);
    console.log('🔒 Senha digitada:', password ? 'Sim' : 'Não');
    console.log('✅ Termos aceitos:', acceptTerms);
    
    // Validações
    if (password !== confirmPassword) {
        console.log('❌ Senhas não coincidem');
        showError('register-error', 'Senhas não coincidem');
        loading = false;
        return;
    }
    
    if (!acceptTerms) {
        console.log('❌ Termos não aceitos');
        showError('register-error', 'Aceite os termos de uso para continuar');
        loading = false;
        return;
    }

    try {
        console.log(`🌐 POST ${BACKEND_URL}/api/auth/register`);
        console.log('📤 Enviando dados:', { email, password: '***' });
        
        const response = await fetch(`${BACKEND_URL}/api/auth/register`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ email, password })
        });

        console.log('📥 Status da resposta:', response.status);
        const data = await response.json();
        console.log('📥 Dados recebidos:', data);

        if (response.ok) {
            console.log('✅ Registro bem-sucedido!');
            alert('Conta criada com sucesso! Faça login para continuar.');
            closeModals();
            showLoginModal();
            document.getElementById('register-form').reset();
        } else {
            console.log('❌ Erro no registro:', data.detail);
            showError('register-error', data.detail || 'Erro no cadastro');
        }
    } catch (error) {
        console.error('❌ Erro de conexão:', error);
        showError('register-error', 'Erro de conexão. Tente novamente.');
    } finally {
        loading = false;
        console.log('🔓 Loading liberado');
    }
}

// Função de busca
async function handleSearch() {
    const searchQuery = document.getElementById('search-input').value.trim();
    console.log('🔍 Iniciando busca:', searchQuery);
    
    if (!searchQuery) {
        alert('Digite o nome completo da pessoa para pesquisar');
        return;
    }

    if (!currentUser) {
        alert('Faça login para realizar pesquisas');
        showLoginModal();
        return;
    }

    if (currentUser.credits < 1) {
        alert('Você não tem créditos suficientes. Compre um pacote para continuar.');
        document.getElementById('pricing').scrollIntoView({ behavior: 'smooth' });
        return;
    }

    // Mostrar progresso de busca
    showSearchProgress();

    try {
        const token = localStorage.getItem('verificapessoa_token');
        console.log(`🌐 POST ${BACKEND_URL}/api/search`);
        
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
            console.log('✅ Busca realizada com sucesso');
            hideSearchProgress();
            displaySearchResults(results);
            // Atualizar créditos do usuário
            currentUser.credits -= 1;
            updateUserDisplay();
        } else {
            throw new Error(results.detail || 'Erro na pesquisa');
        }
    } catch (error) {
        console.error('❌ Erro na pesquisa:', error);
        hideSearchProgress();
        alert('Erro na pesquisa: ' + error.message);
    }
}

// Função de compra
async function handlePurchase(packageType, amount, credits) {
    console.log('💳 Iniciando compra:', packageType);
    
    if (!currentUser) {
        alert('Faça login para comprar créditos');
        showLoginModal();
        return;
    }

    try {
        const token = localStorage.getItem('verificapessoa_token');
        console.log(`🌐 POST ${BACKEND_URL}/api/purchase`);
        
        const response = await fetch(`${BACKEND_URL}/api/purchase`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
                package_type: packageType,
                amount: amount,
                credits: credits
            })
        });

        const data = await response.json();

        if (response.ok) {
            console.log('✅ Pedido criado com sucesso');
            showPaymentModal({
                transaction_id: data.transaction_id,
                package_name: getPackageName(packageType),
                amount: amount,
                credits: credits,
                pix_info: data.pix_info
            });
        } else {
            alert('Erro ao criar pedido: ' + data.detail);
        }
    } catch (error) {
        console.error('❌ Erro na compra:', error);
        alert('Erro de conexão: ' + error.message);
    }
}

// Funções utilitárias
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
    console.log('👋 Fazendo logout...');
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

// Funções de modal
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
        <div class="modal-content">
            <button class="close-btn" onclick="this.parentElement.parentElement.remove()">×</button>
            <h3>💳 Pagamento</h3>
            <p><strong>Produto:</strong> ${paymentData.package_name}</p>
            <p><strong>Valor:</strong> R$ ${paymentData.amount.toFixed(2).replace('.', ',')}</p>
            <p><strong>Créditos:</strong> ${paymentData.credits}</p>
            
            <div class="pix-container">
                <h4>🔑 Pagamento PIX</h4>
                <div class="pix-info">
                    ${paymentData.pix_info.key}
                </div>
                <button class="btn-secondary" onclick="copyToClipboard('${paymentData.pix_info.key}')">📋 Copiar Chave PIX</button>
                <p style="color: #999; font-size: 0.9rem; margin: 1rem 0;">
                    Favorecido: ${paymentData.pix_info.name}<br />
                    Valor: R$ ${paymentData.amount.toFixed(2).replace('.', ',')}
                </p>
            </div>
            
            <p style="color: #666; font-size: 0.8rem; margin: 1rem 0; text-align: center;">
                Após o pagamento, envie o comprovante para silas@contabsf.com.br para liberação dos créditos.
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
        <div class="modal-content" style="max-width: 500px;">
            <h3>🔍 Pesquisa em Andamento</h3>
            <div style="text-align: center; padding: 2rem;">
                <div class="loading-spinner"></div>
                <div id="search-progress-text" style="margin: 1rem 0; color: #fff;">Iniciando busca real...</div>
            </div>
            <p style="color: #666; font-size: 0.9rem; text-align: center;">
                Esta é uma busca real na internet com múltiplas fontes públicas.
            </p>
        </div>
    `;
    
    document.body.appendChild(modal);
    
    // Simular progresso
    const progressSteps = [
        '🔍 Consultando Jusbrasil (processos judiciais)...',
        '🏢 Verificando Receita Federal (dados empresariais)...',
        '🏛️ Buscando em portais de transparência...',
        '📱 Analisando redes sociais públicas...',
        '🎓 Consultando universidades públicas...',
        '📋 Verificando registros civis...',
        '✅ Finalizando relatório...'
    ];
    
    let step = 0;
    const progressInterval = setInterval(() => {
        if (step < progressSteps.length) {
            const progressText = document.getElementById('search-progress-text');
            if (progressText) {
                progressText.textContent = progressSteps[step];
            }
            step++;
        } else {
            clearInterval(progressInterval);
        }
    }, 2000);
}

function hideSearchProgress() {
    const modal = document.getElementById('search-progress-modal');
    if (modal) {
        modal.remove();
    }
}

function displaySearchResults(results) {
    const modal = document.createElement('div');
    modal.className = 'modal active';
    modal.innerHTML = `
        <div class="modal-content search-results-modal">
            <button class="close-btn" onclick="this.parentElement.parentElement.remove()">×</button>
            <h3>🔍 Relatório de Investigação - ${results.name}</h3>
            
            <div class="disclaimer-box">
                <strong style="color: #4ade80;">✅ INFORMAÇÕES 100% PÚBLICAS</strong><br>
                <span style="font-size: 0.9rem; color: #ccc;">
                    ${results.disclaimer || 'Dados coletados exclusivamente de fontes públicas disponíveis na internet.'}
                </span>
            </div>
            
            <div class="summary-box">
                <strong>📊 Resumo da Pesquisa:</strong><br>
                • ${results.profiles_found} perfis encontrados<br>
                • ${results.sources_searched} fontes consultadas<br>
                • Confiança: ${results.confidence_score}%<br>
                • Nível de risco: ${getRiskIcon(results.risk_assessment)} ${getRiskText(results.risk_assessment)}
            </div>
            
            ${generateResultsSections(results)}
            
            <div class="important-notice">
                <strong>⚠️ IMPORTANTE - VERIFICAÇÃO FINAL OBRIGATÓRIA</strong><br>
                Este relatório apresenta informações coletadas de fontes públicas e deve ser usado apenas como ponto de partida. 
                <strong>É OBRIGATÓRIO realizar verificação cruzada independente</strong> antes de tomar qualquer decisão. 
                Podem existir homônimos ou dados desatualizados. 
                <a href="termos.html" target="_blank" style="color: #4ade80;">Leia nossos termos completos</a>.
            </div>
            
            <div style="text-align: center; margin-top: 2rem;">
                <button class="btn" onclick="window.print()">🖨️ Imprimir Relatório</button>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
}

function generateResultsSections(results) {
    let sectionsHtml = '';
    
    // Redes Sociais
    if (results.social_media && results.social_media.length > 0) {
        sectionsHtml += `
            <div class="results-section">
                <h4>📱 Redes Sociais (${results.social_media.length})</h4>
                ${results.social_media.map(profile => `
                    <div class="result-item">
                        <strong>${profile.platform}</strong><br>
                        ${profile.status}<br>
                        <span class="confidence">Confiança: ${profile.confidence}</span><br>
                        <span class="note">${profile.note}</span>
                    </div>
                `).join('')}
            </div>
        `;
    }
    
    // Informações Profissionais
    if (results.professional && results.professional.length > 0) {
        sectionsHtml += `
            <div class="results-section">
                <h4>💼 Informações Profissionais (${results.professional.length})</h4>
                ${results.professional.map(info => `
                    <div class="result-item">
                        <strong>${info.type}</strong><br>
                        Fonte: ${info.source}<br>
                        <span class="confidence">Confiança: ${info.confidence}</span><br>
                        <span class="note">${info.note}</span>
                    </div>
                `).join('')}
            </div>
        `;
    }
    
    // Registros Públicos
    if (results.public_records && results.public_records.length > 0) {
        sectionsHtml += `
            <div class="results-section">
                <h4>🏛️ Registros Públicos (${results.public_records.length})</h4>
                ${results.public_records.map(record => `
                    <div class="result-item">
                        <strong>${record.type}</strong><br>
                        Fonte: ${record.source}<br>
                        <span class="confidence">Confiança: ${record.confidence}</span><br>
                        <span class="note">${record.note}</span>
                    </div>
                `).join('')}
            </div>
        `;
    }
    
    return sectionsHtml;
}

function getRiskIcon(risk) {
    switch (risk) {
        case 'high': return '🔴';
        case 'medium': return '🟡';
        default: return '🟢';
    }
}

function getRiskText(risk) {
    switch (risk) {
        case 'high': return 'Alto';
        case 'medium': return 'Médio';
        default: return 'Baixo';
    }
}

function closeModals() {
    const modals = document.querySelectorAll('.modal');
    modals.forEach(modal => {
        modal.classList.remove('active');
    });
    
    // Limpar erros
    const errors = document.querySelectorAll('.error');
    errors.forEach(error => {
        error.style.display = 'none';
    });
}

function showError(elementId, message) {
    const errorElement = document.getElementById(elementId);
    if (errorElement) {
        errorElement.textContent = message;
        errorElement.style.display = 'block';
        
        setTimeout(() => {
            errorElement.style.display = 'none';
        }, 5000);
    }
}

function copyToClipboard(text) {
    if (navigator.clipboard) {
        navigator.clipboard.writeText(text)
            .then(() => alert('Chave PIX copiada!'))
            .catch(() => alert('Não foi possível copiar. Copie manualmente.'));
    } else {
        // Fallback para browsers mais antigos
        const textArea = document.createElement('textarea');
        textArea.value = text;
        document.body.appendChild(textArea);
        textArea.select();
        document.execCommand('copy');
        document.body.removeChild(textArea);
        alert('Chave PIX copiada!');
    }
}

// Fechar modais ao clicar fora
document.addEventListener('click', function(e) {
    if (e.target.classList.contains('modal')) {
        closeModals();
    }
});

console.log('✅ Script.js carregado completamente!');
