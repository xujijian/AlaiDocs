import json

data = json.load(open('downloads_continuous/explored_keywords.json', encoding='utf-8'))
print(f'Count: {data["count"]}')
print(f'Actual length: {len(data["keywords"])}')
print(f'\nLast 3 keywords:')
for kw in data["keywords"][-3:]:
    print(f'  - {kw[:100]}...' if len(kw) > 100 else f'  - {kw}')
