#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import csv
import json
import os
import asyncio
import aiohttp
import time
from datetime import datetime
from typing import List, Dict, Any, Tuple
import logging
from dotenv import load_dotenv
from src.auth import authenticate_complete

# Carregar variáveis de ambiente
load_dotenv()

class EscalaAPIClient:
    """Cliente para envio de escalas via API com suporte a retry"""

    def __init__(self, base_url: str, token: str, max_retries: int = 3):
        self.base_url = base_url
        self.token = token
        self.max_retries = max_retries

        # Headers padrão baseados no curl fornecido
        self.headers = {
            'Host': 'webp20.seniorcloud.com.br:31531',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:143.0) Gecko/20100101 Firefox/143.0',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'pt-BR,pt;q=0.8,en-US;q=0.5,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Content-Type': 'application/json;charset=utf-8',
            'assertion': token,
            'Origin': 'https://webp20.seniorcloud.com.br:31531',
            'Connection': 'keep-alive',
            'Referer': 'https://webp20.seniorcloud.com.br:31531/gestaoponto-frontend/schedule/time-change/edit',
            'Cookie': 'br.com.senior.gp.backend=%7B%22url%22%3A%22https%3A%2F%2Fwebp20.seniorcloud.com.br%3A31531%2Fgestaoponto-backend%2Fapi%2F%22%7D'
        }
    
    async def enviar_programacao(self, session: aiohttp.ClientSession, colaborador_data: Dict[str, Any], semaphore: asyncio.Semaphore = None) -> Dict[str, Any]:
        """Envia programação de um colaborador via API com retry automático"""

        # Extrair dados do colaborador
        id_colaborador = colaborador_data.get('id_colaborador', 'N/A')
        nome = colaborador_data.get('nome', 'N/A')
        data_original = colaborador_data.get('data', 'N/A')
        codigo_horario = colaborador_data.get('codigo_horario', 'N/A')

        # Usar semáforo se fornecido (para controlar taxa de requisições)
        if semaphore:
            await semaphore.acquire()

        try:
            # Tentar até max_retries vezes
            return await self._tentar_envio(session, id_colaborador, nome, data_original, codigo_horario, colaborador_data)
        finally:
            if semaphore:
                semaphore.release()

    async def _tentar_envio(self, session: aiohttp.ClientSession, id_colaborador: str, nome: str, data_original: str, codigo_horario: str, colaborador_data: Dict[str, Any]) -> Dict[str, Any]:
        """Método interno para tentar envio com retry"""

        for tentativa in range(1, self.max_retries + 1):
            try:
                # Converter data para formato ISO (YYYY-MM-DD) se necessário
                try:
                    if '/' in data_original:
                        # Converter de DD/MM/YYYY para YYYY-MM-DD
                        partes_data = data_original.split('/')
                        if len(partes_data) == 3:
                            data = f"{partes_data[2]}-{partes_data[1].zfill(2)}-{partes_data[0].zfill(2)}"
                        else:
                            data = data_original
                    else:
                        data = data_original
                except:
                    data = data_original

                # Extrair campos do id_colaborador se não fornecidos
                # Formato: numeroEmpresa-tipoColaborador-numeroCadastro (ex: 303-1-29486)
                partes_id = id_colaborador.split('-')

                # Garantir que sempre temos valores válidos
                numero_empresa_csv = colaborador_data.get('numero_empresa', '').strip()
                tipo_colaborador_csv = colaborador_data.get('tipo_colaborador', '').strip()
                numero_cadastro_csv = colaborador_data.get('numero_cadastro', '').strip()

                # Se não fornecido no CSV ou vazio, extrair do ID
                numero_empresa = numero_empresa_csv if numero_empresa_csv else (partes_id[0] if len(partes_id) >= 1 and partes_id[0] else '303')
                tipo_colaborador = tipo_colaborador_csv if tipo_colaborador_csv else (partes_id[1] if len(partes_id) >= 2 and partes_id[1] else '1')
                numero_cadastro = numero_cadastro_csv if numero_cadastro_csv else (partes_id[2] if len(partes_id) >= 3 and partes_id[2] else '1')

                # Validar e garantir que são números válidos
                try:
                    numero_empresa = str(int(numero_empresa)) if numero_empresa.isdigit() else '303'
                    tipo_colaborador = str(int(tipo_colaborador)) if tipo_colaborador.isdigit() else '1'
                    numero_cadastro = str(int(numero_cadastro)) if numero_cadastro.isdigit() else '1'
                except (ValueError, AttributeError):
                    numero_empresa = '303'
                    tipo_colaborador = '1'
                    numero_cadastro = '1'

                # Construir URL da requisição
                url = f"{self.base_url}/colaboradores/{id_colaborador}/programacoes/trocas-horarios/{id_colaborador}-{data}"
                params = {
                    'RD_avisoInterjornada': 'YES',
                    'forcarRecalculo': 'false',
                    'gestor': 'S'
                }

                # Construir payload
                payload = {
                    "colaborador": {
                        "id": id_colaborador,
                        "nome": nome,
                        "numeroCadastro": int(numero_cadastro),
                        "numeroEmpresa": int(numero_empresa),
                        "tipoColaborador": int(tipo_colaborador)
                    },
                    "data": data,
                    "horario": {
                        "codigo": int(codigo_horario)
                    },
                    "customizacao": []
                }

                # Fazer requisição com timeout aumentado
                start_time = time.time()
                # Timeout: 10s para conectar, 60s total para requisição
                timeout = aiohttp.ClientTimeout(total=60, connect=10, sock_read=60)

                async with session.put(url, headers=self.headers, params=params, json=payload, timeout=timeout, ssl=False) as response:
                    response_text = await response.text()
                    end_time = time.time()

                    # Preparar resultado
                    result = {
                        'id_colaborador': id_colaborador,
                        'nome': nome,
                        'data': data,
                        'codigo_horario': codigo_horario,
                        'status_code': response.status,
                        'status': 'sucesso' if response.status in [200, 201, 204] else 'erro',
                        'response_text': response_text[:500] if response_text else '',
                        'tempo_resposta': round(end_time - start_time, 2),
                        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'erro': '',
                        'tentativas': tentativa
                    }

                    # Se sucesso, retornar
                    if response.status in [200, 201, 204]:
                        logging.info(f"Colaborador {id_colaborador}: {response.status} (tentativa {tentativa})")
                        return result

                    # Se erro e não é última tentativa, tentar novamente
                    if tentativa < self.max_retries:
                        delay = 0.5 * (2 ** (tentativa - 1))  # Backoff exponencial: 0.5s, 1s, 2s
                        logging.warning(f"Colaborador {id_colaborador}: erro {response.status} (tentativa {tentativa}/{self.max_retries}). Retentando em {delay}s...")
                        await asyncio.sleep(delay)
                    else:
                        logging.error(f"Colaborador {id_colaborador}: falhou após {tentativa} tentativas com status {response.status}")
                        return result

            except (asyncio.TimeoutError, aiohttp.ServerTimeoutError):
                if tentativa < self.max_retries:
                    # Delay maior para timeout: 2s, 4s, 8s
                    delay = 2 * (2 ** (tentativa - 1))
                    logging.warning(f"Colaborador {id_colaborador}: timeout (tentativa {tentativa}/{self.max_retries}). Retentando em {delay}s...")
                    await asyncio.sleep(delay)
                else:
                    logging.error(f"Colaborador {id_colaborador}: timeout após {tentativa} tentativas")
                    return {
                        'id_colaborador': id_colaborador,
                        'nome': nome,
                        'data': data_original,
                        'codigo_horario': codigo_horario,
                        'status_code': 0,
                        'status': 'timeout',
                        'response_text': 'Timeout na requisição após 3 tentativas (60s cada)',
                        'tempo_resposta': 60.0,
                        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'erro': 'Timeout',
                        'tentativas': tentativa
                    }

            except Exception as e:
                if tentativa < self.max_retries:
                    delay = 0.5 * (2 ** (tentativa - 1))
                    logging.warning(f"Colaborador {id_colaborador}: erro {str(e)} (tentativa {tentativa}/{self.max_retries}). Retentando em {delay}s...")
                    await asyncio.sleep(delay)
                else:
                    logging.error(f"Colaborador {id_colaborador}: erro após {tentativa} tentativas: {str(e)}")
                    return {
                        'id_colaborador': id_colaborador,
                        'nome': nome,
                        'data': data_original,
                        'codigo_horario': codigo_horario,
                        'status_code': 0,
                        'status': 'erro',
                        'response_text': str(e),
                        'tempo_resposta': 0,
                        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'erro': str(e),
                        'tentativas': tentativa
                    }

        # Fallback (nunca deveria chegar aqui)
        return {
            'id_colaborador': id_colaborador,
            'nome': nome,
            'data': data_original,
            'codigo_horario': codigo_horario,
            'status_code': 0,
            'status': 'erro',
            'response_text': 'Falha desconhecida',
            'tempo_resposta': 0,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'erro': 'Falha desconhecida',
            'tentativas': self.max_retries
        }
    
    async def processar_lote(self, colaboradores: List[Dict[str, Any]], max_concurrent: int = 10) -> List[Dict[str, Any]]:
        """Processa um lote de colaboradores usando asyncio com concorrência controlada"""

        # Criar connector com limite de conexões simultâneas
        # Reduzindo limite do connector para evitar sobrecarga
        connector = aiohttp.TCPConnector(limit=max_concurrent, limit_per_host=max_concurrent, ssl=False, ttl_dns_cache=300)
        timeout = aiohttp.ClientTimeout(total=None, connect=10, sock_read=60)

        # Semáforo para controlar taxa de requisições
        semaphore = asyncio.Semaphore(max_concurrent)

        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            # Criar todas as tarefas com semáforo
            tasks = [self.enviar_programacao(session, colaborador, semaphore) for colaborador in colaboradores]

            # Executar todas as tarefas concorrentemente
            resultados = await asyncio.gather(*tasks, return_exceptions=True)

            # Processar resultados
            resultados_finais = []
            for i, resultado in enumerate(resultados):
                if isinstance(resultado, Exception):
                    # Se houve exceção não tratada, criar resultado de erro
                    colaborador = colaboradores[i]
                    print(f"Erro ao processar {colaborador.get('id_colaborador', 'N/A')}: {resultado}")
                    resultados_finais.append({
                        'id_colaborador': colaborador.get('id_colaborador', 'N/A'),
                        'nome': colaborador.get('nome', 'N/A'),
                        'data': colaborador.get('data', 'N/A'),
                        'codigo_horario': colaborador.get('codigo_horario', 'N/A'),
                        'status_code': 0,
                        'status': 'erro',
                        'response_text': str(resultado),
                        'tempo_resposta': 0,
                        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'erro': str(resultado),
                        'tentativas': 0
                    })
                else:
                    # Log de progresso
                    print(f"Processado: {resultado['id_colaborador']} - Status: {resultado['status']} (tentativas: {resultado.get('tentativas', 1)})")
                    resultados_finais.append(resultado)

        return resultados_finais


