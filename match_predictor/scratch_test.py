import predictor
config = predictor.load_config()
live = predictor.fetch_live_event_data(config['worlds_event_id'], config['worlds_division_id'])
print('Live matches count:', len(live))
played = []
for m in live:
  ad = {a.get('color'): a for a in m.get('alliances', [])}
  r = ad.get('red', {}).get('score', 0)
  b = ad.get('blue', {}).get('score', 0)
  if r != 0 or b != 0:
    played.append(m['name'])
print('Played with scores:', played)

played_started = []
for m in live:
  if m.get('started'):
    played_started.append(m['name'])
print('Played with started:', played_started)
