"""
llm_client.py — Fala com o llama-server via HTTP local (127.0.0.1).

Importante: isso NÃO é acesso à internet. É apenas o Python conversando
com outro programa (o llama-server) que está rodando no mesmo computador,
pela porta 8080. Nenhum dado sai da máquina.

Usa apenas a biblioteca padrão do Python (urllib), então não precisa
instalar nada extra só para essa parte.
"""

import json
import os
import urllib.request

SERVIDOR = "http://127.0.0.1:8080"
PASTA_APP = os.path.dirname(os.path.abspath(__file__))
GRAMATICA_PLANO = os.path.join(PASTA_APP, "grammars", "plano.gbnf")


def _chamar(mensagens, gramatica_path=None, temperatura=0.2, debug=False, max_tokens=500, tentativa_timeout=300):
    corpo = {
        "messages": mensagens,
        "temperature": temperatura,
        "max_tokens": max_tokens,
        "stream": False,
    }
    if gramatica_path and os.path.exists(gramatica_path):
        with open(gramatica_path, "r", encoding="utf-8") as f:
            corpo["grammar"] = f.read()

    dados = json.dumps(corpo).encode("utf-8")
    req = urllib.request.Request(
        f"{SERVIDOR}/v1/chat/completions",
        data=dados,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=tentativa_timeout) as resp:
            resultado = json.loads(resp.read().decode("utf-8"))

        mensagem = resultado["choices"][0]["message"]
        conteudo = (mensagem.get("content") or "").strip()
        if not conteudo:
            # Alguns modelos (ex: Qwen3.5) colocam a resposta dentro do
            # "raciocinio interno" em vez do campo de resposta final.
            conteudo = (mensagem.get("reasoning_content") or "").strip()

        if debug:
            print(f"--- [DEBUG] IA respondeu: {conteudo[:300]} ---")

        return conteudo
    except TimeoutError:
        raise RuntimeError(
            f"O motor de IA demorou mais de {tentativa_timeout}s pra responder e eu desisti de esperar. "
            "Isso costuma acontecer quando ele está rodando na CPU em vez da GPU (bem mais lento). "
            "Vale confirmar se a GPU está mesmo sendo usada (veja o console do llama-server)."
        )
    except urllib.error.URLError:
        raise RuntimeError(
            "Não consegui falar com o motor de IA (llama-server). "
            "Ele está rodando? Veja se a janela minimizada dele não fechou."
        )


def perguntar_json(mensagens, debug=False):
    """Fase de planejamento: gramática TRAVADA em {"consultas": [...]} —
    isso impede a IA de incluir campos extras (ex: um "thought" bem longo)
    que consumiam o limite de tokens antes de chegar na parte que importa."""
    return _chamar(mensagens, gramatica_path=GRAMATICA_PLANO, temperatura=0.2, debug=debug, max_tokens=700)


def perguntar_texto_livre(mensagens, debug=False):
    """Fase de síntese: SEM gramática, texto livre — usada depois que os
    dados já foram coletados, pra IA escrever a resposta final em português
    natural (é aqui que ela costuma se sair melhor). max_tokens evita que
    ela entre numa geração longa demais e trave o programa esperando."""
    return _chamar(mensagens, gramatica_path=None, temperatura=0.4, debug=debug, max_tokens=500)
