#!/usr/bin/env bash
# Re-encrypt all held-out files and .env with a new passphrase (typed, never stored). Updates the bio21 backup.
set -eu
cd "$(dirname "$0")/.."
if pgrep -f "claude -p|codex exec|opencode run" > /dev/null; then echo "refusing: agents are running"; exit 1; fi
read -r -s -p "Current passphrase: " OLD; echo
read -r -s -p "New passphrase (long, not reused): " NEW; echo
read -r -s -p "Repeat new passphrase: " NEW2; echo
[ "$NEW" = "$NEW2" ] || { echo "mismatch"; exit 1; }
export OLD NEW
for f in data/holdout.enc/*.enc; do
  openssl enc -d -aes-256-cbc -pbkdf2 -iter 300000 -pass env:OLD -in "$f" | \
    openssl enc -aes-256-cbc -pbkdf2 -iter 300000 -salt -pass env:NEW -out "$f.new"
  openssl enc -d -aes-256-cbc -pbkdf2 -iter 300000 -pass env:NEW -in "$f.new" > /dev/null && mv "$f.new" "$f" && echo "re-keyed $f"
done
unset OLD NEW NEW2
rsync -a data/holdout.enc/ bio21.cluster.example:/scratch/user/ve-holdout-backup/ && echo "backup updated"
