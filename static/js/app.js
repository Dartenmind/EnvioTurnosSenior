/**
 * Sistema de Envio de Escalas - Frontend Application
 * Gerencia upload, processamento e feedback em tempo real via WebSocket
 */

// Estado da aplicação
const appState = {
    socket: null,
    fileUploaded: false,
    authenticated: false,
    processing: false,
    currentFile: null,
    resultsFile: null,
    hasErrors: false
};

// Elementos DOM
const elements = {
    // Upload
    uploadArea: document.getElementById('uploadArea'),
    fileInput: document.getElementById('fileInput'),
    selectFileBtn: document.getElementById('selectFileBtn'),
    fileInfo: document.getElementById('fileInfo'),
    fileName: document.getElementById('fileName'),
    fileRecords: document.getElementById('fileRecords'),
    uploadSection: document.getElementById('uploadSection'),

    // Settings
    settingsSection: document.getElementById('settingsSection'),
    concurrencyInput: document.getElementById('concurrencyInput'),
    startProcessBtn: document.getElementById('startProcessBtn'),
    cancelBtn: document.getElementById('cancelBtn'),

    // Terminal
    terminal: document.getElementById('terminal'),

    // Progress
    progressSection: document.getElementById('progressSection'),
    progressBar: document.getElementById('progressBar'),
    progressText: document.getElementById('progressText'),
    statProcessed: document.getElementById('statProcessed'),
    statSuccess: document.getElementById('statSuccess'),
    statErrors: document.getElementById('statErrors'),
    statTotal: document.getElementById('statTotal'),

    // Results
    resultsSection: document.getElementById('resultsSection'),
    resultsSummary: document.getElementById('resultsSummary'),
    downloadBtn: document.getElementById('downloadBtn'),
    retryBtn: document.getElementById('retryBtn'),
    newProcessBtn: document.getElementById('newProcessBtn'),

    // Errors
    errorsSection: document.getElementById('errorsSection'),
    errorsTableBody: document.getElementById('errorsTableBody'),

    // Status
    statusBadge: document.getElementById('statusBadge'),
    statusText: document.getElementById('statusText')
};

/**
 * Inicializa a aplicação
 */
function init() {
    setupWebSocket();
    setupEventListeners();
    addTerminalLine('Sistema inicializado. Conectando ao servidor...', 'info');

    // Validar configuração após conexão
    setTimeout(() => {
        validateConfiguration();
    }, 1000);
}

/**
 * Configura conexão WebSocket
 */
function setupWebSocket() {
    appState.socket = io();

    appState.socket.on('connect', () => {
        addTerminalLine('✓ Conectado ao servidor com sucesso', 'success');
        updateStatus(true);
    });

    appState.socket.on('disconnect', () => {
        addTerminalLine('✗ Desconectado do servidor', 'error');
        updateStatus(false);
    });

    appState.socket.on('log', (data) => {
        addTerminalLine(data.message, data.type);
    });

    appState.socket.on('progress', (data) => {
        updateProgress(data);
    });

    appState.socket.on('processing_complete', (data) => {
        handleProcessingComplete(data);
    });
}

/**
 * Configura event listeners
 */
function setupEventListeners() {
    // Upload events
    elements.selectFileBtn.addEventListener('click', () => {
        elements.fileInput.click();
    });

    elements.fileInput.addEventListener('change', handleFileSelect);

    elements.uploadArea.addEventListener('click', () => {
        if (!appState.processing) {
            elements.fileInput.click();
        }
    });

    // Drag and drop
    elements.uploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        if (!appState.processing) {
            elements.uploadArea.classList.add('drag-over');
        }
    });

    elements.uploadArea.addEventListener('dragleave', () => {
        elements.uploadArea.classList.remove('drag-over');
    });

    elements.uploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        elements.uploadArea.classList.remove('drag-over');

        if (!appState.processing && e.dataTransfer.files.length > 0) {
            const file = e.dataTransfer.files[0];
            if (file.name.endsWith('.csv')) {
                elements.fileInput.files = e.dataTransfer.files;
                handleFileSelect();
            } else {
                addTerminalLine('✗ Apenas arquivos CSV são permitidos', 'error');
            }
        }
    });

    // Process buttons
    elements.startProcessBtn.addEventListener('click', startProcessing);
    elements.cancelBtn.addEventListener('click', cancelUpload);
    elements.retryBtn.addEventListener('click', retryErrors);
    elements.downloadBtn.addEventListener('click', downloadResults);
    elements.newProcessBtn.addEventListener('click', resetApp);
}

