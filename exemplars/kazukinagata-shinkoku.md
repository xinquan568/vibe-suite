---
slug: kazukinagata-shinkoku
repo: kazukinagata/shinkoku
audited: 2026-05-13
commit_sha: e610b30c549ccc954717561c87004b6079d03f77
score: 94
exemplifies:
  - R01
  - R04
  - R06
  - R07
  - R08
---

# Exemplar: kazukinagata/shinkoku

**Score**: 94/100  |  **Date**: 2026-05-13  |  **Commit**: `e610b30c549ccc954717561c87004b6079d03f77`

A 24-skill Claude Code plugin for Japanese individual tax filing (確定申告) that demonstrates tight trigger descriptions, concrete calculation examples with JSON I/O, explicit scope boundaries, and decision-tree procedure bodies throughout.

## Per-rule evidence

### R01 — No vague quantifiers

Tax calculations require precise rounding rules, and this repo enforces them at both the CLAUDE.md layer and inside skill bodies. Rather than "round appropriately" or "apply the relevant rules," every rounding case cites the exact formula and the controlling statute.

> Real quote from `CLAUDE.md` (rounding table, 所得税 section):
>
> ```
> | 課税所得 | 1,000円未満切捨て `(amount // 1_000) * 1_000` | 国税通則法118条 |
> | 復興特別所得税 | 1円未満切捨て `tax * 21 // 1000` | 復興財源確保法13条 |
> | 申告納税額（納付の場合のみ） | 100円未満切捨て `(amount // 100) * 100` | 国税通則法119条 |
> | 還付金 | 1円単位（切捨てなし） | 国税通則法120条 |
> ```

Each row gives the operand, the integer-arithmetic expression, and the law. A reader can re-implement the rule from the table alone — no ambiguous modifier remains.

### R04 — Description as trigger

Every skill frontmatter description combines an English "use when" sentence with a bilingual trigger-phrase list. The model can route to the right skill from either a JP or EN user utterance without guesswork.

> Real quote from `skills/gather/SKILL.md:3-9`:
>
> ```yaml
> description: >
>   This skill should be used when the user needs to know what documents to collect
>   for their tax filing, wants a checklist of required documents, or asks where to
>   obtain specific tax documents. Trigger phrases include: "必要書類", "書類を集める",
>   "何を準備すればいい", "源泉徴収票はどこで", "書類チェックリスト",
>   "確定申告に必要なもの", "書類収集", "準備するもの".
> ```

Eight JP trigger phrases plus an EN scenario description fit in six lines. The same pattern repeats across `assess`, `consumption-tax`, `reading-receipt`, and 20 other skills — it is a consistent house convention, not a one-off.

### R06 — Runnable examples

The `consumption-tax` skill includes a complete CLI invocation with a concrete JSON input and a field-by-field output description. A model executing the skill does not need to infer argument names or output shape.

> Real quote from `skills/consumption-tax/SKILL.md:102-132`:
>
> ```bash
> shinkoku tax calc-consumption --input consumption_input.json
> ```
> ```json
> {
>   "fiscal_year": 2025,
>   "method": "special_20pct",
>   "taxable_sales_10": 5500000,
>   "taxable_sales_8": 0,
>   "taxable_purchases_10": 0,
>   "taxable_purchases_8": 0,
>   "simplified_business_type": null,
>   "interim_payment": 0
> }
> ```
> Output (ConsumptionTaxResult):
> - `method`: 適用した申告方法
> - `taxable_sales_total`: 課税売上高合計（税込、表示用）
> - `taxable_base_10`: 課税標準額（10%分、税抜、1,000円切捨て）
> - `net_tax`: 差引税額（100円切捨て、正の場合のみ）
> - `total_due`: 合計納付税額（負 = 還付）

The example uses real-world amounts (5,500,000 yen) rather than placeholder 0s, and the output description annotates each field with its rounding rule — bridging the CLI docs and the CLAUDE.md rounding table.

### R07 — Scope notes

The `assess` skill places its out-of-scope statement as a named step in the numbered procedure, rather than burying it in a disclaimer at the bottom. The model encounters the boundary at the moment it would otherwise proceed into unsupported territory.

> Real quote from `skills/assess/SKILL.md:262-266`:
>
> ```
> ## ステップ2.5: （対象外）分離課税の申告要否判定
>
> 分離課税（株式・FX の第三表）の計算・帳票生成は対象外。
> 株式取引・FX取引がある場合は税理士への相談を案内する。
> 仮想通貨は雑所得（総合課税）として所得税スキルで取り扱う。
> ```

The section header "(対象外)" signals exclusion without hiding what is covered. The third sentence redirects crypto to the correct in-scope path, so the model hands off rather than silently skipping.

The `capabilities` skill makes the same point at the persona level with a two-value table (`Full` / `Out`) plus explicit reasoning for each `Out` row:

> Real quote from `skills/capabilities/SKILL.md:14-37`:
>
> ```
> | 株式投資家（分離課税） | Out | 株式譲渡所得・配当の分離課税には対応していません |
> | FXトレーダー | Out | 先物取引に係る雑所得等には対応していません |
> | 不動産所得 | Out | 不動産所得用の決算書・申告に対応していません |
> ```

Each `Out` row is its own scope note: type of user, boundary status, and one-line reason.

### R08 — Patterns over theory

The `assess` skill encodes the legal filing-obligation logic as a concrete decision tree with branch labels, not as a prose summary of tax law. The model reads the tree and follows it; no tax knowledge is assumed.

> Real quote from `skills/assess/SKILL.md:213-244`:
>
> ```
> Q1. 給与所得者ですか？
> ├── Yes → Q2へ
> └── No → Q5へ
>
> Q2. 給与収入は2,000万円を超えますか？
> ├── Yes → 【確定申告必要】（所得税法第121条第1項）
> └── No → Q3へ
>
> Q3. 給与を2か所以上から受けていますか？
> ├── Yes → 主たる給与以外の収入が20万円を超えるか確認 → Q4へ
> └── No → Q4へ
>
> Q4. 給与所得・退職所得以外の所得が20万円を超えますか？
> ├── Yes → 【確定申告必要】（所得税法第121条第1項第2号）
> └── No → Q6へ
> ```

Each terminal node is a bracketed verdict with a statute citation. The pattern repeats for the consumption-tax and residential-tax flowcharts in the same skill, and again in `consumption-tax/SKILL.md` for the method-selection decision.

## Worth adopting

**Pattern: Progress handoff files.** Every skill ends with a "引継書の出力" (handoff output) section that instructs the model to write a YAML-frontmatter progress file to `.shinkoku/progress/<step>-<skill>.md` before finishing. Evidence: `skills/assess/SKILL.md:364-439`, `skills/gather/SKILL.md:282-334`, `skills/consumption-tax/SKILL.md:265-331`. The handoff file carries the step number, skill name, status (`completed`/`skipped`), date, and the result fields that the next skill in the pipeline needs. The next skill opens the relevant handoff file before asking the user anything. Why it would be a useful rule: in multi-step workflows where each skill hands off to the next, writing an explicit intermediate state file lets subsequent skills resume without re-asking questions the user already answered, and survives context compaction between sessions.

**Pattern: Dual-context verification for ambiguous extraction.** The `reading-receipt` skill instructs the model to run two independent subagent reads of the same image and reconcile them before accepting a result. Evidence: `skills/reading-receipt/SKILL.md:22-46`. The fallback section (single-context, no subagents) explicitly marks itself with a ⚠ and requires the model to ask for user confirmation. Why it would be a useful rule: for skills that extract structured data from noisy inputs (OCR, document parsing), encoding the reconciliation protocol directly in the skill body prevents silent data errors without requiring the calling context to know about the verification strategy.
