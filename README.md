# Envio Automático de Escalas - API Senior

Sistema para envio automático de programações de escalas via API do Senior usando multithreading.

## Funcionalidades

- ✅ Envio de múltiplas requisições simultâneas (multithreading)
- ✅ Seleção interativa de arquivo CSV de entrada
- ✅ Geração de relatório CSV com resultados
- ✅ Tratamento robusto de erros e timeouts
- ✅ Interface de linha de comando amigável
- ✅ Sistema de logging completo

## Estrutura do Projeto

```
ENVIO_AUTOMATICO_ESCALA_SENIOR/
├── envio_escala_api.py          # Script principal
├── requirements.txt             # Dependências Python
├── input_data/                  # Diretório para arquivos CSV de entrada
│   └── exemplo_escala.csv       # Arquivo de exemplo
├── output_data/                 # Diretório para relatórios de saída
└── envio_escala.log            # Log do sistema (gerado automaticamente)
```

## Instalação

1. Certifique-se de ter Python 3.6+ instalado
2. Instale as dependências:
```bash
pip install -r requirements.txt
```

## Formato do CSV de Entrada

O arquivo CSV deve conter as seguintes colunas:

| Campo | Obrigatório | Descrição | Exemplo |
|-------|-------------|-----------|---------|
| `id_colaborador` | ✅ | ID único do colaborador | `303-1-29486` |
| `nome` | ✅ | Nome completo do colaborador | `ADRIANA FERREIRA ALVES RODRIGUES` |
| `data` | ✅ | Data da programação (YYYY-MM-DD) | `2025-10-27` |
| `codigo_horario` | ✅ | Código do horário | `1` |
| `numero_cadastro` | ❌ | Número de cadastro (extraído do ID se não fornecido) | `29486` |
| `numero_empresa` | ❌ | Número da empresa (extraído do ID se não fornecido) | `303` |
| `tipo_colaborador` | ❌ | Tipo do colaborador (padrão: 1) | `1` |

### Exemplo de CSV:
```csv
id_colaborador,nome,data,codigo_horario,numero_cadastro,numero_empresa,tipo_colaborador
303-1-29486,ADRIANA FERREIRA ALVES RODRIGUES,2025-10-27,1,29486,303,1
303-1-29487,JOAO SILVA SANTOS,2025-10-27,2,29487,303,1
```

## Como Usar

1. **Prepare o arquivo CSV:**
   - Coloque seu arquivo CSV no diretório `input_data/`
   - Use o arquivo `exemplo_escala.csv` como referência

2. **Execute o script:**
```bash
python envio_escala_api.py
```

3. **Configure os parâmetros:**
   - Digite o token de autenticação (assertion)
   - Escolha o número de threads (1-50, padrão: 5)
   - Selecione o arquivo CSV da lista

4. **Aguarde o processamento:**
   - O progresso será exibido em tempo real
   - Logs detalhados são salvos em `envio_escala.log`

5. **Verifique os resultados:**
   - Relatório CSV será salvo em `output_data/resultados_YYYYMMDD_HHMMSS.csv`

## Relatório de Saída

O arquivo CSV de resultados contém:

| Campo | Descrição |
|-------|-----------|
| `id_colaborador` | ID do colaborador processado |
| `nome` | Nome do colaborador |
| `data` | Data da programação |
| `codigo_horario` | Código do horário |
| `status_code` | Código HTTP da resposta (200, 400, 500, etc.) |
| `status` | Status do processamento (sucesso, erro, timeout) |
| `response_text` | Texto de resposta da API (truncado em 500 chars) |
| `tempo_resposta` | Tempo de resposta em segundos |
| `timestamp` | Data/hora do processamento |
| `erro` | Descrição do erro (se houver) |

## Configuração de Performance

- **Threads recomendadas:** 5-10 para uso normal
- **Máximo de threads:** 50 (limitado pelo sistema)
- **Timeout por requisição:** 30 segundos
- **Retry automático:** Não implementado (pode ser adicionado se necessário)

## Segurança

⚠️ **IMPORTANTE:**
- Nunca commite tokens de autenticação no código
- O token deve ser inserido apenas durante a execução
- Mantenha os logs seguros (podem conter informações sensíveis)

## Troubleshooting

### Erro: "Nenhum arquivo CSV encontrado"
- Verifique se o arquivo está na pasta `input_data/`
- Certifique-se de que a extensão é `.csv`

### Erro: "Token é obrigatório"
- Obtenha o token correto da interface do Senior
- O token é encontrado no header 'assertion' das requisições

### Muitos timeouts
- Reduza o número de threads
- Verifique a conexão com a internet
- Verifique se a API do Senior está disponível

### Erro 401/403
- Verifique se o token está correto e válido
- Confirme se tem permissões para acessar a API

## Logs

O sistema gera logs em dois locais:
- **Console:** Progresso em tempo real
- **Arquivo:** `envio_escala.log` com detalhes completos

## Exemplo de Uso Completo

```bash
$ python envio_escala_api.py

============================================================
           ENVIO AUTOMÁTICO DE ESCALAS - API SENIOR
============================================================
Digite o token de autenticação (assertion): eyJ...
Número de threads simultâneas (padrão: 5): 10

Arquivos CSV disponíveis:
----------------------------------------
1. exemplo_escala.csv
2. escala_outubro_2025.csv

Escolha um arquivo (1-2): 2

Carregando dados de: input_data/escala_outubro_2025.csv
Total de colaboradores carregados: 150

Iniciando envio de 150 programações usando 10 threads...
------------------------------------------------------------
Processado: 303-1-29486 - Status: sucesso
Processado: 303-1-29487 - Status: sucesso
...

============================================================
                        RESUMO FINAL
============================================================
Total de registros processados: 150
Sucessos: 148
Erros: 2
Tempo total: 45.32 segundos
Velocidade média: 3.31 req/seg
Resultados salvos em: output_data/resultados_20251027_143022.csv

Processamento concluído!
```