/**
 * Valida configuração do sistema
 */
async function validateConfiguration() {
    try {
        const response = await fetch('/api/validate-config');
        const data = await response.json();

        if (!data.valid) {
            // Erros críticos
            data.errors.forEach(error => {
                addTerminalLine(`✗ ERRO: ${error.message}`, 'error');
                if (error.details) {
                    addTerminalLine(`  ${error.details}`, 'error');
                }
            });
        }

        // Avisos (não impedem uso)
        data.warnings.forEach(warning => {
            if (warning.type === 'missing_horarios') {
                addTerminalLine(`⚠ AVISO: ${warning.message}`, 'warning');
                addTerminalLine(`  ${warning.details}`, 'warning');
            } else {
                addTerminalLine(`ℹ ${warning.message}`, 'info');
            }
        });

        // Se tudo OK
        if (data.valid && data.warnings.length === 0 && data.errors.length === 0) {
            addTerminalLine('✓ Configuração validada com sucesso', 'success');
        }

    } catch (error) {
        addTerminalLine(`⚠ Não foi possível validar configuração: ${error.message}`, 'warning');
    }
}

/**
 * Manipula seleção de arquivo
 */
async function handleFileSelect() {
    const file = elements.fileInput.files[0];

    if (!file) return;

    if (!file.name.endsWith('.csv')) {
        addTerminalLine('✗ Apenas arquivos CSV são permitidos', 'error');
        return;
    }

    addTerminalLine(`Enviando arquivo: ${file.name}...`, 'info');

    const formData = new FormData();
    formData.append('file', file);

    try {
        const response = await fetch('/api/upload', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (response.ok) {
            appState.fileUploaded = true;
            appState.currentFile = data.filename;

            // Mostrar nome do arquivo (original ou convertido)
            const displayName = data.original_filename || data.filename;
            elements.fileName.textContent = displayName;
            elements.fileRecords.textContent = data.total_records;
            elements.fileInfo.style.display = 'block';
            elements.settingsSection.style.display = 'block';

            elements.statTotal.textContent = data.total_records;

            // Informar sobre formato e conversão
            if (data.converted) {
                addTerminalLine(`✓ Formato GRID detectado e convertido automaticamente`, 'success');
            }

            addTerminalLine(`✓ Arquivo carregado: ${data.total_records} registros`, 'success');

            // Autenticar automaticamente
            await authenticate();
        } else {
            addTerminalLine(`✗ Erro ao carregar arquivo: ${data.error}`, 'error');
            if (data.details) {
                addTerminalLine(`  ${data.details}`, 'error');
            }
        }
    } catch (error) {
        addTerminalLine(`✗ Erro ao enviar arquivo: ${error.message}`, 'error');
    }
}

/**
 * Autentica na API usando credenciais do .env
 */
async function authenticate() {
    addTerminalLine('Autenticando na plataforma Senior...', 'info');

    try {
        const response = await fetch('/api/authenticate', {
            method: 'POST'
        });

        const data = await response.json();

        if (response.ok) {
            appState.authenticated = true;
            addTerminalLine('✓ Autenticação realizada com sucesso!', 'success');
        } else {
            addTerminalLine(`✗ Erro na autenticação: ${data.error}`, 'error');
            appState.authenticated = false;
        }
    } catch (error) {
        addTerminalLine(`✗ Erro na autenticação: ${error.message}`, 'error');
        appState.authenticated = false;
    }
}

/**
 * Inicia processamento
 */
async function startProcessing() {
    if (!appState.fileUploaded) {
        addTerminalLine('✗ Nenhum arquivo carregado', 'error');
        return;
    }

    if (!appState.authenticated) {
        addTerminalLine('✗ Não autenticado. Tentando autenticar...', 'error');
        await authenticate();
        if (!appState.authenticated) return;
    }

    const maxConcurrent = parseInt(elements.concurrencyInput.value);

    if (maxConcurrent < 1 || maxConcurrent > 50) {
        addTerminalLine('✗ Concorrência deve estar entre 1 e 50', 'error');
        return;
    }

    addTerminalLine('═══════════════════════════════════════════════════════', 'info');
    addTerminalLine('INICIANDO PROCESSAMENTO', 'info');
    addTerminalLine('═══════════════════════════════════════════════════════', 'info');

    appState.processing = true;
    elements.startProcessBtn.disabled = true;
    elements.uploadSection.style.display = 'none';
    elements.settingsSection.style.display = 'none';
    elements.progressSection.style.display = 'block';
    elements.resultsSection.style.display = 'none';
    elements.errorsSection.style.display = 'none';

    // Reset progress
    resetProgress();

    try {
        const response = await fetch('/api/process', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                max_concurrent: maxConcurrent
            })
        });

        const data = await response.json();

        if (!response.ok) {
            addTerminalLine(`✗ Erro ao iniciar processamento: ${data.error}`, 'error');
            appState.processing = false;
            elements.startProcessBtn.disabled = false;
        }
    } catch (error) {
        addTerminalLine(`✗ Erro ao iniciar processamento: ${error.message}`, 'error');
        appState.processing = false;
        elements.startProcessBtn.disabled = false;
    }
}

