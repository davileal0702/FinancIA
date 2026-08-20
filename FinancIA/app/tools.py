"""
tools.py — Ponte entre a IA e os dados reais.

A IA nunca faz conta — quem soma, agrupa e calcula média é sempre o
SQLite (em db.py). Mas agora as ferramentas devolvem DADOS BRUTOS
(dicionários), não mais texto pronto. Isso é o que permite a IA de
verdade analisar, comparar e comentar os números na resposta final,
em vez de só repetir uma frase decorada.
"""

import datetime
import json

import db
import charts


def obter_prompt_planejamento():
    hoje = datetime.date.today()
    return f"""Você é a camada de planejamento de um assistente financeiro pessoal.
Leia a pergunta do usuário e decida QUAIS DADOS você precisa consultar pra respondê-la bem.

Ferramentas disponíveis:
- total_periodo: soma de despesas de UM período. params: {{"ano": <int>, "mes": <int ou null>}}
- total_por_categoria: despesas por categoria de UM período. params: {{"ano": <int>, "mes": <int ou null>}}
- totais_por_mes: soma de despesas de TODOS os 12 meses de um ano, de uma vez (sem abrir nada visual) — use essa pra qualquer comparação entre vários meses ou "o ano todo", em vez de chamar total_periodo mês a mês. params: {{"ano": <int>}}
- listar_gastos: lista transações. params: {{"ano": <int>, "mes": <int ou null>, "categoria": <string ou null>}}
- media_mensal: média mensal de despesas. params: {{"categoria": <string ou null>}}
- meses_disponiveis: quais meses/anos existem dados no banco. params: {{}}
- gastos_recorrentes: separa despesas RECORRENTES (aparecem em vários meses — assinaturas, financiamentos, mercado que você sempre frequenta) de despesas AVULSAS (aparecem em um mês só — compra pontual, imprevisto, presente). Use quando o usuário perguntar sobre gastos fixos vs. avulsos/pontuais. params: {{}}
- grafico_pizza: gera e ABRE um gráfico de pizza por categoria — só use se o usuário pedir pra VER/gerar um gráfico. params: {{"ano": <int>, "mes": <int ou null>}}
- grafico_evolucao: gera e ABRE um gráfico de barras da evolução mensal — só use se o usuário pedir pra VER/gerar um gráfico (pra só comparar números sem abrir imagem, use totais_por_mes). params: {{"ano": <int>}}
- grafico_comparativo: gera e ABRE um gráfico de linha de uma categoria ao longo do ano — só use se o usuário pedir pra VER/gerar um gráfico. params: {{"categoria": <string>, "ano": <int>}}
- recategorizar: muda a categoria de um gasto pelo id. params: {{"id": <int>, "categoria": <string>}}

Se a pergunta pedir uma COMPARAÇÃO (ex: "mudou de junho pra julho?", "esse mês vs a média",
"compare com os demais meses"), inclua TODAS as consultas necessárias JÁ NESSA LISTA — você
não terá uma segunda chance de pedir mais dados depois. Prefira sempre a ferramenta que traz
mais dados de uma vez só (ex: totais_por_mes em vez de 12 chamadas de total_periodo).

Responda APENAS com este JSON, sem nenhum texto antes ou depois:
{{"consultas": [{{"tool": "nome_da_ferramenta", "params": {{...}}}}, ...]}}

Se a pergunta não precisar de nenhum dado (cumprimento, conversa geral, opinião), responda:
{{"consultas": []}}

A data de hoje é {hoje.strftime('%d/%m/%Y')} — o ano atual é {hoje.year}, o mês atual é
{hoje.month}. Se o usuário não disser o ano, assuma {hoje.year}. Responda SEMPRE em JSON válido.
"""


