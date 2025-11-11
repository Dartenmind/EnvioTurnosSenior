#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Servidor Flask para Interface Web de Envio de Escalas
Integra com o código existente em envio_escala_api_corrigido.py
"""

import os
import asyncio
import csv
from datetime import datetime
from typing import List, Dict, Any
from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_socketio import SocketIO, emit
from flask_cors import CORS
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

# Importar módulos existentes
from src.auth import authenticate_complete
from envio_escala_api_corrigido import (
    EscalaAPIClient,
    detectar_separador_csv,
    salvar_resultados_csv,
    separar_sucessos_e_erros
)

# Carregar variáveis de ambiente
load_dotenv()

# Configuração do Flask
app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
app.config['UPLOAD_FOLDER'] = 'input_data'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max

# Habilitar CORS e SocketIO
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Estado global da aplicação
app_state = {
    'processing': False,
    'current_file': None,
    'results_file': None,
    'token': None,
    'authenticated': False
}


def emit_log(message: str, log_type: str = 'info'):
    """Emite mensagem de log via WebSocket"""
    timestamp = datetime.now().strftime('%H:%M:%S')
    socketio.emit('log', {
        'message': message,
        'type': log_type,
        'timestamp': timestamp
    })


def emit_progress(current: int, total: int, successes: int, errors: int):
    """Emite progresso via WebSocket"""
    socketio.emit('progress', {
        'current': current,
        'total': total,
        'successes': successes,
        'errors': errors,
        'percentage': round((current / total) * 100, 1) if total > 0 else 0
    })


def detectar_formato_csv(caminho_arquivo: str) -> str:
    """
    Detecta se o arquivo CSV está no formato API ou Grid.

    Formato API: id_colaborador;nome;data;codigo_horario;...
    Formato Grid: NOME;mat;COD. ESCALA;01/11/2025;02/11/2025;...

    Returns:
        'api' ou 'grid'
    """
    try:
        separador = detectar_separador_csv(caminho_arquivo)

        with open(caminho_arquivo, 'r', encoding='utf-8-sig') as arquivo:
            primeira_linha = arquivo.readline().strip()

            # Normalizar cabeçalho para comparação (minúsculas, sem espaços extras)
            cabecalho_lower = primeira_linha.lower()

            # Verificar formato API - procura por campos específicos
            if 'id_colaborador' in cabecalho_lower or 'id colaborador' in cabecalho_lower:
                return 'api'

            # Verificar formato Grid - procura por NOME, mat, COD. ESCALA e datas
            if 'nome' in cabecalho_lower and 'mat' in cabecalho_lower:
                # Verificar se tem colunas com datas (formato dd/mm/yyyy)
                partes = primeira_linha.split(separador)
                for parte in partes[3:]:  # Pular NOME, mat, COD. ESCALA
                    if '/' in parte and len(parte) == 10:  # Formato dd/mm/yyyy
                        return 'grid'

            # Se não identificou claramente, tentar pela estrutura
            if 'escala' in cabecalho_lower:
                return 'grid'

            # Padrão: tentar como API
            return 'api'

    except Exception as e:
        emit_log(f"Erro ao detectar formato: {e}. Assumindo formato API.", 'warning')
        return 'api'


def validar_arquivo_horarios() -> bool:
    """
    Valida se o arquivo horarios.csv existe e está acessível.

    Returns:
        True se o arquivo existe e é válido, False caso contrário
    """
    arquivo_horarios = 'horarios.csv'

    if not os.path.exists(arquivo_horarios):
        return False

    try:
        # Tentar ler o arquivo para verificar se está acessível
        with open(arquivo_horarios, 'r', encoding='utf-8-sig') as f:
            primeira_linha = f.readline()
            if not primeira_linha:
                return False
        return True
    except Exception:
        return False


def converter_grid_para_api(caminho_arquivo_grid: str) -> str:
    """
    Converte arquivo CSV do formato Grid para formato API.

    Args:
        caminho_arquivo_grid: Caminho do arquivo no formato Grid

    Returns:
        Caminho do arquivo convertido no formato API
    """
    try:
        # Importar função de conversão
        import data_convert

        # Gerar nome do arquivo convertido
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        nome_base = os.path.splitext(os.path.basename(caminho_arquivo_grid))[0]
        caminho_convertido = os.path.join(
            app.config['UPLOAD_FOLDER'],
            f"{nome_base}_converted_{timestamp}.csv"
        )

        emit_log('Detectado formato GRID (calendário). Iniciando conversão...', 'info')
        emit_log('Usando arquivo de mapeamento: horarios.csv', 'info')

        # Realizar conversão usando módulo existente
        data_convert.convert_dados_to_senior(
            input_path=caminho_arquivo_grid,
            output_path=caminho_convertido,
            horarios_path='horarios.csv'
        )

        # Verificar se arquivo convertido foi criado
        if os.path.exists(caminho_convertido):
            # Contar registros convertidos
            with open(caminho_convertido, 'r', encoding='utf-8-sig') as f:
                linhas = sum(1 for _ in f) - 1  # -1 para descontar o cabeçalho

            emit_log(f'✓ Conversão concluída: {linhas} registros gerados', 'success')
            return caminho_convertido
        else:
            raise Exception('Arquivo convertido não foi gerado')

    except Exception as e:
        emit_log(f'✗ Erro na conversão: {str(e)}', 'error')
        raise


def ler_csv_colaboradores_web(caminho_arquivo: str) -> List[Dict[str, Any]]:
    """Lê arquivo CSV e retorna lista de colaboradores (versão adaptada para web)"""
    colaboradores = []

    try:
        separador = detectar_separador_csv(caminho_arquivo)
        emit_log(f"Separador detectado: '{separador}'", 'info')

        with open(caminho_arquivo, 'r', encoding='utf-8-sig') as arquivo:
            reader = csv.DictReader(arquivo, delimiter=separador)

            for linha in reader:
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
                    emit_log(f"Linha ignorada por falta de dados obrigatórios", 'warning')

        emit_log(f"Total de colaboradores carregados: {len(colaboradores)}", 'success')
        return colaboradores

    except Exception as e:
        emit_log(f"Erro ao ler arquivo CSV: {e}", 'error')
        return []


async def processar_escalas_async(colaboradores: List[Dict[str, Any]], token: str, max_concurrent: int):
    """Processa escalas de forma assíncrona com feedback em tempo real"""
    base_url = "https://webp20.seniorcloud.com.br:31531/gestaoponto-backend/api"
    client = EscalaAPIClient(base_url, token)

    total = len(colaboradores)
    processados = 0
    sucessos = 0
    erros = 0
    resultados_finais = []

    emit_log(f"Iniciando processamento de {total} registros...", 'info')
    emit_log(f"Concorrência: {max_concurrent} requisições simultâneas", 'info')

    # Criar semáforo para controlar concorrência
    semaphore = asyncio.Semaphore(max_concurrent)

    # Criar sessão HTTP
    import aiohttp
    timeout = aiohttp.ClientTimeout(total=60, connect=10, sock_read=60)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        tasks = []

        for colab in colaboradores:
            task = client.enviar_programacao(session, colab, semaphore)
            tasks.append(task)

        # Processar em lote
        for i, task in enumerate(asyncio.as_completed(tasks)):
            try:
                resultado = await task
                processados += 1

                if resultado['status'] == 'sucesso':
                    sucessos += 1
                    emit_log(f"✓ {resultado['id_colaborador']} - {resultado['nome']} - Sucesso", 'success')
                else:
                    erros += 1
                    erro_msg = resultado.get('erro', resultado.get('response_text', 'Erro desconhecido'))
                    emit_log(f"✗ {resultado['id_colaborador']} - {resultado['nome']} - Erro: {erro_msg[:100]}", 'error')

                resultados_finais.append(resultado)
                emit_progress(processados, total, sucessos, erros)

            except Exception as e:
                processados += 1
                erros += 1
                emit_log(f"✗ Erro inesperado: {str(e)}", 'error')
                emit_progress(processados, total, sucessos, erros)

    return resultados_finais, sucessos, erros


@app.route('/')
def index():
    """Página principal"""
    return render_template('index.html')


@app.route('/api/upload', methods=['POST'])
def upload_file():
    """Endpoint para upload de arquivo CSV"""
    if 'file' not in request.files:
        return jsonify({'error': 'Nenhum arquivo enviado'}), 400

    file = request.files['file']

    if file.filename == '':
        return jsonify({'error': 'Nome de arquivo vazio'}), 400

    if not file.filename.endswith('.csv'):
        return jsonify({'error': 'Apenas arquivos CSV são permitidos'}), 400

    try:
        # Salvar arquivo
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"upload_{timestamp}_{filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)

        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        file.save(filepath)

        emit_log(f'Arquivo recebido: {file.filename}', 'info')

        # Detectar formato do arquivo
        formato = detectar_formato_csv(filepath)
        emit_log(f'Formato detectado: {formato.upper()}', 'info')

        # Se for formato Grid, converter para API
        arquivo_para_processar = filepath
        if formato == 'grid':
            # Validar se arquivo horarios.csv existe
            if not validar_arquivo_horarios():
                os.remove(filepath)
                return jsonify({
                    'error': 'Arquivo horarios.csv não encontrado. Este arquivo é necessário para converter formato GRID.',
                    'details': 'Certifique-se de que o arquivo horarios.csv está presente no diretório raiz da aplicação.'
                }), 400

            try:
                # Converter Grid -> API
                arquivo_para_processar = converter_grid_para_api(filepath)
            except Exception as conv_error:
                os.remove(filepath)
                return jsonify({
                    'error': f'Erro ao converter formato GRID: {str(conv_error)}',
                    'details': 'Verifique se o arquivo horarios.csv está configurado corretamente.'
                }), 400

        # Ler e validar arquivo (já no formato API)
        colaboradores = ler_csv_colaboradores_web(arquivo_para_processar)

        if not colaboradores:
            os.remove(filepath)
            if formato == 'grid' and arquivo_para_processar != filepath:
                os.remove(arquivo_para_processar)
            return jsonify({'error': 'Arquivo CSV vazio ou inválido'}), 400

        # Armazenar arquivo processado (pode ser o original ou o convertido)
        app_state['current_file'] = arquivo_para_processar

        return jsonify({
            'success': True,
            'filename': os.path.basename(arquivo_para_processar),
            'original_filename': file.filename,
            'format': formato,
            'converted': formato == 'grid',
            'total_records': len(colaboradores),
            'message': f'{len(colaboradores)} registros carregados com sucesso'
        })

    except Exception as e:
        return jsonify({'error': f'Erro ao processar arquivo: {str(e)}'}), 500


@app.route('/api/authenticate', methods=['POST'])
def authenticate():
    """Endpoint para autenticação (usa credenciais do .env)"""
    try:
        username = os.getenv('SENIOR_USERNAME')
        password = os.getenv('SENIOR_PASSWORD')

        if not username or not password:
            return jsonify({'error': 'Credenciais não configuradas no arquivo .env'}), 500

        emit_log('Autenticando na plataforma Senior...', 'info')

        # Autenticar usando módulo existente
        result = authenticate_complete(username, password)

        if result and 'gestaoponto_token' in result:
            app_state['token'] = result['gestaoponto_token']
            app_state['authenticated'] = True
            emit_log('Autenticação realizada com sucesso!', 'success')
            return jsonify({
                'success': True,
                'message': 'Autenticado com sucesso'
            })
        else:
            emit_log('Falha na autenticação', 'error')
            return jsonify({'error': 'Falha na autenticação'}), 401

    except Exception as e:
        emit_log(f'Erro na autenticação: {str(e)}', 'error')
        return jsonify({'error': f'Erro na autenticação: {str(e)}'}), 500


@app.route('/api/process', methods=['POST'])
def process():
    """Endpoint para iniciar processamento"""
    if app_state['processing']:
        return jsonify({'error': 'Já existe um processamento em andamento'}), 409

    if not app_state['current_file']:
        return jsonify({'error': 'Nenhum arquivo carregado'}), 400

    if not app_state['authenticated']:
        return jsonify({'error': 'Não autenticado. Execute a autenticação primeiro.'}), 401

    try:
        data = request.json
        max_concurrent = data.get('max_concurrent', 5)

        if not 1 <= max_concurrent <= 50:
            return jsonify({'error': 'Concorrência deve estar entre 1 e 50'}), 400

        # Iniciar processamento em thread separada
        def run_processing():
            app_state['processing'] = True
            try:
                # Ler colaboradores
                colaboradores = ler_csv_colaboradores_web(app_state['current_file'])

                if not colaboradores:
                    emit_log('Nenhum colaborador para processar', 'error')
                    return

                # Executar processamento assíncrono
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                start_time = datetime.now()
                resultados, sucessos, erros = loop.run_until_complete(
                    processar_escalas_async(colaboradores, app_state['token'], max_concurrent)
                )
                loop.close()

                end_time = datetime.now()
                tempo_total = (end_time - start_time).total_seconds()

                # Salvar resultados
                results_file = salvar_resultados_csv(resultados)
                app_state['results_file'] = results_file

                # Emitir resumo final
                emit_log('=' * 60, 'info')
                emit_log('PROCESSAMENTO CONCLUÍDO', 'success')
                emit_log('=' * 60, 'info')
                emit_log(f'Total de registros: {len(resultados)}', 'info')
                emit_log(f'Sucessos: {sucessos}', 'success')
                emit_log(f'Erros: {erros}', 'error' if erros > 0 else 'info')
                emit_log(f'Tempo total: {tempo_total:.2f} segundos', 'info')
                emit_log(f'Velocidade média: {len(resultados)/tempo_total:.2f} req/seg', 'info')

                # Enviar resultados detalhados
                sucessos_list, erros_list = separar_sucessos_e_erros(resultados)

                socketio.emit('processing_complete', {
                    'success': True,
                    'total': len(resultados),
                    'successes': sucessos,
                    'errors': erros,
                    'tempo_total': tempo_total,
                    'results_file': os.path.basename(results_file) if results_file else None,
                    'error_details': erros_list[:100]  # Limitar a 100 erros
                })

            except Exception as e:
                emit_log(f'Erro durante processamento: {str(e)}', 'error')
                socketio.emit('processing_complete', {
                    'success': False,
                    'error': str(e)
                })
            finally:
                app_state['processing'] = False

        # Executar em thread separada
        import threading
        thread = threading.Thread(target=run_processing)
        thread.daemon = True
        thread.start()

        return jsonify({'success': True, 'message': 'Processamento iniciado'})

    except Exception as e:
        return jsonify({'error': f'Erro ao iniciar processamento: {str(e)}'}), 500


@app.route('/api/retry', methods=['POST'])
def retry_errors():
    """Endpoint para reenviar erros"""
    if app_state['processing']:
        return jsonify({'error': 'Já existe um processamento em andamento'}), 409

    if not app_state['results_file'] or not os.path.exists(app_state['results_file']):
        return jsonify({'error': 'Nenhum resultado anterior encontrado'}), 400

    try:
        data = request.json
        max_concurrent = data.get('max_concurrent', 5)

        # Ler arquivo de resultados e filtrar apenas erros
        erros = []
        with open(app_state['results_file'], 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['status'] != 'sucesso':
                    erros.append({
                        'id_colaborador': row['id_colaborador'],
                        'nome': row['nome'],
                        'data': row['data'],
                        'codigo_horario': row['codigo_horario'],
                        'numero_cadastro': row.get('numero_cadastro', ''),
                        'numero_empresa': row.get('numero_empresa', ''),
                        'tipo_colaborador': row.get('tipo_colaborador', '1')
                    })

        if not erros:
            return jsonify({'error': 'Não há erros para reenviar'}), 400

        emit_log(f'Reenviando {len(erros)} registros com erro...', 'info')

        # Iniciar reprocessamento
        def run_retry():
            app_state['processing'] = True
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                start_time = datetime.now()
                resultados, sucessos, erros_count = loop.run_until_complete(
                    processar_escalas_async(erros, app_state['token'], max_concurrent)
                )
                loop.close()

                end_time = datetime.now()
                tempo_total = (end_time - start_time).total_seconds()

                # Atualizar arquivo de resultados
                # Ler todos os resultados antigos
                todos_resultados = []
                with open(app_state['results_file'], 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        if row['status'] == 'sucesso':
                            todos_resultados.append(row)

                # Adicionar novos resultados
                for resultado in resultados:
                    resultado['numero_retry'] = 1
                    todos_resultados.append(resultado)

                # Salvar arquivo atualizado
                salvar_resultados_csv(todos_resultados, caminho_existente=app_state['results_file'])

                emit_log('=' * 60, 'info')
                emit_log('RETRY CONCLUÍDO', 'success')
                emit_log('=' * 60, 'info')
                emit_log(f'Reprocessados: {len(resultados)}', 'info')
                emit_log(f'Novos sucessos: {sucessos}', 'success')
                emit_log(f'Ainda com erro: {erros_count}', 'error' if erros_count > 0 else 'info')

                sucessos_list, erros_list = separar_sucessos_e_erros(resultados)

                socketio.emit('processing_complete', {
                    'success': True,
                    'total': len(resultados),
                    'successes': sucessos,
                    'errors': erros_count,
                    'tempo_total': tempo_total,
                    'results_file': os.path.basename(app_state['results_file']),
                    'error_details': erros_list[:100]
                })

            except Exception as e:
                emit_log(f'Erro durante retry: {str(e)}', 'error')
                socketio.emit('processing_complete', {
                    'success': False,
                    'error': str(e)
                })
            finally:
                app_state['processing'] = False

        import threading
        thread = threading.Thread(target=run_retry)
        thread.daemon = True
        thread.start()

        return jsonify({'success': True, 'message': 'Retry iniciado'})

    except Exception as e:
        return jsonify({'error': f'Erro ao iniciar retry: {str(e)}'}), 500


@app.route('/api/download/<filename>')
def download_file(filename):
    """Endpoint para download de arquivos de resultado"""
    try:
        return send_from_directory('output_data', filename, as_attachment=True)
    except Exception as e:
        return jsonify({'error': f'Arquivo não encontrado: {str(e)}'}), 404


@app.route('/api/status')
def get_status():
    """Retorna status atual da aplicação"""
    return jsonify({
        'processing': app_state['processing'],
        'authenticated': app_state['authenticated'],
        'current_file': os.path.basename(app_state['current_file']) if app_state['current_file'] else None,
        'results_file': os.path.basename(app_state['results_file']) if app_state['results_file'] else None
    })


@app.route('/api/validate-config')
def validate_config():
    """
    Valida configuração do sistema: verifica arquivos necessários.

    Returns:
        JSON com status de validação
    """
    resultado = {
        'valid': True,
        'warnings': [],
        'errors': []
    }

    # Verificar arquivo horarios.csv
    if not validar_arquivo_horarios():
        resultado['warnings'].append({
            'type': 'missing_horarios',
            'message': 'Arquivo horarios.csv não encontrado',
            'details': 'Este arquivo é necessário para processar arquivos em formato GRID (calendário). Arquivos em formato API não precisam deste arquivo.'
        })

    # Verificar credenciais do .env
    username = os.getenv('SENIOR_USERNAME')
    password = os.getenv('SENIOR_PASSWORD')

    if not username or not password:
        resultado['valid'] = False
        resultado['errors'].append({
            'type': 'missing_credentials',
            'message': 'Credenciais não configuradas',
            'details': 'Configure SENIOR_USERNAME e SENIOR_PASSWORD no arquivo .env'
        })

    # Verificar diretórios necessários
    for diretorio in ['input_data', 'output_data']:
        if not os.path.exists(diretorio):
            try:
                os.makedirs(diretorio, exist_ok=True)
                resultado['warnings'].append({
                    'type': 'created_directory',
                    'message': f'Diretório {diretorio}/ criado automaticamente'
                })
            except Exception as e:
                resultado['errors'].append({
                    'type': 'directory_error',
                    'message': f'Erro ao criar diretório {diretorio}/',
                    'details': str(e)
                })
                resultado['valid'] = False

    return jsonify(resultado)


@socketio.on('connect')
def handle_connect():
    """Handler para conexão WebSocket"""
    emit_log('Conectado ao servidor', 'success')


@socketio.on('disconnect')
def handle_disconnect():
    """Handler para desconexão WebSocket"""
    print('Cliente desconectado')


if __name__ == '__main__':
    # Criar diretórios necessários
    os.makedirs('input_data', exist_ok=True)
    os.makedirs('output_data', exist_ok=True)
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static/css', exist_ok=True)
    os.makedirs('static/js', exist_ok=True)

    print("=" * 60)
    print("  SISTEMA DE ENVIO DE ESCALAS - INTERFACE WEB")
    print("  MODO DESENVOLVIMENTO")
    print("=" * 60)
    print("  Acesse: http://localhost:3000")
    print("=" * 60)
    print()
    print("  Para produção, use:")
    print("  gunicorn --worker-class eventlet -w 1 app:app --bind 0.0.0.0:3000")
    print("=" * 60)

    # Iniciar servidor de desenvolvimento
    # ATENÇÃO: Apenas para desenvolvimento local
    # Em produção, use Gunicorn (ver comando acima)
    socketio.run(app, host='0.0.0.0', port=3000, debug=True, allow_unsafe_werkzeug=True)
