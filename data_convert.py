#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Módulo de conversão de dados do formato grid (dados.csv) para formato da API Senior.

Converte arquivo no formato:
    NOME;MAT;COD. ESCALA;01/10/2025;02/10/2025;...

Para o formato:
    id_colaborador;nome;data;codigo_horario
    303-1-16774;ANTONIO DA SILVA;01/10/2025;1234

Regras de conversao:
- Celulas vazias, FE, TR -> Buscar codigo via COD.ESCALA no horarios.csv
- FR -> Codigo fixo 9999
- ** -> Ignorar (nao gerar registro)
- Formato hhmm-hhmm (ex: 0800-1600) -> Converter para hh:mmhh:mm e buscar no horarios.csv
  Se nao encontrado, usar codigo base do colaborador (fallback)
"""

import csv
import os
import re
import pandas as pd
from datetime import datetime
from typing import Dict, List, Tuple, Optional

# Cache global para o DataFrame de horários
_horarios_cache = None


def parse_date_flexible(date_str, verbose=False):
    """
    Parser flexível de datas que tenta diferentes formatos automaticamente.
    Adaptado do data_normalizer.py do projeto ENVIO_TURNOS_SRP V2.

    Args:
        date_str: String com a data a ser parseada
        verbose: Se True, imprime mensagens de debug

    Returns:
        datetime.date object ou None se não conseguir parsear
    """
    if not date_str or pd.isna(date_str):
        return None

    # Limpar string
    date_str = str(date_str).strip().replace("'", "")

    # Remover possível dia da semana (formato: '03/09/25 Qua')
    date_str = date_str.split(' ')[0]

    # Lista de formatos para tentar
    date_formats = [
        '%d/%m/%Y',    # 01/10/2025
        '%d/%m/%y',    # 01/10/25
        '%Y-%m-%d',    # 2025-10-01
        '%d-%m-%Y',    # 01-10-2025
        '%d-%m-%y',    # 01-10-25
    ]

    # Tentar cada formato
    for date_format in date_formats:
        try:
            parsed_date = datetime.strptime(date_str, date_format)
            if verbose:
                print(f"  Data '{date_str}' parseada com formato '{date_format}'")
            return parsed_date.date()
        except ValueError:
            continue

    # Se nenhum formato funcionou
    if verbose:
        print(f"  ERRO: Não foi possível parsear data '{date_str}'")

    return None


def load_horarios_mapping(horarios_path='horarios.csv'):
    """
    Carrega o arquivo horarios.csv e cria um dicionário de mapeamento.
    Usa cache para evitar recarregar o arquivo.

    Args:
        horarios_path: Caminho para o arquivo horarios.csv

    Returns:
        DataFrame do pandas com os horários ou None em caso de erro
    """
    global _horarios_cache

    # Retornar cache se já carregado
    if _horarios_cache is not None:
        return _horarios_cache

    if not os.path.exists(horarios_path):
        print(f"ERRO: Arquivo {horarios_path} não encontrado!")
        return None

    try:
        # Carregar CSV com encoding UTF-8-sig para remover BOM
        df_horarios = pd.read_csv(horarios_path, sep=';', encoding='utf-8-sig')

        # Verificar se as colunas necessárias existem
        required_cols = ['CÓDIGO HORÁRIO', 'ID SCRIPT']
        missing_cols = [col for col in required_cols if col not in df_horarios.columns]

        if missing_cols:
            print(f"ERRO: Colunas não encontradas em {horarios_path}: {missing_cols}")
            print(f"Colunas disponíveis: {list(df_horarios.columns)}")
            return None

        # Limpar espaços e converter códigos para inteiros (remover .0)
        # Converter CÓDIGO HORÁRIO para int primeiro para remover decimais, depois para string
        df_horarios['CÓDIGO HORÁRIO'] = pd.to_numeric(df_horarios['CÓDIGO HORÁRIO'], errors='coerce').fillna(0).astype(int).astype(str)
        df_horarios['ID SCRIPT'] = df_horarios['ID SCRIPT'].astype(str).str.strip()

        # Cachear resultado
        _horarios_cache = df_horarios

        print(f"Arquivo horarios.csv carregado: {len(df_horarios)} horários")
        return df_horarios

    except Exception as e:
        print(f"ERRO ao carregar {horarios_path}: {e}")
        return None


def find_codigo_horario(cod_escala, horarios_df):
    """
    Busca o código de horário correspondente ao COD. ESCALA.

    Args:
        cod_escala: Código de escala do colaborador (ex: "08:0016:00")
        horarios_df: DataFrame com os horários

    Returns:
        String com o código de horário ou None se não encontrado
    """
    if horarios_df is None or cod_escala is None:
        return None

    # Limpar e padronizar o código de escala
    cod_escala = str(cod_escala).strip()

    # Buscar no DataFrame
    try:
        # Filtrar linhas onde ID SCRIPT == cod_escala
        matches = horarios_df[horarios_df['ID SCRIPT'] == cod_escala]

        if len(matches) > 0:
            # Retornar o primeiro código encontrado
            codigo = str(matches.iloc[0]['CÓDIGO HORÁRIO']).strip()
            return codigo
        else:
            # Não encontrado
            return None

    except Exception as e:
        print(f"ERRO ao buscar código para escala '{cod_escala}': {e}")
        return None


def converter_formato_horario(cell_value):
    """
    Detecta e converte horário no formato hhmm-hhmm para hh:mmhh:mm.

    Args:
        cell_value: Valor da célula (ex: "0800-1600")

    Returns:
        String no formato hh:mmhh:mm (ex: "08:0016:00") ou None se não corresponder ao padrão

    Exemplos:
        "0800-1600" -> "08:0016:00"
        "1400-2000" -> "14:0020:00"
        "2200-0400" -> "22:0004:00"
    """
    if not cell_value:
        return None

    # Padrão regex: 4 dígitos, hífen, 4 dígitos
    pattern = re.compile(r'^(\d{4})-(\d{4})$')
    match = pattern.match(cell_value)

    if match:
        hora_inicio = match.group(1)  # ex: "0800"
        hora_fim = match.group(2)      # ex: "1600"

        # Formatar para hh:mmhh:mm
        # hora_inicio[0:2] = "08", hora_inicio[2:4] = "00"
        # hora_fim[0:2] = "16", hora_fim[2:4] = "00"
        formato_convertido = f"{hora_inicio[0:2]}:{hora_inicio[2:4]}{hora_fim[0:2]}:{hora_fim[2:4]}"

        return formato_convertido

    return None


def convert_dados_to_senior(input_path='input_data/dados.csv',
                             output_path='input_data/dados_converted.csv',
                             horarios_path='horarios.csv'):
    """
    Converte o arquivo dados.csv do formato grid para o formato da API Senior.

    Args:
        input_path: Caminho do arquivo de entrada (dados.csv)
        output_path: Caminho do arquivo de saída
        horarios_path: Caminho do arquivo horarios.csv

    Returns:
        Tuple (sucesso: bool, total_registros: int, mensagem: str)
    """
    print("=" * 70)
    print("CONVERSAO DE DADOS - FORMATO GRID -> API SENIOR")
    print("=" * 70)
    print(f"Arquivo de entrada: {input_path}")
    print(f"Arquivo de saída: {output_path}")
    print(f"Arquivo de horários: {horarios_path}")
    print()

    # Verificar se arquivo de entrada existe
    if not os.path.exists(input_path):
        msg = f"ERRO: Arquivo de entrada não encontrado: {input_path}"
        print(msg)
        return False, 0, msg

    # Carregar horários
    horarios_df = load_horarios_mapping(horarios_path)
    if horarios_df is None:
        msg = "ERRO: Não foi possível carregar o arquivo de horários"
        print(msg)
        return False, 0, msg

    print()
    print("REGRAS DE CONVERSAO:")
    print("  - Celula vazia -> Buscar codigo via COD.ESCALA")
    print("  - FE (ferias) -> Buscar codigo via COD.ESCALA")
    print("  - TR (treinamento) -> Buscar codigo via COD.ESCALA")
    print("  - FR (folga) -> Codigo fixo 9999")
    print("  - hhmm-hhmm (ex: 0800-1600) -> Converter e buscar codigo (fallback se nao encontrado)")
    print("  - ** -> Ignorar (nao gerar registro)")
    print()
    print("-" * 70)

    try:
        converted_rows = []
        warnings = []
        stats = {
            'total_colaboradores': 0,
            'total_registros': 0,
            'vazio_busca': 0,
            'fe_busca': 0,
            'tr_busca': 0,
            'fr_9999': 0,
            'asterisco_ignorado': 0,
            'formato_convertido': 0,
            'formato_convertido_fallback': 0,
            'codigo_nao_encontrado': 0
        }

        with open(input_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.reader(f, delimiter=';')

            # Ler cabeçalho
            header = next(reader)
            print(f"Cabeçalho: {len(header)} colunas")

            # Verificar formato esperado
            if len(header) < 4:
                msg = "ERRO: Formato inválido - menos de 4 colunas no cabeçalho"
                print(msg)
                return False, 0, msg

            # Extrair colunas de datas (a partir da 4ª coluna, índice 3)
            date_columns = []
            for i, col in enumerate(header[3:], start=3):
                col_clean = col.strip()
                parsed_date = parse_date_flexible(col_clean)
                if parsed_date:
                    date_columns.append((i, col_clean, parsed_date))
                else:
                    print(f"AVISO: Coluna '{col_clean}' não foi reconhecida como data")

            print(f"Datas encontradas: {len(date_columns)} colunas")
            if date_columns:
                print(f"Período: {date_columns[0][1]} até {date_columns[-1][1]}")
            print()

            # Processar cada linha de colaborador
            for row_num, row in enumerate(reader, start=2):
                if len(row) < 3:
                    print(f"AVISO: Linha {row_num} ignorada - dados insuficientes")
                    continue

                nome = row[0].strip()
                mat = row[1].strip()
                cod_escala = row[2].strip()

                if not nome or not mat:
                    print(f"AVISO: Linha {row_num} ignorada - nome ou matrícula vazia")
                    continue

                stats['total_colaboradores'] += 1
                print(f"Processando: {nome} (MAT: {mat}, COD.ESCALA: {cod_escala})")

                # Buscar código de horário base do colaborador
                codigo_base = find_codigo_horario(cod_escala, horarios_df)
                if codigo_base is None:
                    warning_msg = f"  AVISO: Código de horário não encontrado para COD.ESCALA '{cod_escala}'"
                    print(warning_msg)
                    warnings.append(warning_msg)
                    # Continuar processamento mesmo sem código base

                # Processar cada dia (colunas de data)
                registros_colaborador = 0
                for col_index, date_str, date_obj in date_columns:
                    if col_index < len(row):
                        cell_value = row[col_index].strip().upper()
                    else:
                        cell_value = ""  # Célula vazia se não existe

                    # Aplicar regras de conversão
                    codigo_horario = None
                    skip_registro = False
                    tipo_registro = None

                    if '**' in cell_value or cell_value == '**':
                        # Ignorar registros com **
                        skip_registro = True
                        stats['asterisco_ignorado'] += 1
                        tipo_registro = "ignorado (**)"

                    elif cell_value == 'FR':
                        # Folga - codigo fixo 9999
                        codigo_horario = '9999'
                        stats['fr_9999'] += 1
                        tipo_registro = "FR -> 9999"

                    elif converter_formato_horario(cell_value):
                        # Detectado formato hhmm-hhmm - converter para hh:mmhh:mm
                        formato_convertido = converter_formato_horario(cell_value)
                        print(f"    INFO: Horário '{cell_value}' detectado - convertendo para '{formato_convertido}'")

                        # Buscar código com formato convertido
                        codigo_horario = find_codigo_horario(formato_convertido, horarios_df)

                        if codigo_horario:
                            stats['formato_convertido'] += 1
                            tipo_registro = f"{cell_value} -> {formato_convertido} -> {codigo_horario}"
                            print(f"    OK: Código {codigo_horario} encontrado para '{cell_value}'")
                        else:
                            # Se não encontrar, usar código base (fallback)
                            if codigo_base:
                                stats['formato_convertido_fallback'] += 1
                                codigo_horario = codigo_base
                                tipo_registro = f"{cell_value} -> {formato_convertido} (não encontrado) -> {codigo_base} (fallback)"
                                print(f"    AVISO: Código não encontrado para '{formato_convertido}', usando código base {codigo_base}")
                            else:
                                skip_registro = True
                                stats['codigo_nao_encontrado'] += 1
                                tipo_registro = f"código não encontrado para '{cell_value}' ('{formato_convertido}')"
                                print(f"    ERRO: Código não encontrado e sem código base")

                    elif cell_value == '' or cell_value == 'FE' or cell_value == 'TR':
                        # Vazio, Ferias ou Treinamento - buscar codigo
                        if codigo_base:
                            codigo_horario = codigo_base
                            if cell_value == '':
                                stats['vazio_busca'] += 1
                                tipo_registro = f"vazio -> {codigo_base}"
                            elif cell_value == 'FE':
                                stats['fe_busca'] += 1
                                tipo_registro = f"FE -> {codigo_base}"
                            elif cell_value == 'TR':
                                stats['tr_busca'] += 1
                                tipo_registro = f"TR -> {codigo_base}"
                        else:
                            # Código base não encontrado
                            skip_registro = True
                            stats['codigo_nao_encontrado'] += 1
                            tipo_registro = f"código não encontrado para '{cell_value}'"

                    else:
                        # Valor desconhecido - buscar codigo
                        if codigo_base:
                            codigo_horario = codigo_base
                            tipo_registro = f"'{cell_value}' -> {codigo_base}"
                            print(f"    INFO: Valor '{cell_value}' em {date_str} tratado como trabalho")
                        else:
                            skip_registro = True
                            stats['codigo_nao_encontrado'] += 1
                            tipo_registro = f"código não encontrado para '{cell_value}'"

                    # Gerar registro se não for para pular
                    if not skip_registro and codigo_horario:
                        id_colaborador = f"303-1-{mat}"
                        converted_rows.append({
                            'id_colaborador': id_colaborador,
                            'nome': nome,
                            'data': date_str,
                            'codigo_horario': codigo_horario
                        })
                        registros_colaborador += 1
                        stats['total_registros'] += 1

                print(f"  -> {registros_colaborador} registros gerados")
                print()

        # Criar diretório de saída se não existir
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)

        # Salvar arquivo convertido
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            fieldnames = ['id_colaborador', 'nome', 'data', 'codigo_horario']
            writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=';')
            writer.writeheader()
            writer.writerows(converted_rows)

        # Exibir estatísticas
        print("=" * 70)
        print("CONVERSÃO CONCLUÍDA COM SUCESSO!")
        print("=" * 70)
        print(f"Total de colaboradores processados: {stats['total_colaboradores']}")
        print(f"Total de registros gerados: {stats['total_registros']}")
        print()
        print("DETALHAMENTO:")
        print(f"  - Células vazias (busca código): {stats['vazio_busca']}")
        print(f"  - FE - Férias (busca código): {stats['fe_busca']}")
        print(f"  - TR - Treinamento (busca código): {stats['tr_busca']}")
        print(f"  - FR - Folga (código 9999): {stats['fr_9999']}")
        print(f"  - Horários convertidos (hhmm-hhmm): {stats['formato_convertido']}")
        print(f"  - Horários convertidos (fallback): {stats['formato_convertido_fallback']}")
        print(f"  - ** - Ignorados: {stats['asterisco_ignorado']}")
        print(f"  - Código não encontrado: {stats['codigo_nao_encontrado']}")
        print()
        print(f"Arquivo salvo em: {output_path}")
        print("=" * 70)

        if warnings:
            print()
            print("AVISOS:")
            for warning in warnings[:10]:  # Mostrar apenas primeiros 10
                print(f"  {warning}")
            if len(warnings) > 10:
                print(f"  ... e mais {len(warnings) - 10} avisos")

        return True, stats['total_registros'], "Conversão concluída com sucesso"

    except Exception as e:
        msg = f"ERRO durante a conversão: {e}"
        print(msg)
        import traceback
        traceback.print_exc()
        return False, 0, msg


def main():
    """
    Função principal para execução standalone do módulo.
    """
    print()
    print("=" * 70)
    print(" " * 15 + "CONVERSOR DE DADOS - API SENIOR")
    print("=" * 70)
    print()

    # Configurar caminhos
    input_path = 'input_data/dados.csv'
    output_path = 'input_data/dados_converted.csv'
    horarios_path = 'horarios.csv'

    # Verificar se usuário quer customizar caminhos
    print("Caminhos padrão:")
    print(f"  Entrada: {input_path}")
    print(f"  Saída: {output_path}")
    print(f"  Horários: {horarios_path}")
    print()

    customizar = input("Deseja customizar os caminhos? (s/n): ").strip().lower()
    if customizar in ['s', 'sim', 'y', 'yes']:
        input_path = input(f"Caminho do arquivo de entrada [{input_path}]: ").strip() or input_path
        output_path = input(f"Caminho do arquivo de saída [{output_path}]: ").strip() or output_path
        horarios_path = input(f"Caminho do arquivo de horários [{horarios_path}]: ").strip() or horarios_path

    print()

    # Executar conversão
    sucesso, total, mensagem = convert_dados_to_senior(input_path, output_path, horarios_path)

    if sucesso:
        print()
        print("[OK] Processamento finalizado com sucesso!")
        print(f"     {total} registros convertidos")
    else:
        print()
        print("[ERRO] Processamento finalizado com erros")
        print(f"       {mensagem}")


if __name__ == "__main__":
    main()
