"""
csv_import.py — Leitor do extrato em CSV do PicPay.

O CSV já vem com colunas separadas de verdade (sem o problema de
quebra de linha do PDF), então é o formato mais confiável quando o
PicPay disponibilizar os dois. Colunas esperadas (cabeçalho):

    data,hora,tipo,"origem / destino",valor,"forma de pagamento"

- data já vem em YYYY-MM-DD (não precisa converter)
- valor vem como texto: "−R$ 89,06" (saída) ou "+R$ 200,00" (entrada)
- o arquivo tem BOM UTF-8 (por isso o encoding "utf-8-sig" abaixo)
"""

import os
import csv

import db
import extrato_utils as eu


def _ler_linhas(caminho_csv):
    with open(caminho_csv, "r", encoding="utf-8-sig", newline="") as f:
        leitor = csv.DictReader(f)
        # normaliza nomes de coluna (minúsculas, sem espaço nas pontas)
        # pra aguentar pequenas variações do PicPay ao longo do tempo
        linhas = []
        for linha in leitor:
            linha_norm = {(k or "").strip().lower(): v for k, v in linha.items()}
            linhas.append(linha_norm)
        return linhas


def extrair_transacoes(caminho_csv):
    transacoes = []
    for linha in _ler_linhas(caminho_csv):
        data = (linha.get("data") or "").strip()
        hora = (linha.get("hora") or "").strip()
        tipo_transacao = (linha.get("tipo") or "").strip()
        origem_destino = (linha.get("origem / destino") or "").strip()
        valor_texto = (linha.get("valor") or "").strip()

        if not data or not valor_texto:
            continue

        transacoes.append({
            "data": data,
            "hora": hora,
            "tipo_transacao_original": tipo_transacao,
            "origem_destino": origem_destino,
            "descricao": f"{tipo_transacao} — {origem_destino}".strip(" —"),
            "valor_com_sinal": eu.extrair_valor_com_sinal(valor_texto),
        })
    return transacoes


def _processar(transacoes_brutas):
    categorias = eu.carregar_categorias()
    config = eu.carregar_configuracao()
    meu_nome = config.get("meu_nome") or ""

    resultado = []
    for t in transacoes_brutas:
        tipo, categoria = eu.classificar_transacao(
            t["tipo_transacao_original"], t["origem_destino"], meu_nome
        )
        if tipo is None:
            tipo = "despesa" if t["valor_com_sinal"] < 0 else "receita"
            categoria = eu.categorizar(t["descricao"], categorias)

        resultado.append({
            "data": t["data"],
            "hora": t["hora"],
            "descricao": t["descricao"],
            "categoria": categoria,
            "valor": abs(t["valor_com_sinal"]),
            "tipo": tipo,
        })
    return resultado


def importar_csv(caminho_csv):
    nome_arquivo = os.path.basename(caminho_csv)

    transacoes_brutas = extrair_transacoes(caminho_csv)

    if not transacoes_brutas:
        return {
            "status": "vazio",
            "mensagem": "Não consegui ler transações desse CSV. O formato de colunas pode ter mudado.",
        }

    transacoes = _processar(transacoes_brutas)
    return {"status": "preview", "transacoes": transacoes, "origem": nome_arquivo}


def confirmar_importacao(transacoes, origem):
    """Insere as transações, pulando individualmente qualquer uma que já
    exista no banco (mesma data+hora+valor+tipo) — assim um extrato de
    180 dias não duplica os 30 dias que já tinham vindo de um PDF antes."""
    inseridas = 0
    ignoradas = 0
    for t in transacoes:
        if db.transacao_ja_existe(t["data"], t.get("hora", ""), t["valor"], t["tipo"]):
            ignoradas += 1
            continue
        db.adicionar_gasto(
            t["data"], t["descricao"], t["categoria"], t["valor"], t["tipo"],
            origem, t.get("hora", "")
        )
        inseridas += 1
    return inseridas, ignoradas