def listar_arquivos_csv(diretorio: str = "input_data") -> List[str]:
    """Lista arquivos CSV no diretório especificado"""
    if not os.path.exists(diretorio):
        return []
    
    arquivos = [f for f in os.listdir(diretorio) if f.endswith('.csv')]
    return sorted(arquivos)


def selecionar_arquivo_csv() -> str:
    """Permite ao usuário selecionar um arquivo CSV"""
    arquivos = listar_arquivos_csv()
    
    if not arquivos:
        print("Nenhum arquivo CSV encontrado no diretório 'input_data'.")
        print("Por favor, adicione arquivos CSV ao diretório e tente novamente.")
        return None
    
    print("\nArquivos CSV disponíveis:")
    print("-" * 40)
    for i, arquivo in enumerate(arquivos, 1):
        print(f"{i}. {arquivo}")
    
    while True:
        try:
            escolha = input(f"\nEscolha um arquivo (1-{len(arquivos)}): ")
            indice = int(escolha) - 1
            
            if 0 <= indice < len(arquivos):
                return os.path.join("input_data", arquivos[indice])
            else:
                print("Opção inválida. Tente novamente.")
        except ValueError:
            print("Por favor, digite um número válido.")


def detectar_separador_csv(caminho_arquivo: str) -> str:
    """Detecta se o CSV usa vírgula (,) ou ponto e vírgula (;) como separador"""
    try:
        with open(caminho_arquivo, 'r', encoding='utf-8') as arquivo:
            primeira_linha = arquivo.readline()
            
            # Conta vírgulas e ponto e vírgulas
            virgulas = primeira_linha.count(',')
            ponto_virgulas = primeira_linha.count(';')
            
            # Retorna o separador mais comum
            if ponto_virgulas > virgulas:
                return ';'
            else:
                return ','
    except Exception:
        return ','  # Padrão vírgula em caso de erro


