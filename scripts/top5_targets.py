"""Pin the public P3 fifth-place references for the research plan."""
import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
API = 'https://api.virtualembryo.ai/challenge'
BOARDS = ('T1:test', 'T2:heart:test_extrap', 'T2:embryo:test_interp', 'T3:bcatenin')
TEAM = 'YOUR_TEAM'


def standings(board, track):
    query = urlencode({'task': board.split(':')[0], 'split': 'test', 'board': board, 'track': track})
    with urlopen(f'{API}/leaderboard?{query}', timeout=20) as response:
        data = json.load(response)
    rows = [row for row in data['rows'] if row['track'] == track]
    return data['updated_at'], rows


def main():
    references = {}
    for board in BOARDS:
        stamp, agent = standings(board, 'agent')
        _, human = standings(board, 'human')
        ours = next(row for row in agent if row['team'] == TEAM)
        references[board] = {
            'updated_at': stamp, 'incumbent': ours['headline'], 'incumbent_metrics': ours['metrics'],
            'agent_fifth': agent[4]['headline'], 'human_fifth': human[4]['headline'],
            'agent_gap': round(agent[4]['headline'] - ours['headline'], 4),
        }
    path = ROOT / 'results/top5_targets.json'
    path.write_text(json.dumps(references, indent=2) + '\n')
    for board, result in references.items():
        print(board, result['incumbent'], result['agent_fifth'], result['human_fifth'], result['agent_gap'])


if __name__ == '__main__':
    main()
