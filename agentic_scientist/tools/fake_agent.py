"""Harness smoke-test agent (role cli 'fake'): no LLM, no quota. Never used in a real configuration.

  fake_agent.py <cwd> <label>      (prompt in $FAKE_PROMPT)

ideate: writes hypothesis.json into the cycle directory and appends a documented no-op line to the board file, so
the candidate differs from its parent but predicts identically (the race must then reject it).
review / distill: print a JSON verdict. plan: writes plan.md. Everything else: prints a short message.
"""
import json
import os
import re
import sys
from pathlib import Path

cwd, label = Path(sys.argv[1]), sys.argv[2]
prompt = os.environ.get('FAKE_PROMPT', '')


def result(text):
    print(json.dumps({'type': 'result', 'result': text}))


m = re.search(r'own the \*\*(\w+)\*\* board', prompt)
board = m.group(1) if m else 'heart'
if label == 'ideate' and 'SMOKE-NO-HYPOTHESIS' in prompt:
    # a research session that works but ends without hypothesis.json (the harness must run the wrap-up call)
    cdir = cwd.parent if cwd.name == 'ws' else cwd
    (cdir / 'analysis').mkdir(exist_ok=True)
    (cdir / 'analysis' / 'screen.txt').write_text('smoke screen: variant A +0.3, variant B -0.1\n')
    for i in range(12):
        print(json.dumps({'type': 'item.completed', 'item': {'id': f'item_{i}', 'type': 'agent_message',
                                                             'text': f'smoke research step {i}: screening variant A'}}))
        print(json.dumps({'type': 'item.completed', 'item': {'id': f'cmd_{i}', 'type': 'command_execution',
                          'command': f'python analysis/screen.py --step {i}', 'aggregated_output': 'variant A +0.3'}}))
    print(json.dumps({'type': 'item.started', 'item': {'id': 'cmd_last', 'type': 'command_execution',
                                                       'command': 'python analysis/long_sweep.py'}}))
    sys.exit(0)
if label.startswith('ideate'):
    cdir = cwd.parent if cwd.name == 'ws' else cwd
    hyp = dict(title=f'smoke no-op on {board}', claim='no metric moves', mechanism='none (harness smoke test)',
               evidence=[{'source': 'https://example.org/a', 'finding': 'smoke'},
                         {'source': 'https://example.org/b', 'finding': 'smoke'}],
               change_plan='append a comment', target_boards=[board], expected_gain=0.0, risk='none', complexity=1,
               generalisation_argument='none', metric_signature={'board': board, 'mmd_u': '='}, origin='diagnostic')
    (cdir / 'hypothesis.json').write_text(json.dumps(hyp, indent=1))
    f = cwd / f'{board}.py'
    if f.exists():
        f.write_text(f.read_text() + '\n# smoke test: documented no-op line\n')
        (cwd / 'CHANGES.md').write_text('smoke test: appended a comment\n')
    result(hyp['title'])
elif label.startswith('review'):
    result(json.dumps({'verdict': 'promote', 'issues': [], 'notes': 'smoke'}))
elif label.startswith('distill'):
    result(json.dumps({'lesson': 'smoke test cycle', 'tags': {'boards': [board]}, 'mechanism': 'none'}))
elif label.startswith('plan'):
    (cwd / 'plan.md').write_text('# Plan (smoke)\n- heart: replicate the public heart recipe first.\n')
    result('plan written')
elif label.startswith('curate'):
    result('```markdown\n## Confirmed\n- (smoke)\n```')
else:
    result('nothing to do')
