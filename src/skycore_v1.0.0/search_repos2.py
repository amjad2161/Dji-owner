import urllib.request
import json

repos = [
    ("gym-pybullet-drones", "gym-pybullet-drones+RL+UAV"),
    ("aerostack", "aerostack+multi-robot+UAV"),
    ("EvoDrone", "EvoDrone+UAV+evolution"),
    ("px4+trajectory", "px4+trajectory+planning"),
    ("multi-UAV-simulation", "multi-UAV+simulation+swarm")
]

for name, query in repos:
    try:
        url = f'https://api.github.com/search/repositories?q={query}&sort=stars&per_page=3'
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        resp = urllib.request.urlopen(req)
        data = json.loads(resp.read())
        print(f"\n=== {name} ===")
        for item in data.get('items', [])[:3]:
            desc = item.get('description', '')
            if desc:
                desc = desc.encode('ascii', 'ignore').decode('ascii')
            print(f"{item['full_name']} ({item['stargazers_count']} stars)")
            print(f"  {item['html_url']}")
            print(f"  {desc[:80]}")
    except Exception as e:
        print(f"Error for {name}: {e}")