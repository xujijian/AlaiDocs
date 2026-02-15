import json
import os

# 删除旧文件
if os.path.exists('downloads_continuous/explored_keywords.json'):
    os.remove('downloads_continuous/explored_keywords.json')
    print('✅ 已删除旧文件')

# 创建干净的初始关键词
clean_keywords = {
    "timestamp": "2026-01-28 14:45:00",
    "keywords": [
        "buck converter datasheet",
        "boost regulator application",
        "flyback design guide",
        "forward converter reference",
        "LLC resonant converter",
        "SEPIC regulator datasheet",
        "Cuk converter application",
        "synchronous buck controller",
        "high efficiency regulator",
        "automotive power supply",
        "industrial DC-DC converter",
        "telecom power module",
        "server power management",
        "battery charger controller",
        "USB PD controller",
        "LED driver IC",
        "motor driver datasheet",
        "isolated DC-DC converter",
        "non-isolated buck converter",
        "POL converter datasheet",
        "multi-phase buck controller",
        "current mode PWM controller",
        "voltage mode controller",
        "PWM controller datasheet",
        "PFC controller application",
        "active clamp forward",
        "soft start circuit",
        "PMIC datasheet",
        "voltage regulator IC",
        "LDO regulator",
        "switching regulator datasheet",
        "step down converter",
        "step up boost regulator",
        "buck-boost converter",
        "hot swap controller",
        "load switch datasheet",
        "gate driver IC",
        "synchronous rectifier controller",
        "power stage module",
        "digital power controller",
        "wireless charging IC",
        "solar MPPT controller",
        "battery management system",
        "power factor correction",
        "thermal management guide",
        "EMI filter design",
        "evaluation board manual",
        "reference design guide",
        "application note PDF",
        "technical datasheet"
    ],
    "count": 50,
    "note": "手动清理后的高质量关键词"
}

with open('downloads_continuous/explored_keywords.json', 'w', encoding='utf-8') as f:
    json.dump(clean_keywords, f, indent=2, ensure_ascii=False)

print(f'✅ 已创建新文件，包含 {len(clean_keywords["keywords"])} 个关键词')

# 验证
data = json.load(open('downloads_continuous/explored_keywords.json', encoding='utf-8'))
print(f'验证: {len(data["keywords"])} 个关键词')
print(f'前5个: {data["keywords"][:5]}')
print(f'后5个: {data["keywords"][-5:]}')