/**
 * Cancela upload e reseta formulário
 */
function cancelUpload() {
    elements.fileInput.value = '';
    elements.fileInfo.style.display = 'none';
    elements.settingsSection.style.display = 'none';
    appState.fileUploaded = false;
    appState.currentFile = null;
    addTerminalLine('Upload cancelado', 'warning');
}

/**
 * Reseta progresso
 */
function resetProgress() {
    elements.progressBar.style.width = '0%';
    elements.progressText.textContent = '0%';
    elements.statProcessed.textContent = '0';
    elements.statSuccess.textContent = '0';
    elements.statErrors.textContent = '0';
}

/**
 * Atualiza barra de progresso
 */
function updateProgress(data) {
    elements.progressBar.style.width = data.percentage + '%';
    elements.progressText.textContent = data.percentage + '%';
    elements.statProcessed.textContent = data.current;
    elements.statSuccess.textContent = data.successes;
    elements.statErrors.textContent = data.errors;
}

/**
 * Manipula conclusão do processamento
 */
function handleProcessingComplete(data) {
    appState.processing = false;
    elements.startProcessBtn.disabled = false;

    if (data.success) {
        addTerminalLine('═══════════════════════════════════════════════════════', 'info');
        addTerminalLine('✓ PROCESSAMENTO CONCLUÍDO COM SUCESSO', 'success');
        addTerminalLine('═══════════════════════════════════════════════════════', 'info');

        // Exibir resumo
        elements.resultsSection.style.display = 'block';

        const summaryHTML = `
            <p>
                <span class="label">Total de Registros:</span>
                <span class="value">${data.total}</span>
            </p>
            <p>
                <span class="label">Sucessos:</span>
                <span class="value success">${data.successes}</span>
            </p>
            <p>
                <span class="label">Erros:</span>
                <span class="value error">${data.errors}</span>
            </p>
            <p>
                <span class="label">Tempo Total:</span>
                <span class="value">${data.tempo_total.toFixed(2)}s</span>
            </p>
            <p>
                <span class="label">Velocidade Média:</span>
                <span class="value">${(data.total / data.tempo_total).toFixed(2)} req/seg</span>
            </p>
        `;

        elements.resultsSummary.innerHTML = summaryHTML;

        // Botões de ação
        if (data.results_file) {
            appState.resultsFile = data.results_file;
            elements.downloadBtn.style.display = 'inline-flex';
        }

        if (data.errors > 0) {
            appState.hasErrors = true;
            elements.retryBtn.style.display = 'inline-flex';

            // Exibir tabela de erros
            displayErrors(data.error_details);
        } else {
            appState.hasErrors = false;
        }

        elements.newProcessBtn.style.display = 'inline-flex';

    } else {
        addTerminalLine(`✗ Erro no processamento: ${data.error}`, 'error');
    }
}

/**
 * Exibe tabela de erros
 */