def ler_csv_colaboradores(caminho_arquivo: str) -> List[Dict[str, Any]]:
    """Lê arquivo CSV e retorna lista de colaboradores"""
    colaboradores = []

    try:
        # Detectar separador automaticamente
        separador = detectar_separador_csv(caminho_arquivo)
        print(f"Separador detectado: '{separador}'")

        # utf-8-sig remove automaticamente o BOM (\ufeff) se presente
        with open(caminho_arquivo, 'r', encoding='utf-8-sig') as arquivo:
            reader = csv.DictReader(arquivo, delimiter=separador)
            
            for linha in reader:
                # Validar campos obrigatórios
                campos_obrigatorios = ['id_colaborador', 'nome', 'data', 'codigo_horario']
                if all(campo in linha and linha[campo].strip() for campo in campos_obrigatorios):
                    colaboradores.append({
                        'id_colaborador': linha['id_colaborador'].strip(),
                        'nome': linha['nome'].strip(),
                        'data': linha['data'].strip(),
                        'codigo_horario': linha['codigo_horario'].strip(),
                        'numero_cadastro': linha.get('numero_cadastro', '').strip(),
                        'numero_empresa': linha.get('numero_empresa', '').strip(),
                        'tipo_colaborador': linha.get('tipo_colaborador', '1').strip()
                    })
                else:
                    print(f"Linha ignorada por falta de dados obrigatórios: {linha}")
        
        print(f"Total de colaboradores carregados: {len(colaboradores)}")
        return colaboradores
        
    except Exception as e:
        print(f"Erro ao ler arquivo CSV: {e}")
        return []


