---
slug: pe-menezes-fin-claude-plugin
repo: pe-menezes/fin-claude-plugin
audited: 2026-05-13
commit_sha: 8ddfa3bb22fdde71b8fd2ceb37c736f29f2c221b
score: 94
exemplifies:
  - R04
  - R07
  - R08
  - R11
  - R12
---

# Exemplar: pe-menezes/fin-claude-plugin

**Score**: 94/100  |  **Date**: 2026-05-13  |  **Commit**: `8ddfa3bb22fdde71b8fd2ceb37c736f29f2c221b`

A six-skill personal-finance plugin for FIN App, notable for skill descriptions that function as dispatch tables and scope sections that eliminate routing ambiguity across the entire collection.

## Per-rule evidence

### R04 — Description as trigger

Every skill in this collection packs its description with natural-language user phrases and named edge cases rather than a label. The `lancar` skill leads with six quoted user utterances and names the non-obvious sub-cases (dinheiro vivo, câmbio, balance adjustment) that distinguish it from `extrato` and `fatura`:

> Real quote from `skills/lancar/SKILL.md:2-10`:
>
> ```
> description: >
>   Lançamento avulso de transação no FIN App. Entende instruções em linguagem
>   natural ("lança 45 no mercado, débito [conta]", "20 conto no pão, dinheiro",
>   "saquei 200 no Itaú", "recebi 4mil do cliente X", "vendi $100 e veio R$540",
>   "tô com $487 na carteira"), aplica regras aprendidas de Estabelecimentos.md,
>   trata dinheiro vivo, saque, câmbio USD/BRL e ajuste de saldo corretamente,
>   sempre confirma em uma linha antes de criar. Aprende e atualiza memória.
> ```

Six quoted phrases in 481 characters. The `extrato` and `fatura` descriptions follow the same pattern — `extrato` names its five-format priority order (`OFX > CSV > CNAB 240 > texto colado > PDF`) and its idempotency mechanism; `fatura` names the FIN tool it calls (`fin_fatura_transacoes`) and why (`NÃO via despesa avulsa, regra de negócio do FIN`). A model dispatching across this collection can make the correct choice on description alone without reading skill bodies.

### R07 — Scope note when related skills exist

Every skill opens with two sections: `## Quando usar` followed immediately by `## Quando NÃO usar`. The negative section names the exact alternative skill for each out-of-scope case — not a generic "see other skills" note:

> Real quote from `skills/extrato/SKILL.md:19-27`:
>
> ```
> ## Quando NÃO usar
>
> - Lançamento de **uma única transação** → use `/financeiro:lancar`
> - **Fatura de cartão de crédito** → use `/financeiro:fatura` (fluxo diferente, lança via `fin_fatura_transacoes`)
> - MCP do FIN não tá instalado → `/financeiro:instalar-fin-mcp`
> - Plugin nunca rodou nessa máquina → `/financeiro:onboarding` primeiro
> ```

The pattern is consistent across all six skills with context-appropriate redirects: `conciliar` sends "lançar transações novas" to `lancar`, `extrato`, or `fatura`; `fatura` redirects "pagamento sem lançamento" to a direct tool call. No skill leaves an out-of-scope case as "not applicable" — every case has a named destination. This makes the collection self-routing: the model is never left guessing when a request crosses skill boundaries.

### R08 — Patterns over theory

The agent body replaces dispatch prose with a 20-row routing table mapping natural-language intents to specific skill invocations and FIN tools:

> Real quote from `agents/financeiro.md:104-114`:
>
> ```
> | Intenção da pessoa | Fluxo |
> |---|---|
> | "lança X reais em Y" / "gastei X" / "recebi X" / "transferi X de A pra B" | `/financeiro:lancar` |
> | "vendi $X e veio R$Y" / "comprei $X por R$Y" / "câmbio" | `/financeiro:lancar` (caso especial: câmbio via `fin_cambio`) |
> | "tô com $X na carteira" / "agora tenho $X" / "achei mais $X" | `/financeiro:lancar` (caso especial: ajuste saldo via `fin_ajustar_saldo_conta`) |
> | "gastei $X no [lugar]" / "paguei $X" (em conta USD) | `/financeiro:lancar` (caso USD: `fin_criar_despesa` com `original_amount_cents` + `original_currency: "USD"`) |
> ```

The `lancar` skill extends the same approach to currency parsing: instead of a rule for "detect informal Brazilian Portuguese numbers," it provides a lookup table:

