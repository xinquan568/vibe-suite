# Re-Audit: kubesphere/kubesphere

**Date**: 2026-05-07  |  **Before**: `1681475` (89/100)  |  **After**: `00d94f4` (—)

## Summary

| Outcome | Count |
|---------|------:|
| fixed — our PR merged | 5 |
| fixed — upstream, not via our PR | 13 |
| newly introduced (regressions) | 3 |

## Original findings — verification

| # | File | Line | Rule | Pattern | Outcome | PR |
|---|------|------|------|---------|---------|----|
| 1 | `skills/kubesphere-devops-credentials/SKILL.md` | 111 | BUG-incorrect-api-example | `wrong-credential-type` | fixed — our PR merged | #6632 |
| 2 | `skills/kubesphere-fluid/SKILL.md` | 410 | BUG-yaml-syntax-error | `unclosed-string-literal` | fixed — our PR merged | #6633 |
| 3 | `skills/whizard-logging/SKILL.md` | 106 | BUG-incorrect-step-reference | `wrong-step-reference` | fixed — our PR merged | #6634 |
| 4 | `skills/kubesphere-devops-pipeline/SKILL.md` | 323 | BUG-broken-markdown | `unclosed-bold-marker` | fixed — our PR merged | #6635 |
| 5 | `skills/kubesphere-devops-overview/SKILL.md` | 92 | BUG-duplicate-section | `duplicate-content-block` | fixed — our PR merged | #6636 |
| 6 | `config/ks-core/charts/ks-crds/scripts/post-delete.sh` | 33 | SEC-xargs-shell-injection | `xargs-sh-c-interpolation` | fixed — upstream, not via our PR |  |
| 7 | `skills/whizard-telemetry/scripts/generate-config.sh` | 354 | SEC-plaintext-credential-output | `credential-echoed-to-stdout` | fixed — upstream, not via our PR |  |
| 8 | `skills/kubesphere-core/scripts/ks_api.py` | 28 | SEC-insecure-token-storage | `token-file-no-chmod` | fixed — upstream, not via our PR |  |
| 9 | `skills/kubesphere-multi-tenant-management/scripts/ks_api.py` | 28 | SEC-insecure-token-storage | `token-file-no-chmod` | fixed — upstream, not via our PR |  |
| 10 | `skills/kubesphere-devops-tenant/SKILL.md` | 130 | SEC-hardcoded-credential | `hardcoded-password-in-docs` | fixed — upstream, not via our PR |  |
| 11 | `skills/kubesphere-devops-argocd/SKILL.md` | 640 | R25 | `duplicate-content` | fixed — upstream, not via our PR |  |
| 12 | `skills/kubesphere-devops-pipeline/SKILL.md` | 1277 | R25 | `duplicate-content` | fixed — upstream, not via our PR |  |
| 13 | `skills/kubesphere-devops-overview/SKILL.md` | — | R25 | `duplicate-heading` | fixed — upstream, not via our PR |  |
| 14 | `skills/kubesphere-devops-tenant/SKILL.md` | 247 | R25 | `duplicate-header-in-example` | fixed — upstream, not via our PR |  |
| 15 | `skills/kubesphere-devops-tenant/SKILL.md` | 130 | R15 | `hardcoded-credential-in-docs` | fixed — upstream, not via our PR |  |
| 16 | `skills/kubesphere-volcano/SKILL.md` | 713 | R05 | `vague-quantifier` | fixed — upstream, not via our PR |  |
| 17 | `skills/kubesphere-multi-tenant-management/scripts/ks_api.py` | — | CC-duplicate-file | `verbatim-duplicate-script` | fixed — upstream, not via our PR |  |
| 18 | `skills/whizard-telemetry/SKILL.md` | — | CC-undocumented-dependency | `implicit-cross-extension-dependency` | fixed — upstream, not via our PR |  |

## Findings introduced since audit

These findings appear in the re-audit but were not in the original audit. They may be true regressions (new commits introduced them) or artifacts of scoring drift.

| # | File | Line | Rule | Pattern | Description |
|---|------|------|------|---------|-------------|
| 1 | `skills/kubesphere-volcano/SKILL.md` | 715 | R24 | `vague-quantifier-appropriate` | Vague quantifier 'appropriate' appears 3 times at lines 715, 733, 790 (penalty -2 each = -6 total) |
| 2 | `skills/kubesphere-devops-pipeline/SKILL.md` | 185 | R24 | `vague-quantifier-properly` | Vague quantifier 'properly' appears 1 time at line 185 (penalty -2) |
| 3 | `skills/kubesphere-devops-tenant/SKILL.md` | 49 | CC-broken-relative-path | `broken-relative-path` | Lines 49 and 75 reference '../../core/kubesphere-core/SKILL.md'; kubesphere-core skill exists at 'skills/kubesphere-core/SKILL.md', expected relative path is '../kubesphere-core/SKILL.md' |

