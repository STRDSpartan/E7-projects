#!/usr/bin/env bash
# Prépare l'environnement de dev pour les sessions Claude Code sur le web
# (conteneur éphémère). En local, ne fait rien : le développeur gère son venv.
set -euo pipefail
[ "${CLAUDE_CODE_REMOTE:-}" = "true" ] || exit 0

cd "$CLAUDE_PROJECT_DIR"
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
.venv/bin/pip install -q -e ".[dev]" playwright >/dev/null
echo "export PATH=\"$CLAUDE_PROJECT_DIR/.venv/bin:\$PATH\"" >> "${CLAUDE_ENV_FILE:-/dev/null}"
chrome=$(ls -d /opt/pw-browsers/chromium-*/chrome-linux*/chrome 2>/dev/null | head -1 || true)
if [ -n "$chrome" ]; then
  echo "export E7_CHROMIUM_PATH=\"$chrome\"" >> "${CLAUDE_ENV_FILE:-/dev/null}"
fi
