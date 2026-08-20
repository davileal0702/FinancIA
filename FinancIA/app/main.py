"""
main.py — Terminal do FinancIA.

Fluxo de cada pergunta (duas fases, não mais um loop aberto):
  1. PLANEJAMENTO: a IA lê a pergunta e decide de uma vez só toda a lista de
     dados que precisa (pode ser mais de um — ex: "junho" E "julho" pra
     comparar). Isso evita o problema de ela ter que decidir, rodada a
     rodada, "continuo ou já respondo?" — decisão em que modelos menores
     travam e ficam repetindo a mesma consulta.
  2. Python executa cada consulta pedida (SQLite calcula, matplotlib desenha).
  3. SÍNTESE: com os dados já em mãos, a IA escreve a resposta final em
     texto livre (sem forçar JSON) — é aqui que ela consegue comentar e
     comparar de verdade, em vez de só devolver um número.
"""

import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import db
import tools
import llm_client
import pdf_import
import csv_import
import extrato_utils as eu

MAX_CONSULTAS_POR_PERGUNTA = 8
MODO_DEBUG = True  # mostra as ferramentas que a IA está chamando


def limpar_json(texto):
    texto = texto.strip()
    if texto.startswith("```"):
        texto = texto.strip("`")
        texto = texto.replace("json", "", 1).strip()
    inicio = texto.find("{")
    fim = texto.rfind("}")
    if inicio != -1 and fim != -1:
        texto = texto[inicio : fim + 1]
    return texto


def processar_pergunta(pergunta):
    # --- Fase 1: planejamento (decide toda a lista de consultas de uma vez) ---
    mensagens_plano = [
        {"role": "system", "content": tools.obter_prompt_planejamento()},
        {"role": "user", "content": pergunta},
    ]

    try:
        bruto = llm_client.perguntar_json(mensagens_plano)
    except RuntimeError as e:
        print(f"\n{e}\n")
        return

    limpo = limpar_json(bruto)
    try:
        plano = json.loads(limpo)
    except Exception:
        print("\nHmm, não consegui interpretar isso direito. Pode reformular?")
        print("--- [DEBUG] Resposta bruta da IA (planejamento) ---")
        print(bruto)
        print("--- [FIM DEBUG] ---\n")
        return

    consultas = plano.get("consultas", []) if isinstance(plano, dict) else []

    # --- Fase 2: executa as consultas pedidas, sem repetir nenhuma ---
    resultados = []
    vistos = set()
    for consulta in consultas[:MAX_CONSULTAS_POR_PERGUNTA]:
        nome_tool = consulta.get("tool") if isinstance(consulta, dict) else None
        if not nome_tool:
            continue
        params = consulta.get("params", {}) or {}
        chave = (nome_tool, json.dumps(params, sort_keys=True, ensure_ascii=False))
        if chave in vistos:
            continue
        vistos.add(chave)

        if MODO_DEBUG:
            print(f"  [consultando: {nome_tool}({params})]")

        resultado_tool = tools.executar(nome_tool, params)
        resultados.append({"tool": nome_tool, "params": params, "resultado": resultado_tool})

    # --- Fase 3: síntese (texto livre, sem JSON) ---
    if resultados:
        mensagens_resposta = [
            {"role": "system", "content": "Você é um assistente financeiro pessoal, direto e analítico. Responda sempre em português, em texto natural — nunca em JSON."},
            {"role": "user", "content": tools.montar_prompt_sintese(pergunta, resultados)},
        ]
    else:
        # Pergunta não precisou de nenhum dado (ex: só uma conversa/cumprimento)
        mensagens_resposta = [
            {"role": "system", "content": "Você é um assistente financeiro pessoal, simpático e direto. Responda sempre em português, em texto natural."},
            {"role": "user", "content": pergunta},
        ]

    try:
        resposta_final = llm_client.perguntar_texto_livre(mensagens_resposta)
    except RuntimeError as e:
        print(f"\n{e}\n")
        return

    print(f"\n{resposta_final.strip()}\n")


