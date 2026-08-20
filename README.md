# FinancIA

Assistente de IA local para controle de gastos pessoais — roda inteiramente offline
(sem internet, sem enviar seus dados pra lugar nenhum), lê extratos do PicPay (PDF
ou CSV), guarda tudo num banco de dados local e responde perguntas em português
com análise de verdade, não só números soltos.

Pensado pra ser portátil: dá pra montar num pendrive e usar em qualquer PC Windows
sem instalar nada além das dependências (baixadas uma vez, self-contained).

## O que ele faz

- **Importa extratos do PicPay** (PDF ou CSV) e categoriza as transações automaticamente
- **Separa transferências internas** (cofrinho de investimentos, Pix pra você mesmo)
  dos gastos/ganhos reais, pra não distorcer seus totais
- **Detecta duplicatas** — mesmo se você importar períodos sobrepostos em formatos
  diferentes, não conta a mesma transação duas vezes
- **Responde perguntas em português natural**, com análise (compara meses, aponta
  o que chama atenção, separa gastos fixos de avulsos) — a matemática é sempre
  feita por código determinístico (SQLite), a IA só interpreta e comenta os
  números reais, nunca inventa ou estima valores
- **Gera gráficos** (pizza por categoria, evolução mensal, comparativo por categoria)
- **100% local**: o motor de IA (llama.cpp) e o modelo rodam na sua máquina

## Arquitetura

```
Pergunta em português
        │
        ▼
┌───────────────────┐     1. Planejamento: a IA decide TODA a lista de dados
│   Fase 1: Plano    │        que precisa consultar de uma vez (JSON, gramática
└─────────┬──────────┘        travada via GBNF)
          │
          ▼
┌───────────────────┐     2. Execução: Python/SQLite calcula de verdade
│  Fase 2: Execução  │        (soma, agrupa, gera gráfico) — a IA nunca faz conta
└─────────┬──────────┘
          │
          ▼
┌───────────────────┐     3. Síntese: com os dados reais em mãos, a IA escreve
│  Fase 3: Síntese   │        a resposta final em texto livre (sem JSON)
└────────────────────┘
```

Por que duas fases em vez de deixar a IA decidir "continuo ou já respondo?" a
cada rodada: modelos locais menores tendem a travar em loops de repetição
nesse tipo de decisão aberta. Decidir tudo de uma vez, executar, e só depois
sintetizar evita esse problema e fica mais rápido (menos idas e voltas).

## Requisitos

- Windows 10/11, 64-bit
- ~15 GB de espaço livre (motor de IA + modelo + Python portátil)
- Se for usar num pendrive: **formatado em exFAT**, não FAT32 (FAT32 tem limite de
  4 GB por arquivo e o modelo de IA é maior que isso)

## Instalação

### 1. Baixe este repositório

Baixe o código deste repositório (`Code` → `Download ZIP`, ou `git clone`) e
extraia numa pasta — pode ser no seu HD ou num pendrive/drive externo formatado
em exFAT.

### 2. Motor de IA (llama.cpp)

