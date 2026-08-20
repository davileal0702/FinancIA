"""
db.py — Camada de dados do FinancIA.

Toda a matemática (somas, médias, agrupamentos) é feita aqui via SQL,
nunca pela IA. Isso garante que os números estão sempre corretos,
independente de qual modelo de IA você estiver usando.

O banco fica em data/gastos.db e cresce mês a mês sem limite —
é assim que a IA "nunca esquece": ela consulta o histórico, não o
carrega inteiro numa conversa.
"""

import sqlite3
import os
import unicodedata

PASTA_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PASTA_RAIZ, "data", "gastos.db")


def _normalizar_simples(texto):
    if not texto:
        return ""
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return texto.lower().strip()


def resolver_categoria(nome_aproximado):
    """Acha o nome EXATO da categoria salva no banco mais parecido com o
    que foi pedido, ignorando maiúscula/minúscula e acento — assim
    'mercado', 'Mercado' ou 'MERCADO' sempre encontram a mesma coisa,
    mesmo que a IA escreva a categoria de um jeito levemente diferente
    do que está salvo."""
    if not nome_aproximado:
        return None
    conn = conectar()
    cur = conn.execute("SELECT DISTINCT categoria FROM gastos")
    categorias_reais = [row[0] for row in cur.fetchall()]
    conn.close()

    alvo = _normalizar_simples(nome_aproximado)
    for cat in categorias_reais:
        if _normalizar_simples(cat) == alvo:
            return cat
    return nome_aproximado  # não achou parecido — devolve como veio (não quebra a busca)