def montar_prompt_sintese(pergunta, resultados):
    dados_texto = json.dumps(resultados, ensure_ascii=False, indent=2)
    return f"""O usuário perguntou: "{pergunta}"

Você consultou os seguintes dados reais do banco de dele:
{dados_texto}

Responda em português, em texto natural (sem JSON, sem markdown, só a resposta em si).
Não apenas repita os números — compare, aponte o que chama atenção (categoria que mais
pesou, alta ou queda em relação à média/mês anterior, algo fora do padrão), como um
consultor faria. Use APENAS os números mostrados acima, nunca invente ou estime valores.
Se os dados não foram suficientes pra responder bem, diga isso claramente.
"""


def executar(tool_name, params):
    if tool_name == "total_periodo":
        ano = params.get("ano")
        mes = params.get("mes")
        total = db.total_periodo(ano, mes)
        return {"ano": ano, "mes": mes, "total_despesas": round(total, 2)}

    elif tool_name == "total_por_categoria":
        ano = params.get("ano")
        mes = params.get("mes")
        dados = db.total_por_categoria(ano, mes)
        return {
            "ano": ano, "mes": mes,
            "categorias": [{"categoria": c, "total": round(v, 2)} for c, v in dados],
        }

    elif tool_name == "listar_gastos":
        registros = db.listar_gastos(params.get("ano"), params.get("mes"), params.get("categoria"))
        return {
            "transacoes": [
                {"data": d, "descricao": desc, "categoria": cat, "valor": round(v, 2)}
                for d, desc, cat, v in registros
            ]
        }

    elif tool_name == "media_mensal":
        categoria = params.get("categoria")
        media = db.media_mensal(categoria)
        return {"categoria": categoria, "media_mensal": round(media, 2)}

    elif tool_name == "totais_por_mes":
        ano = params.get("ano")
        dados = [{"mes": m, "total": round(db.total_periodo(ano, m), 2)} for m in range(1, 13)]
        return {"ano": ano, "totais_por_mes": dados}

    elif tool_name == "gastos_recorrentes":
        tipo = params.get("tipo", "despesa")
        dados = db.identificar_recorrentes(tipo)
        recorrentes = []
        avulsos = []
        for descricao, categoria, n_meses, n_transacoes, total, media in dados:
            item = {
                "descricao": descricao,
                "categoria": categoria,
                "meses_diferentes": n_meses,
                "vezes": n_transacoes,
                "total_geral": round(total, 2),
                "valor_medio": round(media, 2),
            }
            if n_meses >= 2:
                recorrentes.append(item)
            else:
                avulsos.append(item)
        return {"recorrentes": recorrentes, "avulsos": avulsos}

    elif tool_name == "meses_disponiveis":
        return {"meses_com_dados": db.meses_disponiveis()}

    elif tool_name == "grafico_pizza":
        ano, mes = params.get("ano"), params.get("mes")
        dados = db.total_por_categoria(ano, mes)
        caminho = charts.grafico_pizza_categorias(ano, mes)
        return {
            "grafico_gerado": bool(caminho),
            "arquivo": caminho,
            "dados_do_grafico": [{"categoria": c, "total": round(v, 2)} for c, v in dados],
        }

    elif tool_name == "grafico_evolucao":
        ano = params.get("ano")
        dados = [{"mes": m, "total": round(db.total_periodo(ano, m), 2)} for m in range(1, 13)]
        caminho = charts.grafico_evolucao_mensal(ano)
        return {"grafico_gerado": bool(caminho), "arquivo": caminho, "dados_do_grafico": dados}

    elif tool_name == "grafico_comparativo":
        categoria, ano = params.get("categoria"), params.get("ano")
        dados = []
        for m in range(1, 13):
            por_categoria = dict(db.total_por_categoria(ano, m))
            dados.append({"mes": m, "total": round(por_categoria.get(categoria, 0), 2)})
        caminho = charts.grafico_comparativo_categoria(categoria, ano)
        return {"grafico_gerado": bool(caminho), "arquivo": caminho, "dados_do_grafico": dados}

    elif tool_name == "recategorizar":
        db.recategorizar(params.get("id"), params.get("categoria"))
        return {"sucesso": True}

    else:
        return {"erro": f"Ferramenta desconhecida: {tool_name}"}
