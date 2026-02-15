import json

data = json.load(open('downloads_continuous/explored_keywords.json', encoding='utf-8'))
print(f'总数: {len(data["keywords"])} 个关键词')
print(f'时间戳: {data["timestamp"]}')

print(f'\n最后 5 个关键词:')
for i, kw in enumerate(data["keywords"][-5:], len(data["keywords"])-4):
    if len(kw) > 120:
        print(f'{i}. {kw[:120]}...')
    else:
        print(f'{i}. {kw}')

# 统计超长关键词
long_keywords = [kw for kw in data["keywords"] if len(kw) > 100]
print(f'\n超长关键词 (>100字符): {len(long_keywords)} 个')
if long_keywords:
    print('前3个超长关键词预览:')
    for i, kw in enumerate(long_keywords[:3], 1):
        print(f'  {i}. 长度={len(kw)}, 内容={kw[:80]}...')
