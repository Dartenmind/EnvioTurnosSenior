# Interface Web - Sistema de Envio de Escalas Senior

## Visão Geral

Este sistema agora possui uma interface web moderna com tema terminal para facilitar o envio de escalas para a API Senior. A interface oferece feedback em tempo real via WebSocket, mantendo toda a lógica robusta do sistema CLI original.

## Características

✅ **Interface Terminal-like** - Design escuro e moderno inspirado em terminais
✅ **Upload via Drag & Drop** - Arraste e solte arquivos CSV facilmente
✅ **Feedback em Tempo Real** - Acompanhe cada requisição via WebSocket
✅ **Barra de Progresso** - Visualização clara do andamento
✅ **Sistema de Retry** - Reenvie erros com um clique
✅ **Download de Resultados** - Baixe o CSV de resultados diretamente
✅ **Autenticação Automática** - Usa credenciais do arquivo .env
✅ **Código Original Preservado** - CLI continua funcionando normalmente

## Estrutura de Arquivos

```
ENVIO_AUTOMATICO_ESCALA_SENIOR_V7/
├── app.py                          # Servidor Flask com WebSocket
├── templates/
│   └── index.html                  # Interface web principal
├── static/
│   ├── css/
│   │   └── style.css              # Estilos terminal-like
│   └── js/
│       └── app.js                 # Lógica frontend + WebSocket
├── envio_escala_api_corrigido.py  # Sistema CLI original (mantido)
├── src/                            # Módulos reutilizados
│   ├── auth.py
│   └── ...
└── requirements.txt                # Dependências (atualizadas)
```

## Instalação

### 1. Instalar Dependências

```bash
pip install -r requirements.txt
```

As novas dependências adicionadas são:
- Flask>=2.3.0
- Flask-SocketIO>=5.3.0
- flask-cors>=4.0.0
- python-socketio>=5.9.0

### 2. Configurar Credenciais

Certifique-se de que o arquivo `.env` está configurado:

```env
SENIOR_USERNAME=seu_usuario@empresa.com.br
SENIOR_PASSWORD=sua_senha_aqui
```

### 3. Iniciar Servidor

```bash
python app.py
```

O servidor será iniciado em: **http://localhost:5000**

## Como Usar

### 1. Acessar Interface

Abra seu navegador e acesse: `http://localhost:5000`

### 2. Upload de Arquivo

**Opção 1 - Drag & Drop:**
- Arraste o arquivo CSV para a área de upload

**Opção 2 - Seleção Manual:**
- Clique em "Selecionar Arquivo"
- Escolha o arquivo CSV desejado

### 3. Aguardar Autenticação

O sistema autentica automaticamente usando as credenciais do `.env`

### 4. Configurar e Processar

- Defina o número de requisições simultâneas (1-50)
- Clique em "Iniciar Processamento"
- Acompanhe o progresso em tempo real no console

### 5. Visualizar Resultados

Após o processamento:
- **Resumo**: Total, sucessos, erros, tempo
- **Download**: Baixe o CSV de resultados
- **Retry**: Reenvie apenas os registros com erro
- **Novo Processamento**: Inicie um novo ciclo

## Formato do Arquivo CSV

O arquivo CSV deve seguir o formato API:

```csv
id_colaborador;nome;data;codigo_horario;numero_cadastro;numero_empresa;tipo_colaborador
303-1-29486;ADRIANA FERREIRA ALVES;2025-11-27;1;29486;303;1
303-1-29487;JOAO SILVA SANTOS;2025-11-28;151;29487;303;1
```

### Campos Obrigatórios
- `id_colaborador`: ID único do colaborador
- `nome`: Nome completo
- `data`: Data da programação (YYYY-MM-DD)
- `codigo_horario`: Código do horário

### Campos Opcionais
- `numero_cadastro`: Extraído do ID se omitido
- `numero_empresa`: Extraído do ID se omitido
- `tipo_colaborador`: Padrão = 1

## Endpoints da API

### REST Endpoints

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| GET | `/` | Página principal |
| POST | `/api/upload` | Upload de arquivo CSV |
| POST | `/api/authenticate` | Autenticação (usa .env) |
| POST | `/api/process` | Iniciar processamento |
| POST | `/api/retry` | Reenviar erros |
| GET | `/api/download/<filename>` | Download de resultados |
| GET | `/api/status` | Status da aplicação |

