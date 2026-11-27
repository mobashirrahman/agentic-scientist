#!/usr/bin/env python3
"""Usage-limit-aware wrapper around the `headless` CLI for ShinkaEvolve.

Set:  SHINKA_HEADLESS_COMMAND="python /path/shinka_ve/limit_wrapper.py"
      SHINKA_HEADLESS_TIMEOUT=25200   (7 h, longer than the maximum wait below)

Policy (fixed before a run; part of the locked configuration):
 1. Run the requested agent.
 2. If the failure output looks like a subscription usage/rate limit, try the
    pre-declared fallback agent once (codex <-> claude, each with its own model).
 3. If both are limited, sleep WAIT_STEP seconds and retry, up to MAX_WAIT total.
 Every limit event, fallback and wait is appended to VE_LIMIT_LOG as JSON lines.
Non-limit failures are passed through unchanged so Shinka handles them normally.
"""
import json
import os
import re
import shlex
import subprocess
import sys
import time

HEADLESS = shlex.split(os.environ.get('VE_HEADLESS_BIN', 'npx -y @roberttlange/headless'))
LOG = os.environ.get('VE_LIMIT_LOG', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'limit_events.jsonl'))
WAIT_STEP = int(os.environ.get('VE_LIMIT_WAIT_STEP', '600'))
MAX_WAIT = int(os.environ.get('VE_LIMIT_MAX_WAIT', str(6 * 3600)))
# Fallback models are fixed at lock time via env, e.g. VE_FALLBACK_CODEX_MODEL=gpt-...
FALLBACK = {'codex': 'claude', 'claude': 'codex'}
LIMIT = re.compile(r'usage limit|rate.?limit|\b429\b|quota|too many requests|limit reached|'
                   r'try again (at|in)|resets? (at|in)|out of credits|credit balance', re.I)


def log(**event):
    event['time'] = time.strftime('%Y-%m-%dT%H:%M:%S')
    with open(LOG, 'a') as f:
        f.write(json.dumps(event) + '\n')


def swap_agent(args, agent):
    """Replace the agent and its model/effort with the fallback's pre-declared values."""
    out, skip = [], False
    for i, a in enumerate(args):
        if skip:
            skip = False
            continue
        if i == 0:
            out.append(agent)
        elif a in ('--model', '--reasoning-effort', '--effort'):
            skip = True
        else:
            out.append(a)
    model = os.environ.get(f'VE_FALLBACK_{agent.upper()}_MODEL')
    effort = os.environ.get(f'VE_FALLBACK_{agent.upper()}_EFFORT')
    if model:
        out += ['--model', model]
    if effort:
        out += ['--reasoning-effort', effort]
    return out


def run(args):
    p = subprocess.run(HEADLESS + args, capture_output=True, text=True)
    return p, p.returncode != 0 and bool(LIMIT.search(p.stderr + '\n' + p.stdout))


def main():
    args = sys.argv[1:]
    if not args or args[0].startswith('-') or args[0] not in FALLBACK:
        os.execvp(HEADLESS[0], HEADLESS + args)
    waited = 0
    while True:
        p, limited = run(args)
        if not limited:
            break
        log(event='limit', agent=args[0], tail=(p.stderr or p.stdout)[-300:])
        alt = swap_agent(args, FALLBACK[args[0]])
        p, limited = run(alt)
        if not limited:
            log(event='fallback_ok', agent=alt[0])
            break
        log(event='both_limited', waited=waited)
        if waited >= MAX_WAIT:
            log(event='gave_up', waited=waited)
            break
        time.sleep(WAIT_STEP)
        waited += WAIT_STEP
    sys.stdout.write(p.stdout)
    sys.stderr.write(p.stderr)
    sys.exit(p.returncode)


if __name__ == '__main__':
    main()
