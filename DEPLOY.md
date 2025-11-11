# 🚀 Guia de Deploy - EnvioTurnosSenior

## ✅ Configuração de Produção Completa

Esta aplicação agora está configurada para **produção** usando **Gunicorn + eventlet**.

---

## 📦 O Que Foi Configurado

### 1. **Servidor de Produção**
- ✅ **Gunicorn** com worker class `eventlet`
- ✅ Suporte completo a **WebSocket** (Socket.IO)
- ✅ Logging otimizado para Docker/Coolify
- ✅ Health checks configurados
- ❌ Removido servidor de desenvolvimento Flask

### 2. **Dependências Atualizadas**
```txt
gunicorn>=21.2.0
eventlet>=0.33.0
```

### 3. **Dockerfile Otimizado**
- Usa Gunicorn como servidor principal
- Logs enviados para stdout/stderr (Docker-friendly)
- Usuário não-root (segurança)
- Health check automático

---

## 🔧 Deploy no Coolify

### Passo 1: Commit e Push

```bash
git add .
git commit -m "Configure production server with Gunicorn + eventlet"
git push
```

### Passo 2: Configurar no Coolify

1. **Build Pack:** Dockerfile
2. **Port:** 3000
3. **Variáveis de Ambiente:**
   ```env
   SENIOR_USERNAME=seu_usuario@empresa.com.br
   SENIOR_PASSWORD=sua_senha_aqui
   ```

4. **Volumes Persistentes (Opcional mas Recomendado):**
   - `/app/input_data` → Para uploads de CSV
   - `/app/output_data` → Para resultados processados

5. **Domínio:**
   - Configure: `https://senior.dartenmind.com.br`
   - SSL automático via Let's Encrypt

### Passo 3: Deploy

- Clique em "Deploy" no Coolify
- Aguarde o build completar
- Acesse seu domínio configurado

---

## ☁️ Configuração Cloudflare

### Para WebSocket Funcionar:

**Opção 1: DNS Only (Recomendado)**
1. Vá no DNS do Cloudflare
2. Encontre `senior.dartenmind.com.br`
3. Clique na **nuvem laranja 🟠** para ficar **cinza ☁️**
4. WebSocket funcionará perfeitamente

**Opção 2: Manter Proxy**
1. Mantenha **nuvem laranja 🟠**
2. Vá em **Network** → Ative **WebSockets**
3. Vá em **SSL/TLS** → **Full (strict)**

---

## 🧪 Teste Local (Opcional)

### Usando Docker Compose:

```bash
# Certifique-se que .env existe
docker-compose up --build
```

Acesse: `http://localhost:3000`

### Usando Python diretamente:

```bash
# Modo desenvolvimento (Flask dev server)
python app.py

# OU

# Modo produção (Gunicorn)
gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:3000 app:app
```

---

## 📊 Monitoramento

### Logs no Coolify:
- Todos os logs são enviados para stdout/stderr
- Acesse via interface do Coolify
- Logs de acesso e erro unificados

### Health Check:
- Endpoint: `http://localhost:3000/`
- Intervalo: 30 segundos
- Timeout: 10 segundos
- Retries: 3

---

## 🔍 Solução de Problemas

### WebSocket não conecta:
1. Verifique configuração do Cloudflare (DNS Only recomendado)
2. Confirme que porta 3000 está exposta
3. Verifique logs no Coolify

### Erro de autenticação Senior:
1. Verifique variáveis de ambiente no Coolify
2. Confirme credenciais corretas
3. Teste acesso manual à API Senior

### Container não inicia:
1. Verifique logs: `docker logs envio-turnos-senior`
2. Confirme que todas as dependências foram instaladas
3. Verifique se diretórios foram criados

---

## 📚 Arquitetura de Produção

```
Cloudflare DNS (opcional)
        ↓
Coolify (Reverse Proxy + SSL)
        ↓
Docker Container
        ↓
Gunicorn (WSGI Server)
        ↓
Eventlet (Async Worker)
        ↓
Flask + Socket.IO (App)
        ↓
Senior API
```

---

## 🎯 Características de Produção

- ✅ Servidor WSGI profissional (Gunicorn)
- ✅ Suporte async para WebSocket (eventlet)
- ✅ Logs estruturados
- ✅ Health checks automáticos
- ✅ Restart automático em caso de falha
- ✅ Usuário não-root (segurança)
- ✅ Configuração via variáveis de ambiente
- ✅ SSL/TLS via Coolify/Let's Encrypt

---

## 📞 Suporte

Para problemas ou dúvidas:
1. Verifique logs no Coolify
2. Consulte este guia
3. Revise configurações do Cloudflare

---

**Status:** ✅ Pronto para Produção

Última atualização: 2025-11-11
