import shutil
shutil.copy('downloads_continuous/explored_keywords.json.backup', 
            'downloads_continuous/explored_keywords.json')
print('✅ 已恢复到备份版本')

import json
data = json.load(open('downloads_continuous/explored_keywords.json', encoding='utf-8'))
print(f'关键词数量: {len(data["keywords"])}')
