"""
extrato_utils.py — Funções compartilhadas entre pdf_import.py e csv_import.py.

Aqui mora a lógica de:
- normalizar texto (remover acentos, minúsculas) pra comparar com segurança
- converter "−R$ 89,06" / "+R$ 200,00" em número com sinal
- categorizar uma transação por palavra-chave (via categorias.json)
- reconhecer movimentações internas (cofrinho, transferência pra si mesmo)
  que não devem contar como gasto ou ganho real
"""

import os
import re
import json
import unicodedata

PASTA_APP = os.path.dirname(os.path.abspath(__file__))
CATEGORIAS_PATH = os.path.join(PASTA_APP, "categorias.json")
CONFIG_PATH = os.path.join(PASTA_APP, "configuracao.json")

# Tipos de transação do PicPay que são movimentação interna (não é gasto nem ganho)
TIPOS_COFRINHO = {"dinheiro guardado", "dinheiro resgatado"}


def normalizar(texto):
    """Remove acentos e coloca em minúsculas, pra comparar 'Alimentação' com
    'alimentacao' sem problema."""
    if not texto:
        return ""
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return texto.lower().strip()


def extrair_valor_com_sinal(valor_texto):
    """Converte '−R$ 89,06' (saída) ou '+R$ 200,00' (entrada) num float com sinal.
    Aceita tanto o sinal de menos "−" (U+2212, usado pelo PicPay) quanto o
    hífen comum "-"."""
    if not valor_texto:
        return 0.0
    negativo = ("−" in valor_texto) or bool(re.match(r"^\s*-", valor_texto))
    limpo = re.sub(r"[^\d,]", "", valor_texto)
    if not limpo:
        return 0.0
    valor = float(limpo.replace(",", "."))
    return -valor if negativo else valor


def carregar_categorias():
    if os.path.exists(CATEGORIAS_PATH):
        with open(CATEGORIAS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def categorizar(texto, categorias):
    texto_norm = normalizar(texto)
    for categoria, palavras in categorias.items():
        for palavra in palavras:
            if normalizar(palavra) in texto_norm:
                return categoria
    return "Outros"


def carregar_configuracao():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"meu_nome": ""}


def salvar_configuracao(config):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def classificar_transacao(tipo_transacao, origem_destino, meu_nome=None):
    """
    Decide se a transação é uma movimentação interna (não conta como gasto
    real): dinheiro indo/vindo do cofrinho de investimentos, ou Pix para
    você mesmo (entre suas próprias contas).

    Retorna (tipo, categoria):
      - tipo é "transferencia" quando é movimentação interna, ou None
        quando é uma despesa/receita de verdade (a decidir por sinal + palavra-chave)
      - categoria já vem preenchida quando tipo == "transferencia"
    """
    tipo_norm = normalizar(tipo_transacao)

    if tipo_norm in TIPOS_COFRINHO:
        return "transferencia", "Cofrinho / Investimentos"

    if meu_nome:
        nome_norm = normalizar(meu_nome)
        destino_norm = normalizar(origem_destino)
        if nome_norm and nome_norm in destino_norm:
            return "transferencia", "Transferência própria"

    return None, None