function displayErrors(errors) {
    if (!errors || errors.length === 0) return;

    elements.errorsSection.style.display = 'block';
    elements.errorsTableBody.innerHTML = '';

    errors.forEach((error, index) => {
        const row = document.createElement('tr');

        const errorMsg = error.response_text || error.erro || 'Erro desconhecido';
        const truncatedError = errorMsg.length > 100
            ? errorMsg.substring(0, 100) + '...'
            : errorMsg;

        row.innerHTML = `
            <td>${index + 1}</td>
            <td>${error.id_colaborador}</td>
            <td>${error.nome}</td>
            <td>${error.data}</td>
            <td>${error.codigo_horario}</td>
            <td style="color: var(--accent-red);">${truncatedError}</td>
        `;

        elements.errorsTableBody.appendChild(row);
    });
}

/**
 * Reprocessa erros
 */
async function retryErrors() {
    if (!appState.hasErrors) return;

    addTerminalLine('═══════════════════════════════════════════════════════', 'info');
    addTerminalLine('REENVIANDO REGISTROS COM ERRO', 'warning');
    addTerminalLine('═══════════════════════════════════════════════════════', 'info');

    appState.processing = true;
    elements.retryBtn.disabled = true;
    elements.resultsSection.style.display = 'none';
    elements.errorsSection.style.display = 'none';
    elements.progressSection.style.display = 'block';

    resetProgress();

    const maxConcurrent = parseInt(elements.concurrencyInput.value);

    try {
        const response = await fetch('/api/retry', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                max_concurrent: maxConcurrent
            })
        });

        const data = await response.json();

        if (!response.ok) {
            addTerminalLine(`✗ Erro ao iniciar retry: ${data.error}`, 'error');
            appState.processing = false;
            elements.retryBtn.disabled = false;
        }
    } catch (error) {
        addTerminalLine(`✗ Erro ao iniciar retry: ${error.message}`, 'error');
        appState.processing = false;
        elements.retryBtn.disabled = false;
    }
}

/**
 * Download de resultados
 */
function downloadResults() {
    if (!appState.resultsFile) return;

    window.location.href = `/api/download/${appState.resultsFile}`;
    addTerminalLine(`Baixando arquivo de resultados: ${appState.resultsFile}`, 'success');
}

/**
 * Reseta aplicação para novo processamento
 */
function resetApp() {
    // Reset state
    appState.fileUploaded = false;
    appState.processing = false;
    appState.currentFile = null;
    appState.resultsFile = null;
    appState.hasErrors = false;

    // Reset UI
    elements.fileInput.value = '';
    elements.fileInfo.style.display = 'none';
    elements.settingsSection.style.display = 'none';
    elements.progressSection.style.display = 'none';
    elements.resultsSection.style.display = 'none';
    elements.errorsSection.style.display = 'none';
    elements.uploadSection.style.display = 'block';

    elements.downloadBtn.style.display = 'none';
    elements.retryBtn.style.display = 'none';
    elements.newProcessBtn.style.display = 'none';

    elements.startProcessBtn.disabled = false;
    elements.retryBtn.disabled = false;

    resetProgress();

    addTerminalLine('═══════════════════════════════════════════════════════', 'info');
    addTerminalLine('Sistema pronto para novo processamento', 'info');
    addTerminalLine('═══════════════════════════════════════════════════════', 'info');
}

/**
 * Adiciona linha ao terminal
 */
function addTerminalLine(message, type = 'info') {
    const line = document.createElement('div');
    line.className = `terminal-line ${type}`;

    const timestamp = new Date().toLocaleTimeString('pt-BR');

    line.innerHTML = `
        <span class="terminal-prompt">[${timestamp}]</span>
        <span class="terminal-text">${escapeHtml(message)}</span>
    `;

    elements.terminal.appendChild(line);
    elements.terminal.scrollTop = elements.terminal.scrollHeight;
}

/**
 * Atualiza status da conexão
 */
function updateStatus(connected) {
    if (connected) {
        elements.statusBadge.classList.add('connected');
        elements.statusText.textContent = 'Conectado';
    } else {
        elements.statusBadge.classList.remove('connected');
        elements.statusText.textContent = 'Desconectado';
    }
}

/**
 * Escapa HTML para prevenir XSS
 */
function escapeHtml(text) {
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, m => map[m]);
}

// Inicializar aplicação quando DOM estiver pronto
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}
