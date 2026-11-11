#!/usr/bin/env bash
# Configure pip to use Tsinghua mirror (user-level, persistent)
set -euo pipefail

if [[ "$(uname -s)" == "Darwin" ]]; then
  PIP_DIR="$HOME/Library/Application Support/pip"
else
  PIP_DIR="$HOME/.config/pip"
fi
mkdir -p "$PIP_DIR"

cat > "$PIP_DIR/pip.conf" <<'EOF'
[global]
index-url = https://pypi.tuna.tsinghua.edu.cn/simple
trusted-host = pypi.tuna.tsinghua.edu.cn
timeout = 120
EOF

echo "pip mirror -> Tsinghua ($PIP_DIR/pip.conf)"
python -m pip config list