def conectar():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS gastos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT NOT NULL,              -- formato YYYY-MM-DD
            hora TEXT NOT NULL DEFAULT '',    -- formato HH:MM, quando disponível
            descricao TEXT NOT NULL,
            categoria TEXT NOT NULL DEFAULT 'Outros',
            valor REAL NOT NULL,             -- sempre positivo
            tipo TEXT NOT NULL DEFAULT 'despesa',  -- 'despesa' ou 'receita'
            origem TEXT,                     -- nome do arquivo PDF/CSV de origem
            importado_em TEXT DEFAULT (datetime('now'))
        )
        """
    )
    # Migração: bancos criados antes da coluna "hora" existir ganham ela aqui,
    # sem perder nenhum dado já importado.
    colunas = [linha[1] for linha in conn.execute("PRAGMA table_info(gastos)")]
    if "hora" not in colunas:
        conn.execute("ALTER TABLE gastos ADD COLUMN hora TEXT NOT NULL DEFAULT ''")
    conn.commit()
    return conn


def adicionar_gasto(data, descricao, categoria, valor, tipo="despesa", origem=None, hora=""):
    conn = conectar()
    conn.execute(
        "INSERT INTO gastos (data, hora, descricao, categoria, valor, tipo, origem) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (data, hora, descricao, categoria, valor, tipo, origem),
    )
    conn.commit()
    conn.close()


def ja_importado(origem):
    """Evita importar o mesmo arquivo duas vezes (checagem pelo nome do arquivo)."""
    conn = conectar()
    cur = conn.execute("SELECT COUNT(*) FROM gastos WHERE origem = ?", (origem,))
    count = cur.fetchone()[0]
    conn.close()
    return count > 0


def transacao_ja_existe(data, hora, valor, tipo):
    """Checagem precisa por TRANSAÇÃO (não por arquivo inteiro): compara
    data + hora + valor + tipo. Isso é o que impede duplicar um gasto
    quando o mesmo período aparece em dois arquivos diferentes (ex: PDF
    de 30 dias e depois um CSV de 180 dias que já inclui esses 30 dias),
    mesmo que os nomes dos arquivos sejam diferentes."""
    conn = conectar()
    if hora:
        cur = conn.execute(
            "SELECT COUNT(*) FROM gastos WHERE data = ? AND hora = ? AND ABS(valor - ?) < 0.01 AND tipo = ?",
            (data, hora, valor, tipo),
        )
    else:
        # Sem hora disponível (ex: formato antigo), cai pra comparação por dia inteiro
        cur = conn.execute(
            "SELECT COUNT(*) FROM gastos WHERE data = ? AND ABS(valor - ?) < 0.01 AND tipo = ?",
            (data, valor, tipo),
        )
    existe = cur.fetchone()[0] > 0
    conn.close()
    return existe


def total_periodo(ano, mes=None, tipo="despesa"):
    conn = conectar()
    padrao = f"{int(ano):04d}-{int(mes):02d}%" if mes else f"{int(ano):04d}%"
    cur = conn.execute(
        "SELECT COALESCE(SUM(valor), 0) FROM gastos WHERE data LIKE ? AND tipo = ?",
        (padrao, tipo),
    )
    total = cur.fetchone()[0]
    conn.close()
    return total


def total_por_categoria(ano, mes=None, tipo="despesa"):
    conn = conectar()
    padrao = f"{int(ano):04d}-{int(mes):02d}%" if mes else f"{int(ano):04d}%"
    cur = conn.execute(
        "SELECT categoria, COALESCE(SUM(valor), 0) FROM gastos "
        "WHERE data LIKE ? AND tipo = ? GROUP BY categoria ORDER BY 2 DESC",
        (padrao, tipo),
    )
    resultado = cur.fetchall()
    conn.close()
    return resultado


def listar_gastos(ano, mes=None, categoria=None, tipo="despesa", limite=50):
    if categoria:
        categoria = resolver_categoria(categoria)
    conn = conectar()
    padrao = f"{int(ano):04d}-{int(mes):02d}%" if mes else f"{int(ano):04d}%"
    if categoria:
        cur = conn.execute(
            "SELECT data, descricao, categoria, valor FROM gastos "
            "WHERE data LIKE ? AND tipo = ? AND categoria = ? ORDER BY data LIMIT ?",
            (padrao, tipo, categoria, limite),
        )
    else:
        cur = conn.execute(
            "SELECT data, descricao, categoria, valor FROM gastos "
            "WHERE data LIKE ? AND tipo = ? ORDER BY data LIMIT ?",
            (padrao, tipo, limite),
        )
    resultado = cur.fetchall()
    conn.close()
    return resultado


def media_mensal(categoria=None, tipo="despesa"):
    if categoria:
        categoria = resolver_categoria(categoria)
    conn = conectar()
    if categoria:
        cur = conn.execute(
            "SELECT strftime('%Y-%m', data) AS mes, SUM(valor) FROM gastos "
            "WHERE tipo = ? AND categoria = ? GROUP BY mes",
            (tipo, categoria),
        )
    else:
        cur = conn.execute(
            "SELECT strftime('%Y-%m', data) AS mes, SUM(valor) FROM gastos "
            "WHERE tipo = ? GROUP BY mes",
            (tipo,),
        )
    valores = [row[1] for row in cur.fetchall()]
    conn.close()
    if not valores:
        return 0.0
    return sum(valores) / len(valores)


def recategorizar(id_gasto, nova_categoria):
    conn = conectar()
    conn.execute("UPDATE gastos SET categoria = ? WHERE id = ?", (nova_categoria, id_gasto))
    conn.commit()
    conn.close()


def encontrar_duplicatas_exatas():
    """Encontra grupos de transações idênticas (mesma data, descrição,
    categoria, valor e tipo) que aparecem mais de uma vez no banco —
    sinal de reimportação do mesmo período em arquivos diferentes."""
    conn = conectar()
    cur = conn.execute(
        """
        SELECT data, descricao, categoria, valor, tipo, COUNT(*) as qtd, GROUP_CONCAT(id) as ids
        FROM gastos
        GROUP BY data, descricao, categoria, valor, tipo
        HAVING COUNT(*) > 1
        ORDER BY data
        """
    )
    resultado = cur.fetchall()
    conn.close()
    return resultado


def remover_duplicatas_exatas():
    """Remove as cópias extras de cada grupo duplicado, mantendo sempre
    o registro mais antigo (menor id). Devolve quantas linhas foram removidas."""
    duplicatas = encontrar_duplicatas_exatas()
    conn = conectar()
    total_removidas = 0
    for _data, _descricao, _categoria, _valor, _tipo, _qtd, ids_str in duplicatas:
        ids = sorted(int(i) for i in ids_str.split(","))
        for id_remover in ids[1:]:  # mantem o primeiro, remove o resto
            conn.execute("DELETE FROM gastos WHERE id = ?", (id_remover,))
            total_removidas += 1
    conn.commit()
    conn.close()
    return total_removidas


def identificar_recorrentes(tipo="despesa"):
    """Agrupa transações pela descrição e conta em quantos MESES DIFERENTES
    cada uma aparece. Quem aparece em 2+ meses distintos é recorrente
    (assinatura, financiamento, mercado que você sempre frequenta); quem
    aparece em 1 mês só é avulso (compra pontual, presente, imprevisto)."""
    conn = conectar()
    cur = conn.execute(
        """
        SELECT descricao, categoria,
               COUNT(DISTINCT strftime('%Y-%m', data)) AS n_meses,
               COUNT(*) AS n_transacoes,
               SUM(valor) AS total,
               AVG(valor) AS media
        FROM gastos
        WHERE tipo = ?
        GROUP BY descricao, categoria
        ORDER BY n_meses DESC, total DESC
        """,
        (tipo,),
    )
    resultado = cur.fetchall()
    conn.close()
    return resultado


def recategorizar_todos_por_regras(categorizador):
    """Reaplica a categorização (categorias.json) em TODOS os gastos já
    salvos — útil depois de editar categorias.json, pra que a mudança
    valha também pro que já foi importado, não só pro que vier depois.
    'categorizador' é uma função(descricao) -> nova_categoria, passada de
    fora pra não criar dependência circular com extrato_utils."""
    conn = conectar()
    cur = conn.execute("SELECT id, descricao, categoria FROM gastos WHERE tipo IN ('despesa', 'receita')")
    linhas = cur.fetchall()
    alteradas = 0
    for id_gasto, descricao, categoria_atual in linhas:
        nova_categoria = categorizador(descricao)
        if nova_categoria != categoria_atual:
            conn.execute("UPDATE gastos SET categoria = ? WHERE id = ?", (nova_categoria, id_gasto))
            alteradas += 1
    conn.commit()
    conn.close()
    return alteradas


def meses_disponiveis():
    conn = conectar()
    cur = conn.execute("SELECT DISTINCT strftime('%Y-%m', data) FROM gastos ORDER BY 1")
    resultado = [row[0] for row in cur.fetchall()]
    conn.close()
    return resultado