Acesse as [releases do llama.cpp](https://github.com/ggml-org/llama.cpp/releases)
e baixe:

- **Sempre:** a versão **Windows x64 (CPU)** — ex: `llama-<versão>-bin-win-cpu-x64.zip`
  → extraia o conteúdo em `bin\cpu\`
- **Se tiver GPU NVIDIA:** também a versão **Windows x64 (CUDA)** correspondente
  à sua versão de driver (12.x é a mais compatível) **e** o pacote **"CUDA DLLs"**
  correspondente → extraia os dois juntos em `bin\cuda\`

O `Iniciar.bat` detecta sozinho se há uma GPU NVIDIA disponível (via `nvidia-smi`)
e escolhe a pasta certa automaticamente — não precisa configurar nada manualmente
pra isso.

### 3. Modelo de IA

Recomendado: **Qwen3-8B-Instruct**, quantização **Q4_K_M** (~5 GB).

👉 [Qwen_Qwen3-8B-Q4_K_M.gguf](https://huggingface.co/bartowski/Qwen_Qwen3-8B-GGUF/resolve/main/Qwen_Qwen3-8B-Q4_K_M.gguf?download=true)

Renomeie o arquivo baixado para **`modelo.gguf`** e coloque em `models\`.

> **Evite o Qwen3.5** apesar de mais novo: ele usa um componente de arquitetura
> ("Gated Delta Net") com suporte ainda instável em várias backends de GPU do
> llama.cpp (CUDA incluso), causando travamentos depois de algumas respostas —
> [issue documentada aqui](https://github.com/ggml-org/llama.cpp/issues/20423).
> O Qwen3 "clássico" usa arquitetura padrão, bem mais madura e estável.

### 4. Python portátil

Baixe o **WinPython** (versão "dot", a mais enxuta — sem pacotes desnecessários)
em [winpython.github.io](https://winpython.github.io/), extraia, e copie o
**conteúdo** da subpasta `python` (não a pasta toda) pra dentro de `python\`
deste projeto — o resultado deve ser `python\python.exe`.

### 5. Instale as dependências

Dê dois cliques em **`Instalar_Dependencias.bat`**. Ele confere cada etapa e
avisa exatamente o que fazer se algo faltar (Python não encontrado, sem internet,
erro de certificado, etc.).

### 6. Primeira execução — desbloqueio do Windows

Arquivos baixados da internet (os `.exe`/`.dll` do llama.cpp) vêm marcados pelo
Windows como "não confiável" e podem ser bloqueados. Duas coisas a checar:

**a) SmartScreen / Mark of the Web** — resolva rodando isto no PowerShell
(ajuste o caminho conforme onde você extraiu o projeto):
```powershell
Get-ChildItem -Path "C:\caminho\FinancIA\bin" -Recurse | Unblock-File
```

**b) Smart App Control** (Windows 11, mais recente e mais rígido) — se o erro
`0xc0e90002` aparecer mesmo depois do Unblock-File, esse é o culpado. Verifique
em Segurança do Windows → Controle de aplicativos e navegador → Controle
inteligente de aplicativos. **Atenção:** desativar esse recurso é uma via de
mão única — só reativa reinstalando o Windows. Pense antes de desligar.

### 7. Use

Dê dois cliques em **`Iniciar.bat`**. Isso abre o terminal do assistente.

```
importar "C:\caminho\extrato.pdf"      → importa um extrato do PicPay (PDF ou CSV)
verificar_duplicatas                   → checa e limpa gastos duplicados
recategorizar_tudo                     → reaplica categorias.json em tudo já importado
sair                                    → fecha o assistente
```

Ou pergunte livremente:
```
Quanto gastei em julho?
Minha maior categoria mudou de junho pra julho?
Quais dos meus gastos são fixos e quais são avulsos?
Gera um gráfico da evolução do ano e me diz se tem algum mês estranho
```

## Personalizando categorias

Edite `app/categorias.json` — é só uma lista de palavras-chave por categoria,
sem precisar mexer em código:

```json
{
  "Mercado": ["nome do seu supermercado", "outro supermercado"],
  "Categoria Nova": ["palavra-chave", "outra palavra-chave"]
}
```

Depois de editar, rode o comando `recategorizar_tudo` no assistente pra aplicar
as mudanças em tudo que já foi importado (não só nas próximas importações).

## Formato do extrato

O leitor de PDF (`app/pdf_import.py`) foi calibrado com o layout real do extrato
de conta do PicPay (lê por coordenadas na página, não por texto corrido, porque
nomes de estabelecimento longos quebram em várias linhas e bagunçam a ordem se
lidos ingenuamente). Se o PicPay mudar esse layout no futuro, ou se você quiser
adaptar pra outro banco/carteira digital, esse é o arquivo a ajustar — o restante
do projeto (banco de dados, IA, gráficos) é agnóstico ao formato de origem.

## Problemas conhecidos / solução de problemas

| Sintoma | Causa provável | Solução |
|---|---|---|
| Erro ao copiar o modelo pro pendrive ("arquivo muito grande") | Pendrive em FAT32 (limite de 4 GB/arquivo) | Reformate em exFAT |
| `llama-server.exe` — "Imagem Incorreta", erro `0xc0e90002` | SmartScreen ou Smart App Control bloqueando binário não assinado | Veja passo 6 da instalação |
| IA responde vazio ou em campo errado | Modelo colocando a resposta em `reasoning_content` em vez de `content` | Já tratado em `llm_client.py` (fallback automático) |
| IA trava repetindo a mesma consulta em loop | Modelos menores não lidam bem com "continue ou pare?" em várias rodadas | Já resolvido pela arquitetura de 2 fases (planejamento único + síntese) |
| Respostas saem em inglês / cortadas no meio | Modo de "pensamento" (thinking) do modelo consumindo o limite de tokens | Já tratado via `--reasoning off --reasoning-budget 0` no `Iniciar.bat` |
| Categoria não encontrada / soma zerada | Comparação de categoria sensível a maiúscula/acento | Já tratado em `db.py` (`resolver_categoria`) |
| Instabilidade/crash depois de algumas respostas com Qwen3.5 | Bug conhecido do llama.cpp com a arquitetura "Gated Delta Net" | Use Qwen3 (não 3.5) — veja passo 3 |

## Estrutura do projeto

```
FinancIA/
├── app/
│   ├── main.py            # loop principal do terminal
│   ├── db.py               # banco de dados (SQLite) — toda a matemática mora aqui
│   ├── tools.py             # ferramentas que a IA pode chamar + prompts
│   ├── llm_client.py        # comunicação HTTP com o llama-server
│   ├── pdf_import.py        # leitor de extrato em PDF (PicPay)
│   ├── csv_import.py        # leitor de extrato em CSV (PicPay)
│   ├── extrato_utils.py     # funções compartilhadas entre os dois leitores
│   ├── charts.py            # geração de gráficos (matplotlib)
│   ├── categorias.json      # regras de categorização (editável)
│   └── grammars/            # gramáticas GBNF (força saída da IA em JSON válido)
├── bin/                     # motor de IA (você baixa — veja instalação)
├── models/                  # modelo de IA em .gguf (você baixa)
├── python/                  # Python portátil (você baixa)
├── data/                    # seu banco de dados pessoal (nunca vai pro git)
├── graficos/                # gráficos gerados
├── Iniciar.bat
├── Instalar_Dependencias.bat
└── requirements.txt
```

## Contribuindo

Pull requests são bem-vindos — seja pra suportar outros bancos/carteiras digitais,
melhorar a categorização, adicionar novas ferramentas de análise, ou qualquer
outra coisa. O projeto inteiro roda com duas dependências Python (`pdfplumber`,
`matplotlib`) de propósito, pra manter a instalação simples.

## Licença

MIT — veja [LICENSE](LICENSE).
