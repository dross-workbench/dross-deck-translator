import argparse
from pathlib import Path
from dross_server.vocabulary import VocabularyStore

p = argparse.ArgumentParser()
p.add_argument('--output', required=True)
p.add_argument('--game-id')
args = p.parse_args()
data = Path(__file__).parent/'.local/data'
Path(args.output).write_text(VocabularyStore(data).export(args.game_id), encoding='utf-8')
print('Vocabulary exported. Keep the file private; it contains saved game dialogue.')