def salvar_resultados_csv(resultados: List[Dict[str, Any]], diretorio: str = "output_data") -> str:
    """Salva resultados em arquivo CSV"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    nome_arquivo = f"resultados_{timestamp}.csv"
    caminho_completo = os.path.join(diretorio, nome_arquivo)

    # Certificar que o diretório existe
    os.makedirs(diretorio, exist_ok=True)

    campos = [
        'id_colaborador', 'nome', 'data', 'codigo_horario', 'status_code',
        'status', 'tentativas', 'response_text', 'tempo_resposta', 'timestamp', 'erro'
    ]
    
    try:
        with open(caminho_completo, 'w', newline='', encoding='utf-8') as arquivo:
            writer = csv.DictWriter(arquivo, fieldnames=campos)
            writer.writeheader()
            writer.writerows(resultados)
        
        print(f"Resultados salvos em: {caminho_completo}")
        return caminho_completo
        
    except Exception as e:
        print(f"Erro ao salvar resultados: {e}")
        return None


def configurar_logging():
    """Configura sistema de logging"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('envio_escala.log'),
            logging.StreamHandler()
        ]
    )


def obter_configuracao_usuario() -> Tuple[str, int]:
    """Obtém configurações do usuário e realiza autenticação automática"""
    print("=" * 60)
    print("           ENVIO AUTOMÁTICO DE ESCALAS - API SENIOR")
    print("=" * 60)

    # Obter credenciais do .env
    username = os.getenv('SENIOR_USERNAME')
    password = os.getenv('SENIOR_PASSWORD')

    if not username or not password:
        print("\n❌ ERRO: Credenciais não configuradas!")
        print("Por favor, configure as variáveis SENIOR_USERNAME e SENIOR_PASSWORD no arquivo .env")
        return None, None

    print(f"\n🔐 Realizando autenticação automática...")
    print(f"Usuário: {username}")

    try:
        # Autenticar e obter token da Gestão de Ponto
        result = authenticate_complete(username, password)

        if not result['success']:
            print(f"\n❌ Falha na autenticação: {result.get('error', 'Erro desconhecido')}")
            return None, None

        # O token da Gestão de Ponto é o que usamos no header 'assertion'
        token = result['gestaoponto_token']

        if not token:
            print("\n❌ Token da Gestão de Ponto não foi obtido!")
            print(f"Autenticação Senior OK, mas falha ao obter token Gestão de Ponto")
            return None, None

        # Exibir informações do usuário
        user_info = result['user_info']['user_info']
        print(f"✅ Autenticação bem-sucedida!")
        print(f"👤 Nome: {user_info['full_name']}")
        print(f"📧 Email: {user_info['email']}")
        print(f"🏢 Empresa: {user_info['tenant_name']}")
        print(f"🔑 Token obtido: {token[:50]}..." if len(token) > 50 else f"🔑 Token obtido: {token}")

    except Exception as e:
        print(f"\n❌ Erro durante autenticação: {str(e)}")
        import traceback
        traceback.print_exc()
        return None, None

    # Número de requisições simultâneas (agora asyncio ao invés de threads)
    print("\nDica: Se estiver tendo timeouts, use valores menores (3-5)")
    while True:
        try:
            num_concurrent = input("Número de requisições simultâneas (padrão: 5, max: 50): ").strip()
            num_concurrent = int(num_concurrent) if num_concurrent else 5

            if 1 <= num_concurrent <= 50:
                break
            else:
                print("Número de requisições deve estar entre 1 e 50.")
        except ValueError:
            print("Por favor, digite um número válido.")

    return token, num_concurrent


