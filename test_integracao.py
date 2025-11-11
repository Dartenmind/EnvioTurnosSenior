#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Script de teste para validar a integração do módulo de conversão
com o envio de escalas.
"""

import os
import sys

# Importar módulos
import envio_escala_api_corrigido as api_client
import data_convert

def test_deteccao_formato():
    """Testa a detecção de formato dos arquivos"""
    print("=" * 70)
    print("TESTE 1: DETECCAO DE FORMATO")
    print("=" * 70)

    arquivos_teste = [
        ('input_data/dados.csv', 'grid'),
        ('input_data/dados_converted.csv', 'api'),
        ('input_data/alteracoes_08_10.csv', 'api'),
    ]

    todos_corretos = True
    for arquivo, formato_esperado in arquivos_teste:
        if os.path.exists(arquivo):
            formato_detectado = api_client.detectar_formato_csv(arquivo)
            status = "[OK]" if formato_detectado == formato_esperado else "[ERRO]"
            print(f"{status} {arquivo}")
            print(f"     Esperado: {formato_esperado} | Detectado: {formato_detectado}")

            if formato_detectado != formato_esperado:
                todos_corretos = False
        else:
            print(f"[AVISO] Arquivo não encontrado: {arquivo}")

    print()
    if todos_corretos:
        print("[OK] Todos os formatos foram detectados corretamente!")
    else:
        print("[ERRO] Alguns formatos não foram detectados corretamente")

    return todos_corretos


def test_conversao_arquivo():
    """Testa a conversão de arquivo"""
    print("\n" + "=" * 70)
    print("TESTE 2: CONVERSAO DE ARQUIVO")
    print("=" * 70)

    arquivo_teste = 'input_data/dados.csv'

    if not os.path.exists(arquivo_teste):
        print(f"[ERRO] Arquivo de teste não encontrado: {arquivo_teste}")
        return False

    # Testar conversão
    print(f"\nConvertendo: {arquivo_teste}")
    arquivo_convertido = api_client.processar_conversao(arquivo_teste)

    if arquivo_convertido and os.path.exists(arquivo_convertido):
        print(f"\n[OK] Arquivo convertido com sucesso: {arquivo_convertido}")

        # Verificar formato do arquivo convertido
        formato = api_client.detectar_formato_csv(arquivo_convertido)
        if formato == 'api':
            print("[OK] Formato do arquivo convertido está correto (api)")
            return True
        else:
            print(f"[ERRO] Formato do arquivo convertido está incorreto: {formato}")
            return False
    else:
        print("[ERRO] Conversão falhou")
        return False


def test_leitura_arquivo_convertido():
    """Testa a leitura do arquivo convertido"""
    print("\n" + "=" * 70)
    print("TESTE 3: LEITURA DO ARQUIVO CONVERTIDO")
    print("=" * 70)

    arquivo_convertido = 'input_data/dados_converted.csv'

    if not os.path.exists(arquivo_convertido):
        print(f"[ERRO] Arquivo convertido não encontrado: {arquivo_convertido}")
        return False

    try:
        # Tentar ler o arquivo usando a função do api_client
        colaboradores = api_client.ler_csv_colaboradores(arquivo_convertido)

        if colaboradores:
            print(f"[OK] Arquivo lido com sucesso!")
            print(f"     Total de colaboradores: {len(colaboradores)}")

            # Mostrar alguns exemplos
            print("\n     Primeiros 3 registros:")
            for i, col in enumerate(colaboradores[:3], 1):
                print(f"     {i}. {col.get('nome', 'N/A')} - {col.get('data', 'N/A')} - Código: {col.get('codigo_horario', 'N/A')}")

            return True
        else:
            print("[ERRO] Nenhum colaborador encontrado no arquivo")
            return False

    except Exception as e:
        print(f"[ERRO] Erro ao ler arquivo: {e}")
        return False


def main():
    """Função principal de teste"""
    print("\n")
    print("=" * 70)
    print(" " * 15 + "TESTE DE INTEGRACAO - CONVERSAO + ENVIO")
    print("=" * 70)
    print()

    resultados = []

    # Teste 1: Detecção de formato
    resultados.append(("Detecção de formato", test_deteccao_formato()))

    # Teste 2: Conversão de arquivo
    resultados.append(("Conversão de arquivo", test_conversao_arquivo()))

    # Teste 3: Leitura do arquivo convertido
    resultados.append(("Leitura do arquivo", test_leitura_arquivo_convertido()))

    # Resumo
    print("\n" + "=" * 70)
    print("RESUMO DOS TESTES")
    print("=" * 70)

    for nome, sucesso in resultados:
        status = "[OK]" if sucesso else "[ERRO]"
        print(f"{status} {nome}")

    total_sucesso = sum(1 for _, sucesso in resultados if sucesso)
    total_testes = len(resultados)

    print("\n" + "=" * 70)
    print(f"Total: {total_sucesso}/{total_testes} testes passaram")
    print("=" * 70)

    if total_sucesso == total_testes:
        print("\n[OK] TODOS OS TESTES PASSARAM!")
        print("\nA integracao esta funcionando corretamente.")
        print("O sistema pode:")
        print("  1. Detectar automaticamente o formato do arquivo")
        print("  2. Converter arquivos no formato grid")
        print("  3. Usar o arquivo convertido para envio")
        return 0
    else:
        print("\n[ERRO] ALGUNS TESTES FALHARAM")
        return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"\n[ERRO] Erro durante execução dos testes: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
