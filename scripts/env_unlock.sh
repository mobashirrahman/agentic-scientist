#!/usr/bin/env bash
# Decrypt the challenge API key into .env for a manual API session; `scripts/env_lock.sh` removes it again.
# Never leave .env in place while AgenticScientist agents are running.
cd "$(dirname "$0")/.."
if pgrep -f "claude -p|codex exec|opencode run" > /dev/null; then echo "refusing: agents are running"; exit 1; fi
read -r -s -p "Passphrase: " P; echo
P="$P" openssl enc -d -aes-256-cbc -pbkdf2 -iter 300000 -pass env:P -in data/holdout.enc/dotenv.enc -out .env && chmod 600 .env && echo ".env unlocked (run scripts/env_lock.sh when done)"