async def processar_escalas():
    """Função assíncrona principal para processar escalas"""

    # Obter configurações do usuário
    token, num_concurrent = obter_configuracao_usuario()
    if not token:
        return

    # Selecionar arquivo CSV
    caminho_csv = selecionar_arquivo_csv()
    if not caminho_csv:
        return

    # Carregar dados dos colaboradores
    print(f"\nCarregando dados de: {caminho_csv}")
    colaboradores = ler_csv_colaboradores(caminho_csv)

    if not colaboradores:
        print("Nenhum colaborador válido encontrado no arquivo.")
        return

    # Configurar cliente da API
    base_url = "https://webp20.seniorcloud.com.br:31531/gestaoponto-backend/api"
    client = EscalaAPIClient(base_url, token, max_retries=3)

    # Processar envios
    print(f"\nIniciando envio de {len(colaboradores)} programações usando asyncio (max {num_concurrent} simultâneas)...")
    print("Sistema de retry: 3 tentativas com backoff exponencial")
    print("Timeout por requisição: 60 segundos (10s conexão + 60s leitura)")
    print("-" * 60)

    inicio = time.time()

    resultados = await client.processar_lote(colaboradores, num_concurrent)
    fim = time.time()

    # Estatísticas
    total_tempo = round(fim - inicio, 2)
    sucessos = len([r for r in resultados if r['status'] == 'sucesso'])
    erros = len(resultados) - sucessos

    # Calcular estatísticas de retry
    com_retry = len([r for r in resultados if r.get('tentativas', 1) > 1])
    total_tentativas = sum([r.get('tentativas', 1) for r in resultados])

    print("\n" + "=" * 60)
    print("                        RESUMO FINAL")
    print("=" * 60)
    print(f"Total de registros processados: {len(resultados)}")
    print(f"Sucessos: {sucessos}")
    print(f"Erros: {erros}")
    print(f"Requisições que precisaram de retry: {com_retry}")
    print(f"Total de tentativas realizadas: {total_tentativas}")
    print(f"Tempo total: {total_tempo} segundos")
    print(f"Velocidade média: {round(len(resultados)/total_tempo, 2)} req/seg")

    # Salvar resultados
    arquivo_resultado = salvar_resultados_csv(resultados)

    if arquivo_resultado:
        print(f"Relatório completo salvo em: {arquivo_resultado}")

    print("\nProcessamento concluído!")


def main():
    """Função principal"""
    configurar_logging()

    # Executar função assíncrona
    asyncio.run(processar_escalas())


if __name__ == "__main__":
    main()