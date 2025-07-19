#!/bin/bash
# Pull latest payloads and scripts from GitHub

REPO_DIR="/opt/p4wnp1"
GIT_URL="https://github.com/quasialex/p4wnp1-zero2w.git"

echo "[+] Checking for updates in $REPO_DIR..."
cd "$REPO_DIR"

if [ ! -d ".git" ]; then
  echo "[!] Git not initialized. Initializing now..."
  git init
  git remote add origin "$GIT_URL"
  git pull origin master
else
  git stash save "autoupdate-$(date +%Y%m%d-%H%M%S)"
  git pull origin master
  git stash pop || true
fi

chmod -R +x "$REPO_DIR/payloads" "$REPO_DIR/hooks"
echo "[+] Payloads and hooks updated."