### WebSocket Events

| Event | Direção | Descrição |
|-------|---------|-----------|
| `connect` | Cliente → Servidor | Conexão estabelecida |
| `disconnect` | Cliente → Servidor | Desconexão |
| `log` | Servidor → Cliente | Mensagens de log |
| `progress` | Servidor → Cliente | Atualização de progresso |
| `processing_complete` | Servidor → Cliente | Processamento concluído |

## Console de Saída

O console exibe mensagens em tempo real com cores:

- 🟢 **Verde**: Sucessos e confirmações
- 🔵 **Azul**: Informações gerais
- 🟡 **Amarelo**: Avisos
- 🔴 **Vermelho**: Erros

Exemplo:
```
[14:35:12] Autenticando na plataforma Senior...
[14:35:15] ✓ Autenticação realizada com sucesso!
[14:35:16] Iniciando processamento de 150 registros...
[14:35:17] ✓ 303-1-29486 - ADRIANA FERREIRA - Sucesso
[14:35:18] ✗ 303-1-29487 - JOAO SILVA - Erro: Colaborador demitido
```

## Compatibilidade

### Navegadores Suportados
- Chrome/Edge 90+
- Firefox 88+
- Safari 14+

### Sistema CLI Original

O sistema CLI continua funcionando normalmente:

```bash
python envio_escala_api_corrigido.py
```

**Ambos compartilham:**
- Módulos de autenticação (`src/`)
- Lógica de processamento
- Sistema de retry
- Validações

## Configurações Avançadas

### Alterar Porta do Servidor

Edite `app.py`:

```python
socketio.run(app, host='0.0.0.0', port=8080, debug=True)
```

### Desabilitar Debug Mode

Para produção:

```python
socketio.run(app, host='0.0.0.0', port=5000, debug=False)
```

### Aumentar Limite de Upload

Edite `app.py`:

```python
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024  # 32MB
```

## Troubleshooting

### Erro: "Credenciais não configuradas"

✅ Verifique se o arquivo `.env` existe e está preenchido corretamente

### Erro: "Port 5000 already in use"

✅ Altere a porta em `app.py` ou finalize o processo:

```bash
# Windows
netstat -ano | findstr :5000
taskkill /PID <PID> /F

# Linux/Mac
lsof -ti:5000 | xargs kill -9
```

### WebSocket não conecta

✅ Certifique-se de que não há firewall bloqueando a porta
✅ Verifique se o navegador suporta WebSocket
✅ Limpe o cache do navegador

### Arquivo não faz upload

✅ Verifique se o arquivo é .csv
✅ Verifique se o tamanho é menor que 16MB
✅ Certifique-se de que o diretório `input_data/` existe

## Segurança

⚠️ **Importante:**

- As credenciais são armazenadas apenas no servidor (arquivo `.env`)
- Não expõe credenciais ao navegador
- Recomendado usar HTTPS em produção
- Considere adicionar autenticação de usuário para ambientes multi-usuário

## Performance

### Concorrência Recomendada

| Cenário | Requisições Simultâneas |
|---------|-------------------------|
| Desenvolvimento | 5-10 |
| Produção (rede boa) | 20-30 |
| Produção (rede lenta) | 5-15 |

### Métricas Típicas

- **Velocidade**: 3-5 requisições/segundo
- **Timeout**: 60 segundos por requisição
- **Retry**: Até 3 tentativas com backoff exponencial

## Desenvolvimento

### Estrutura do Código

**Backend (app.py):**
- Flask + Flask-SocketIO
- Importa classes do código CLI original
- Endpoints REST para operações
- WebSocket para comunicação em tempo real

**Frontend (app.js):**
- JavaScript puro (sem frameworks)
- Socket.IO client para WebSocket
- Gerenciamento de estado da aplicação
- Manipulação de eventos e UI

**Estilos (style.css):**
- Tema terminal escuro
- Cores inspiradas em editores de código
- Responsivo para mobile

## Suporte

Para reportar bugs ou sugerir melhorias:
- Verifique os logs no terminal onde o servidor está rodando
- Verifique o console do navegador (F12)
- Documente os passos para reproduzir o problema

## Licença

Este sistema é de uso interno da empresa.

---

**Desenvolvido para Swissport Brasil**
**Integração com API Senior Gestão de Ponto v7.0**
