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

# Importar módulo de conversão de dados
import data_convert


class TokenExpiradoException(Exception):
    """Exceção levantada quando o token de autenticação expira"""
    pass


class EscalaAPIClient:
    """Cliente para envio de escalas via API com suporte a retry"""

    def __init__(self, base_url: str, token: str, max_retries: int = 3):
        self.base_url = base_url
        self.token = token
        self.max_retries = max_retries

        # Headers padrão baseados no curl fornecido
        self.headers = {
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
            'Connection': 'keep-alive',
            'Content-Type': 'application/json;charset=UTF-8',
            'assertion': token,
            'Origin': 'https://webp20.seniorcloud.com.br:31531',
            'Referer': 'https://webp20.seniorcloud.com.br:31531/gestaoponto-frontend/schedule/time-change/edit?timeChangeId=303-1-31344-2025-11-03&timeChangeUserId=303-1-31344',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            'User-Agent': 'Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Mobile Safari/537.36 Edg/141.0.0.0',
            'sec-ch-ua': '"Microsoft Edge";v="141", "Not?A_Brand";v="8", "Chromium";v="141"',
            'sec-ch-ua-mobile': '?1',
            'sec-ch-ua-platform': '"Android"',
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

                async with session.put(url, headers=self.headers, params=params, json=payload, timeout=timeout) as response:
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

                    # Se erro 401, token expirado - levantar exceção específica
                    if response.status == 401:
                        logging.error(f"Token expirado (401 Unauthorized)")
                        raise TokenExpiradoException("Token de autenticação expirado ou inválido")

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
        # Removendo ssl=False para usar SSL normalmente
        connector = aiohttp.TCPConnector(limit=max_concurrent, limit_per_host=max_concurrent, ttl_dns_cache=300)
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


def salvar_resultados_csv(resultados: List[Dict[str, Any]], diretorio: str = "output_data", caminho_existente: str = None) -> str:
    """
    Salva resultados em arquivo CSV.

    Args:
        resultados: Lista de resultados a serem salvos
        diretorio: Diretório onde salvar o arquivo
        caminho_existente: Se fornecido, sobrescreve arquivo existente

    Returns:
        Caminho do arquivo salvo
    """
    # Se tem caminho existente, usar esse
    if caminho_existente:
        caminho_completo = caminho_existente
    else:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        nome_arquivo = f"resultados_{timestamp}.csv"
        caminho_completo = os.path.join(diretorio, nome_arquivo)

    # Certificar que o diretório existe
    os.makedirs(diretorio, exist_ok=True)

    campos = [
        'id_colaborador', 'nome', 'data', 'codigo_horario', 'status_code',
        'status', 'tentativas', 'numero_retry', 'response_text', 'tempo_resposta', 'timestamp', 'erro'
    ]

    try:
        # Garantir que todos os resultados têm o campo numero_retry
        for resultado in resultados:
            if 'numero_retry' not in resultado:
                resultado['numero_retry'] = 0

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


def separar_sucessos_e_erros(resultados: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Separa resultados em sucessos e erros.

    Args:
        resultados: Lista de resultados do processamento

    Returns:
        Tupla (sucessos, erros)
    """
    sucessos = [r for r in resultados if r['status'] == 'sucesso']
    erros = [r for r in resultados if r['status'] != 'sucesso']
    return sucessos, erros


def exibir_resumo_erros(erros: List[Dict[str, Any]]) -> None:
    """
    Exibe resumo formatado dos erros.

    Args:
        erros: Lista de requisições com erro
    """
    if not erros:
        return

    print("\n" + "=" * 100)
    print("                                  REQUISIÇÕES COM ERRO")
    print("=" * 100)

    # Cabeçalho da tabela
    print(f"{'#':<4} {'ID Colaborador':<18} {'Nome':<30} {'Data':<12} {'Tipo Erro':<15}")
    print("-" * 100)

    # Agrupar por tipo de erro para estatísticas
    erros_por_tipo = {}

    for i, erro in enumerate(erros, 1):
        id_colab = erro.get('id_colaborador', 'N/A')
        nome = erro.get('nome', 'N/A')
        data = erro.get('data', 'N/A')
        status = erro.get('status', 'erro')
        status_code = erro.get('status_code', 0)

        # Determinar tipo de erro
        if status == 'timeout':
            tipo_erro = 'Timeout'
        elif status_code == 401:
            tipo_erro = 'Token Expirado'
        elif status_code >= 500:
            tipo_erro = f'Erro Servidor ({status_code})'
        elif status_code >= 400:
            tipo_erro = f'Erro Cliente ({status_code})'
        else:
            tipo_erro = 'Erro Geral'

        # Truncar nome se muito longo
        nome_truncado = nome[:27] + '...' if len(nome) > 30 else nome

        # Exibir linha
        print(f"{i:<4} {id_colab:<18} {nome_truncado:<30} {data:<12} {tipo_erro:<15}")

        # Contar por tipo
        erros_por_tipo[tipo_erro] = erros_por_tipo.get(tipo_erro, 0) + 1

    print("-" * 100)
    print(f"Total de erros: {len(erros)}")

    # Estatísticas por tipo
    print("\nErros por tipo:")
    for tipo, quantidade in erros_por_tipo.items():
        print(f"  - {tipo}: {quantidade}")

    print("=" * 100)


def menu_retry_erros() -> bool:
    """
    Pergunta ao usuário se deseja reenviar requisições com erro.

    Returns:
        True se usuário quer tentar novamente, False caso contrário
    """
    print("\n" + "=" * 60)
    print("           DESEJA TENTAR REENVIAR AS REQUISIÇÕES COM ERRO?")
    print("=" * 60)
    print("1. Sim - Tentar novamente")
    print("2. Não - Finalizar processamento")
    print("=" * 60)

    while True:
        try:
            escolha = input("\nEscolha uma opção (1-2): ").strip()
            escolha_int = int(escolha)

            if escolha_int == 1:
                return True
            elif escolha_int == 2:
                return False
            else:
                print("Opção inválida. Por favor, escolha 1 ou 2.")
        except ValueError:
            print("Por favor, digite um número válido (1 ou 2).")


def detectar_formato_csv(caminho_arquivo: str) -> str:
    """
    Detecta o formato do arquivo CSV.

    Retorna:
        "grid" - Formato grid/calendário (NOME;MAT;COD. ESCALA;datas...)
        "api" - Formato API Senior (id_colaborador;nome;data;codigo_horario)
        "desconhecido" - Formato não reconhecido
    """
    try:
        with open(caminho_arquivo, 'r', encoding='utf-8-sig') as arquivo:
            reader = csv.DictReader(arquivo, delimiter=';')
            header = reader.fieldnames

            if not header:
                return "desconhecido"

            # Normalizar header para comparação (lowercase e sem espaços)
            header_clean = [col.strip().upper() for col in header]

            # Verificar se é formato grid
            # Deve ter: NOME, MAT, COD. ESCALA
            has_nome = any('NOME' in col for col in header_clean)
            has_mat = any('MAT' in col and 'MATRICULA' not in col for col in header_clean)
            has_cod_escala = any('COD' in col and 'ESCALA' in col for col in header_clean)

            if has_nome and has_mat and has_cod_escala:
                return "grid"

            # Verificar se é formato API
            # Deve ter: id_colaborador, nome, data, codigo_horario
            has_id = any('ID_COLABORADOR' in col for col in header_clean)
            has_nome_api = any(col == 'NOME' for col in header_clean)
            has_data = any(col == 'DATA' for col in header_clean)
            has_codigo = any('CODIGO' in col and 'HORARIO' in col for col in header_clean)

            if has_id and has_nome_api and has_data and has_codigo:
                return "api"

            return "desconhecido"

    except Exception as e:
        print(f"Erro ao detectar formato do CSV: {e}")
        return "desconhecido"


def processar_conversao(caminho_arquivo: str) -> str:
    """
    Processa a conversão do arquivo usando o módulo data_convert.

    Args:
        caminho_arquivo: Caminho do arquivo a ser convertido

    Returns:
        Caminho do arquivo convertido ou None em caso de erro
    """
    try:
        # Gerar nome do arquivo convertido
        diretorio = os.path.dirname(caminho_arquivo)
        nome_base = os.path.splitext(os.path.basename(caminho_arquivo))[0]
        arquivo_convertido = os.path.join(diretorio, f"{nome_base}_converted.csv")

        print("\n" + "=" * 70)
        print("INICIANDO CONVERSAO DE DADOS")
        print("=" * 70)

        # Chamar função de conversão do módulo data_convert
        sucesso, total, mensagem = data_convert.convert_dados_to_senior(
            input_path=caminho_arquivo,
            output_path=arquivo_convertido,
            horarios_path='horarios.csv'
        )

        if sucesso:
            print("\n" + "=" * 70)
            print("[OK] CONVERSAO CONCLUIDA COM SUCESSO!")
            print("=" * 70)
            print(f"Total de registros convertidos: {total}")
            print(f"Arquivo convertido: {arquivo_convertido}")
            print("=" * 70)
            return arquivo_convertido
        else:
            print("\n" + "=" * 70)
            print("[ERRO] FALHA NA CONVERSAO")
            print("=" * 70)
            print(f"Mensagem: {mensagem}")
            print("=" * 70)
            return None

    except Exception as e:
        print(f"\n[ERRO] Erro ao processar conversao: {e}")
        import traceback
        traceback.print_exc()
        return None


def exibir_menu_continuacao() -> int:
    """
    Exibe menu de continuação e retorna a escolha do usuário.

    Returns:
        1 - Processar outro arquivo
        2 - Sair
    """
    print("\n" + "=" * 60)
    print("                    O QUE DESEJA FAZER?")
    print("=" * 60)
    print("1. Processar outro arquivo")
    print("2. Sair")
    print("=" * 60)

    while True:
        try:
            escolha = input("\nEscolha uma opção (1-2): ").strip()
            escolha_int = int(escolha)

            if escolha_int in [1, 2]:
                return escolha_int
            else:
                print("Opção inválida. Por favor, escolha 1 ou 2.")
        except ValueError:
            print("Por favor, digite um número válido (1 ou 2).")


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


async def processar_escalas(token: str = None, num_concurrent: int = None):
    """
    Função assíncrona principal para processar escalas.

    Args:
        token: Token de autenticação (opcional). Se não fornecido, realiza autenticação.
        num_concurrent: Número de requisições simultâneas (opcional). Se não fornecido, pergunta ao usuário.
    """

    # Obter configurações do usuário se não fornecidas
    if not token or not num_concurrent:
        token_obtido, num_concurrent_obtido = obter_configuracao_usuario()
        if not token_obtido:
            return

        # Usar valores obtidos se não foram fornecidos
        token = token or token_obtido
        num_concurrent = num_concurrent or num_concurrent_obtido

    # Selecionar arquivo CSV
    caminho_csv = selecionar_arquivo_csv()
    if not caminho_csv:
        return

    # Detectar formato do arquivo
    print("\nDetectando formato do arquivo...")
    formato = detectar_formato_csv(caminho_csv)

    if formato == "grid":
        print("\n" + "=" * 70)
        print("FORMATO GRID DETECTADO - CONVERSAO NECESSARIA")
        print("=" * 70)
        print(f"Arquivo: {os.path.basename(caminho_csv)}")
        print("Este arquivo esta no formato grid e precisa ser convertido")
        print("para o formato da API antes do envio.")
        print("=" * 70)

        converter = input("\nDeseja converter agora? (s/n): ").strip().lower()

        if converter in ['s', 'sim', 'y', 'yes']:
            caminho_convertido = processar_conversao(caminho_csv)
            if caminho_convertido:
                print(f"\n[OK] Usando arquivo convertido: {os.path.basename(caminho_convertido)}")
                caminho_csv = caminho_convertido
            else:
                print("\n[ERRO] Falha na conversao. Abortando envio.")
                return
        else:
            print("\n[INFO] Conversao cancelada pelo usuario. Abortando envio.")
            return

    elif formato == "api":
        print("[OK] Formato API detectado - arquivo pronto para envio")

    else:
        print("[AVISO] Formato nao reconhecido. Tentando processar como formato API...")

    # Carregar dados dos colaboradores
    print(f"\nCarregando dados de: {os.path.basename(caminho_csv)}")
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

    # Inicializar numero_retry em todos os resultados
    for resultado in resultados:
        resultado['numero_retry'] = 0

    # Estatísticas iniciais
    total_tempo = round(fim - inicio, 2)
    sucessos = len([r for r in resultados if r['status'] == 'sucesso'])
    erros = len(resultados) - sucessos

    # Calcular estatísticas de retry
    com_retry = len([r for r in resultados if r.get('tentativas', 1) > 1])
    total_tentativas = sum([r.get('tentativas', 1) for r in resultados])

    print("\n" + "=" * 60)
    print("                    RESUMO DO PROCESSAMENTO INICIAL")
    print("=" * 60)
    print(f"Total de registros processados: {len(resultados)}")
    print(f"Sucessos: {sucessos}")
    print(f"Erros: {erros}")
    print(f"Requisições que precisaram de retry: {com_retry}")
    print(f"Total de tentativas realizadas: {total_tentativas}")
    print(f"Tempo total: {total_tempo} segundos")
    print(f"Velocidade média: {round(len(resultados)/total_tempo, 2)} req/seg")

    # Salvar resultados iniciais
    arquivo_resultado = salvar_resultados_csv(resultados)

    if arquivo_resultado:
        print(f"Relatório completo salvo em: {arquivo_resultado}")

    # Loop de retry interativo
    numero_ciclo_retry = 0
    while True:
        # Separar sucessos e erros
        sucessos_lista, erros_lista = separar_sucessos_e_erros(resultados)

        # Se não há erros, finalizar
        if not erros_lista:
            print("\n" + "=" * 60)
            print("✅ TODAS AS REQUISIÇÕES FORAM PROCESSADAS COM SUCESSO!")
            print("=" * 60)
            break

        # Exibir resumo de erros
        exibir_resumo_erros(erros_lista)

        # Perguntar se quer tentar novamente
        if not menu_retry_erros():
            print("\n" + "=" * 60)
            print("Processamento finalizado. Alguns erros permaneceram.")
            print(f"Total de sucessos: {len(sucessos_lista)}")
            print(f"Total de erros: {len(erros_lista)}")
            print("=" * 60)
            break

        # Incrementar contador de ciclo
        numero_ciclo_retry += 1

        print("\n" + "=" * 60)
        print(f"           INICIANDO RETRY #{numero_ciclo_retry}")
        print("=" * 60)
        print(f"Reenviando {len(erros_lista)} requisições com erro...")
        print("-" * 60)

        # Preparar dados dos colaboradores que falharam
        colaboradores_retry = []
        for erro in erros_lista:
            colaboradores_retry.append({
                'id_colaborador': erro['id_colaborador'],
                'nome': erro['nome'],
                'data': erro['data'],
                'codigo_horario': erro['codigo_horario'],
                'numero_cadastro': '',
                'numero_empresa': '',
                'tipo_colaborador': '1'
            })

        # Processar novamente apenas os erros
        inicio_retry = time.time()
        resultados_retry = await client.processar_lote(colaboradores_retry, num_concurrent)
        fim_retry = time.time()
        tempo_retry = round(fim_retry - inicio_retry, 2)

        # Atualizar resultados - substituir os erros pelos novos resultados
        # Criar dicionário para busca rápida
        novos_resultados_dict = {}
        for novo in resultados_retry:
            chave = f"{novo['id_colaborador']}_{novo['data']}"
            novo['numero_retry'] = numero_ciclo_retry
            novos_resultados_dict[chave] = novo

        # Atualizar lista de resultados
        for i, resultado in enumerate(resultados):
            chave = f"{resultado['id_colaborador']}_{resultado['data']}"
            if chave in novos_resultados_dict:
                resultados[i] = novos_resultados_dict[chave]

        # Estatísticas do retry
        sucessos_retry = len([r for r in resultados_retry if r['status'] == 'sucesso'])
        erros_retry = len(resultados_retry) - sucessos_retry

        print("\n" + "=" * 60)
        print(f"           RESUMO DO RETRY #{numero_ciclo_retry}")
        print("=" * 60)
        print(f"Requisições reprocessadas: {len(resultados_retry)}")
        print(f"Sucessos neste retry: {sucessos_retry}")
        print(f"Erros restantes: {erros_retry}")
        print(f"Tempo do retry: {tempo_retry} segundos")
        print("=" * 60)

        # Salvar resultados atualizados (sobrescrever arquivo)
        salvar_resultados_csv(resultados, caminho_existente=arquivo_resultado)

    # Exibir resumo final
    sucessos_finais, erros_finais = separar_sucessos_e_erros(resultados)

    print("\n" + "=" * 60)
    print("                        RESUMO FINAL")
    print("=" * 60)
    print(f"Total de registros: {len(resultados)}")
    print(f"Sucessos: {len(sucessos_finais)}")
    print(f"Erros: {len(erros_finais)}")
    print(f"Ciclos de retry executados: {numero_ciclo_retry}")
    print("=" * 60)

    print("\nProcessamento concluído!")

    # Retornar token e num_concurrent para reutilização
    return token, num_concurrent


async def processar_escalas_com_retry_token(token: str = None, num_concurrent: int = None):
    """
    Wrapper para processar_escalas com reautenticação automática em caso de token expirado.

    Args:
        token: Token de autenticação (opcional)
        num_concurrent: Número de requisições simultâneas (opcional)

    Returns:
        Tupla (token, num_concurrent) para reutilização
    """
    try:
        # Tentar processar com token fornecido
        resultado = await processar_escalas(token, num_concurrent)
        return resultado

    except TokenExpiradoException as e:
        # Token expirou durante o processamento
        print("\n" + "=" * 60)
        print("⚠️  TOKEN EXPIRADO DETECTADO")
        print("=" * 60)
        print("O token de autenticação expirou durante o processamento.")
        print("Realizando reautenticação automática...")
        print("=" * 60)

        # Reautenticar automaticamente
        username = os.getenv('SENIOR_USERNAME')
        password = os.getenv('SENIOR_PASSWORD')

        if not username or not password:
            print("\n❌ ERRO: Credenciais não configuradas no .env")
            return None, None

        try:
            result = authenticate_complete(username, password)

            if not result['success']:
                print(f"\n❌ Falha na reautenticação: {result.get('error', 'Erro desconhecido')}")
                return None, None

            novo_token = result['gestaoponto_token']
            print(f"✅ Reautenticação bem-sucedida!")
            print(f"🔑 Novo token obtido")

            # Tentar novamente com novo token
            print("\nRetomando processamento com novo token...")
            resultado = await processar_escalas(novo_token, num_concurrent)
            return resultado

        except Exception as reauth_error:
            print(f"\n❌ Erro durante reautenticação: {str(reauth_error)}")
            return None, None


def main():
    """Função principal"""
    configurar_logging()

    token = None
    num_concurrent = None

    # Loop principal de execução contínua
    while True:
        try:
            # Executar processamento (reutilizando token se disponível)
            resultado = asyncio.run(processar_escalas_com_retry_token(token, num_concurrent))

            # Se falhou, resetar credenciais
            if resultado is None or resultado == (None, None):
                print("\n❌ Erro no processamento. Encerrando...")
                break

            # Desempacotar resultado
            token, num_concurrent = resultado

            # Exibir menu de continuação
            escolha = exibir_menu_continuacao()

            if escolha == 1:
                # Usuário quer processar outro arquivo
                print("\n" + "=" * 60)
                print("Iniciando novo processamento (reutilizando token)...")
                print("=" * 60)
                continue
            elif escolha == 2:
                # Usuário quer sair
                print("\n" + "=" * 60)
                print("Encerrando aplicação. Até logo!")
                print("=" * 60)
                break

        except KeyboardInterrupt:
            print("\n\n" + "=" * 60)
            print("Execução interrompida pelo usuário (Ctrl+C)")
            print("=" * 60)
            break
        except Exception as e:
            print(f"\n❌ Erro inesperado: {str(e)}")
            import traceback
            traceback.print_exc()
            break


if __name__ == "__main__":
    main()