def importar(caminho):
    caminho = caminho.strip().strip('"').strip("'")
    if not os.path.exists(caminho):
        print(f"\nNão achei o arquivo em: {caminho}\n")
        return

    extensao = os.path.splitext(caminho)[1].lower()
    if extensao == ".csv":
        resultado = csv_import.importar_csv(caminho)
        modulo = csv_import
    elif extensao == ".pdf":
        resultado = pdf_import.importar_pdf(caminho)
        modulo = pdf_import
    else:
        print(f"\nNão sei ler arquivos '{extensao}'. Use um .pdf ou .csv exportado do PicPay.\n")
        return

    if resultado["status"] in ("duplicado", "vazio"):
        print(f"\n{resultado['mensagem']}\n")
        return

    transacoes = resultado["transacoes"]

    marcador = {"despesa": " ", "receita": "+", "transferencia": "~"}
    print(f"\nEncontrei {len(transacoes)} transações:")
    print("(+ = entrada  ~ = transferência interna, não conta como gasto/ganho)\n")
    for t in transacoes[:20]:
        m = marcador.get(t["tipo"], " ")
        print(f"  {m} {t['data']}  {t['descricao'][:42]:<42}  {t['categoria']:<22}  R$ {t['valor']:.2f}")
    if len(transacoes) > 20:
        print(f"  ... e mais {len(transacoes) - 20}")

    n_despesas = sum(1 for t in transacoes if t["tipo"] == "despesa")
    n_receitas = sum(1 for t in transacoes if t["tipo"] == "receita")
    n_transf = sum(1 for t in transacoes if t["tipo"] == "transferencia")
    print(f"\nResumo: {n_despesas} despesas, {n_receitas} receitas, {n_transf} transferências internas.")

    confirmar = input("\nConfirma a importação? (s/n): ").strip().lower()
    if confirmar == "s":
        inseridas, ignoradas = modulo.confirmar_importacao(transacoes, resultado["origem"])
        print(f"\n{inseridas} transações novas importadas com sucesso!")
        if ignoradas:
            print(f"({ignoradas} já existiam no seu histórico e foram puladas automaticamente, sem duplicar)")
        print()
    else:
        print("\nImportação cancelada.\n")


def verificar_duplicatas():
    duplicatas = db.encontrar_duplicatas_exatas()
    if not duplicatas:
        print("\nNenhuma duplicata encontrada no seu histórico. Tudo certo!\n")
        return

    total_extras = sum(qtd - 1 for *_resto, qtd, _ids in duplicatas)
    print(f"\nEncontrei {len(duplicatas)} transações repetidas, totalizando {total_extras} cópias extras:\n")
    for data, descricao, categoria, valor, tipo, qtd, _ids in duplicatas[:15]:
        print(f"  {data}  {descricao[:40]:<40}  {categoria:<20}  R$ {valor:.2f}  (aparece {qtd}x)")
    if len(duplicatas) > 15:
        print(f"  ... e mais {len(duplicatas) - 15} grupos")

    confirmar = input("\nRemover as cópias extras, mantendo só uma de cada? (s/n): ").strip().lower()
    if confirmar == "s":
        removidas = db.remover_duplicatas_exatas()
        print(f"\n{removidas} transações duplicadas removidas. Seus totais já refletem isso.\n")
    else:
        print("\nNada foi removido.\n")


def recategorizar_tudo():
    categorias = eu.carregar_categorias()

    def categorizador(descricao):
        return eu.categorizar(descricao, categorias)

    alteradas = db.recategorizar_todos_por_regras(categorizador)
    if alteradas:
        print(f"\n{alteradas} transações foram reclassificadas com as categorias atuais.\n")
    else:
        print("\nNenhuma transação precisou mudar de categoria — já estava tudo de acordo.\n")


def main():
    print("=" * 55)
    print("   FinancIA — assistente financeiro local")
    print("=" * 55)
    print("Comandos:")
    print('  importar "caminho\\do\\extrato.pdf"   -> importa um PDF/CSV do PicPay')
    print("  verificar_duplicatas                -> checa e limpa gastos duplicados")
    print("  recategorizar_tudo                  -> reaplica categorias.json em tudo que já foi importado")
    print("  sair                                -> fecha o assistente")
    print("Ou apenas pergunte algo, ex: 'quanto gastei em junho?'\n")

    while True:
        try:
            entrada = input("Você: ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not entrada:
            continue
        if entrada.lower() in ("sair", "exit", "quit"):
            break
        if entrada.lower().startswith("importar "):
            importar(entrada[len("importar "):])
            continue
        if entrada.lower() in ("verificar_duplicatas", "verificar duplicatas", "checar duplicatas"):
            verificar_duplicatas()
            continue
        if entrada.lower() in ("recategorizar_tudo", "recategorizar tudo"):
            recategorizar_tudo()
            continue

        processar_pergunta(entrada)

    print("\nAté a próxima!")


if __name__ == "__main__":
    main()
