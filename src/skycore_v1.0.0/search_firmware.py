import urllib.request
import json

repos = [
    ("px4_firmware", "PX4/Firmware+px4"),
    ("ardupilot", "ArduPilot/ardupilot"),
    ("cleanflight", "cleanflight/cleanflight"),
    ("betaflight", "betaflight/betaflight"),
    ("inav", "inavflight/inav"),
    ("px4_autorun", "PX4/Autopilot"),
    ("mavlink", "mavlink/mavlink"),
    ("qgroundcontrol", "mavlink/QGroundControl")
]

for name, query in repos:
    try:
        url = f'https://api.github.com/search/repositories?q={query}&sort=stars&per_page=3'
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        resp = urllib.request.urlopen(req)
        data = json.loads(resp.read())
        print(f"\n=== {name} ===")
        for item in data.get('items', [])[:1]:
            desc = item.get('description', '')
            if desc:
                desc = desc.encode('ascii', 'ignore').decode('ascii')
            print(f"{item['full_name']} ({item['stargazers_count']} stars)")
            print(f"  {item['html_url']}")
            print(f"  {desc[:100]}")
    except Exception as e:
        print(f"Error for {name}: {e}")