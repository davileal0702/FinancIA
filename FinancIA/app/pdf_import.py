"""
pdf_import.py — Leitor do extrato em PDF do PicPay.

O PDF do PicPay não desenha linhas de tabela de verdade (sem bordas
detectáveis pelo pdfplumber), e nomes de estabelecimento longos quebram
em 2 ou 3 linhas dentro da célula "Origem / Destino" — isso bagunça a
ordem se a gente só ler o texto corrido de cima a baixo.

Por isso a leitura aqui é feita por COORDENADA: cada palavra tem uma
posição (x, y) na página. Usamos a posição x pra saber a QUAL COLUNA
a palavra pertence (Hora / Tipo / Origem-Destino / Forma / Valor), e a
posição y (chamada de "top" no pdfplumber) pra saber a QUAL TRANSAÇÃO
ela pertence — mesmo quando o nome da loja quebra em várias linhas
acima/abaixo da linha "âncora" daquela transação.

Se um dia o PicPay mudar esse layout, as faixas em COLUNAS abaixo são
o primeiro lugar a ajustar.
"""

import os
import re
import pdfplumber

import db
import extrato_utils as eu

PADRAO_HORA = re.compile(r"^\d{1,2}:\d{2}$")
PADRAO_DATA_EXTENSO = re.compile(
    r"^(\d{1,2})\s+de\s+(\w+)\s+(?:de\s+)?(\d{4})", re.IGNORECASE
)

MESES = {
    "janeiro": 1, "fevereiro": 2, "marco": 3, "abril": 4, "maio": 5, "junho": 6,
    "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12,
}

# Faixas de posição horizontal (x0, em pontos) de cada coluna — calibradas
# a partir de um extrato real do PicPay.
COLUNAS = [
    ("hora", 0, 115),
    ("tipo", 115, 240),
    ("origem", 240, 345),
    ("forma", 345, 460),
    ("valor", 460, 9999),
]

# Quantos pontos acima/abaixo da linha-âncora ainda contam como parte da
# mesma transação (cobre quebras de até 3 linhas na coluna Origem/Destino).
JANELA_LINHA = 11


def _coluna(x0):
    for nome, ini, fim in COLUNAS:
        if ini <= x0 < fim:
            return nome
    return "valor"


def _nome_do_titular(pdf):
    """O nome do titular da conta é a primeira linha da primeira página."""
    if not pdf.pages:
        return None
    palavras = pdf.pages[0].extract_words()
    if not palavras:
        return None
    primeiro_top = round(palavras[0]["top"])
    palavras_linha = [p for p in palavras if round(p["top"]) == primeiro_top]
    palavras_linha.sort(key=lambda w: w["x0"])
    return " ".join(w["text"] for w in palavras_linha).strip()


def extrair_transacoes(caminho_pdf):
    """Devolve uma lista de transações 'cruas' (ainda sem categoria),
    lendo o PDF inteiro por coordenadas."""
    transacoes = []

    with pdfplumber.open(caminho_pdf) as pdf:
        nome_titular = _nome_do_titular(pdf)

        for pagina in pdf.pages:
            palavras = pagina.extract_words(use_text_flow=False, keep_blank_chars=False)
            if not palavras:
                continue

            # Agrupa palavras por linha física (mesma posição vertical "top")
            linhas = {}
            for p in palavras:
                chave = round(p["top"])
                linhas.setdefault(chave, []).append(p)
            tops = sorted(linhas.keys())

            ancoras = []          # tops que começam uma transação (ex: "09:01")
            datas_por_top = {}    # tops que são cabeçalho de dia (ex: "04 de julho 2026")

            for top in tops:
                palavras_linha = sorted(linhas[top], key=lambda w: w["x0"])
                texto_linha = " ".join(w["text"] for w in palavras_linha)
                primeira = palavras_linha[0]

                if PADRAO_HORA.match(primeira["text"]) and primeira["x0"] < 115:
                    ancoras.append(top)
                    continue

                m = PADRAO_DATA_EXTENSO.match(texto_linha)
                if m:
                    dia, mes_nome, ano = m.groups()
                    mes_num = MESES.get(eu.normalizar(mes_nome))
                    if mes_num:
                        datas_por_top[top] = f"{int(ano):04d}-{mes_num:02d}-{int(dia):02d}"

            tops_data = sorted(datas_por_top.keys())

            for top_ancora in ancoras:
                # A data vigente é a última seção de dia encontrada ANTES desta âncora
                data_valida = None
                for td in tops_data:
                    if td <= top_ancora:
                        data_valida = datas_por_top[td]
                    else:
                        break
                if not data_valida:
                    continue

                # Junta todas as palavras num raio de +-JANELA_LINHA pontos
                colunas_texto = {"hora": [], "tipo": [], "origem": [], "forma": [], "valor": []}
                for top in tops:
                    if abs(top - top_ancora) <= JANELA_LINHA:
                        for w in linhas[top]:
                            colunas_texto[_coluna(w["x0"])].append(w)

                def montar(nome_col):
                    ws = sorted(colunas_texto[nome_col], key=lambda w: (w["top"], w["x0"]))
                    return " ".join(w["text"] for w in ws).strip()

                hora = montar("hora")
                if not PADRAO_HORA.match(hora):
                    continue

                tipo_transacao = montar("tipo")
                origem_destino = montar("origem")
                valor_texto = montar("valor")

                if not valor_texto:
                    continue

                transacoes.append({
                    "data": data_valida,
                    "hora": hora,
                    "tipo_transacao_original": tipo_transacao,
                    "origem_destino": origem_destino,
                    "descricao": f"{tipo_transacao} — {origem_destino}".strip(" —"),
                    "valor_com_sinal": eu.extrair_valor_com_sinal(valor_texto),
                    "nome_titular": nome_titular,
                })

    return transacoes


def _processar(transacoes_brutas):
    categorias = eu.carregar_categorias()
    config = eu.carregar_configuracao()
    meu_nome = config.get("meu_nome") or ""

    # Se ainda não sabemos o nome do titular, aprende automaticamente do PDF
    if not meu_nome and transacoes_brutas:
        nome_detectado = transacoes_brutas[0].get("nome_titular")
        if nome_detectado:
            meu_nome = nome_detectado
            config["meu_nome"] = meu_nome
            eu.salvar_configuracao(config)

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


def importar_pdf(caminho_pdf):
    nome_arquivo = os.path.basename(caminho_pdf)

    transacoes_brutas = extrair_transacoes(caminho_pdf)

    if not transacoes_brutas:
        return {
            "status": "vazio",
            "mensagem": (
                "Não consegui identificar transações nesse PDF. O layout do "
                "extrato pode ter mudado — me envie uma cópia (pode trocar os "
                "valores reais por fictícios, mantendo o layout) que eu ajusto o leitor."
            ),
        }

    transacoes = _processar(transacoes_brutas)
    return {"status": "preview", "transacoes": transacoes, "origem": nome_arquivo}


def confirmar_importacao(transacoes, origem):
    """Insere as transações, pulando individualmente qualquer uma que já
    exista no banco (mesma data+hora+valor+tipo) — isso é o que permite
    importar um extrato de 180 dias mesmo já tendo importado um PDF de
    30 dias antes: só as transações realmente novas entram."""
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
