"""
charts.py — Geração de gráficos com matplotlib.

Cada gráfico é salvo como PNG em graficos/ e aberto automaticamente
no visualizador de imagens padrão do Windows.
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import os
import sys

import db

PASTA_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PASTA_GRAFICOS = os.path.join(PASTA_RAIZ, "graficos")


def _salvar_e_abrir(fig, nome_arquivo):
    os.makedirs(PASTA_GRAFICOS, exist_ok=True)
    caminho = os.path.join(PASTA_GRAFICOS, nome_arquivo)
    fig.savefig(caminho, dpi=150, bbox_inches="tight")
    plt.close(fig)
    if sys.platform == "win32":
        try:
            os.startfile(caminho)
        except Exception:
            pass
    return caminho


def grafico_pizza_categorias(ano, mes=None):
    dados = db.total_por_categoria(ano, mes)
    if not dados:
        return None
    categorias = [d[0] for d in dados]
    valores = [d[1] for d in dados]
    fig, ax = plt.subplots(figsize=(7, 7))
    ax.pie(valores, labels=categorias, autopct="%1.1f%%", startangle=90)
    titulo = f"Gastos por categoria — {int(mes):02d}/{ano}" if mes else f"Gastos por categoria — {ano}"
    ax.set_title(titulo)
    nome = f"pizza_{ano}_{mes or 'ano'}.png"
    return _salvar_e_abrir(fig, nome)


def grafico_evolucao_mensal(ano):
    meses = list(range(1, 13))
    valores = [db.total_periodo(ano, m) for m in meses]
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(meses, valores, color="#4C72B0")
    ax.set_xticks(meses)
    ax.set_xlabel("Mês")
    ax.set_ylabel("Total gasto (R$)")
    ax.set_title(f"Evolução de gastos em {ano}")
    nome = f"evolucao_{ano}.png"
    return _salvar_e_abrir(fig, nome)


def grafico_comparativo_categoria(categoria, ano):
    meses = list(range(1, 13))
    valores = []
    for m in meses:
        dados = dict(db.total_por_categoria(ano, m))
        valores.append(dados.get(categoria, 0))
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(meses, valores, marker="o", color="#DD8452")
    ax.set_xticks(meses)
    ax.set_xlabel("Mês")
    ax.set_ylabel("R$")
    ax.set_title(f"{categoria} ao longo de {ano}")
    nome = f"{categoria.replace(' ', '_')}_{ano}.png"
    return _salvar_e_abrir(fig, nome)