> Real quote from `skills/lancar/SKILL.md:65-76`:
>
> ```
> **Notação numérica BR:**
> - "20 conto" / "20 mango" / "20 pila" = R$20
> - "4 mil" / "4k" = R$4.000
> - "500 reais" / "500" = R$500
> - Vírgula é decimal: "45,50" = R$45,50
>
> **Notação USD:**
> - "$100" / "100 dólares" / "100 dolar" / "100 USD" = US$100
> - "$1.5k" / "1500 dólares" = US$1.500
> - Quando a pessoa só fala "100" sem moeda, **assume BRL** (default)
> - Quando a pessoa usa `$` no início, **assume USD**
> - Em caso de dúvida, pergunta ("100 reais ou 100 dólares?")
> ```

Every ambiguous case has a defined resolution. The model never has to infer behavior from a description — the table is the behavior.

### R11 — Tools follow least-privilege

The fallback skill `instalar-fin-mcp` declares only three tools:

> Real quote from `skills/instalar-fin-mcp/SKILL.md:10-11`:
>
> ```
> allowed-tools: Read Write Bash
> ```

It uses `Bash` to run `node --version` and `claude mcp list`. It uses `Write` to create config files. It uses `Read` to inspect existing configs. That's the complete tool surface the body references. Compare to `skills/lancar/SKILL.md:11`, which adds `Edit Glob Grep` (needed to update `.md` memory files and search the `Estabelecimentos.md` table) but omits `Bash` — the skill has no shell commands. The `allowed-tools` lists in this repo are written to match the actual calls in each skill body, not padded for hypothetical future use.

### R12 — Output format defined in body

The `conciliar` skill specifies its reconciliation report as a complete ASCII template with every section header, column structure, and summary row:

> Real quote from `skills/conciliar/SKILL.md:100-134`:
>
> ```
> === CONCILIAÇÃO: [conta] — Período YYYY-MM-DD a YYYY-MM-DD ===
>
> ✓ BATEM CERTINHO (47)
> | Data       | Valor    | Descrição (FIN)        | Status |
>
> ⚠ BATEM COM LEVE DIFERENÇA (3)
> | Data FIN   | Data Ext   | Valor    | Descrição (FIN)  | Descrição (Ext) | Diferença    |
>
> ❌ SÓ NO FIN — não tem no extrato (5)
> | Data       | Valor    | Descrição              | Categoria         | Ação? |
>
> ❌ SÓ NO EXTRATO — não tem no FIN (8)
> | Data       | Valor    | Descrição              | Ação? |
>
> 🚨 SUSPEITO DE DUPLICATA NO FIN (1)
> | Data       | Valor   | Descrição     | Transações no FIN matchando |
>
> === RESUMO ===
> - 47 ✓ batem
> - 3 ⚠ leve diferença
> - 5 ❌ só no FIN
> - 8 ❌ só no extrato
> - 1 🚨 suspeito de duplicata
> - Saldo do período: FIN=R$X / Externo=R$Y / Diferença=R$Z
> ```

The `lancar` skill applies the same discipline to the one-line confirmation: `skills/lancar/SKILL.md:235-249` specifies the exact format for expense, income, transfer, and withdrawal confirmations including slot order. Any two invocations produce structurally identical output, which is what makes these skills verifiable at a glance.

## Worth adopting

**Pattern: Standardized prerequisites checklist before the main flow.** Every skill opens its body with a `## Pré-requisitos` section listing ordered system checks (MCP responds, config file exists, memory files exist, documentation read this session) before the main numbered steps begin. Evidence: `skills/conciliar/SKILL.md:29-33`, `skills/lancar/SKILL.md:27-33`, `skills/extrato/SKILL.md:29-33`. Why it would be a useful rule: skills in a multi-skill plugin often share session-level setup; a named prerequisites section gives the model a checklist it can skip if already completed this session, preventing redundant reads without silently omitting required state.

**Pattern: Numbered antipattern list as a closing section.** Every skill ends with `## Erros comuns que você deve evitar` — a numbered list of concrete wrong actions with the correct alternative on the same line. Evidence: `skills/lancar/SKILL.md:394-412` (13 entries), `skills/extrato/SKILL.md:398-410` (10 entries), `skills/fatura/SKILL.md:406-421` (14 entries). Why it would be a useful rule: R03 covers positive framing in the body; the closing antipattern list addresses a complementary need — capturing failure modes that look locally correct (e.g., "lançar saque como despesa" when it should be a transfer) but diverge from system-wide invariants. Structuring these as a numbered closing section keeps them discoverable without scattering corrective notes throughout the step-by-step flow.
