#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
关键词探索器 - 使用 Gemini 生成新的搜索关键词和厂商网站
"""

import json
import logging
import time
from pathlib import Path
from datetime import datetime
from chatgpt_keyword_generator import GeminiKeywordGenerator

# 配置
OUTPUT_DIR = Path("downloads_continuous")
KEYWORDS_FILE = OUTPUT_DIR / "explored_keywords.json"
VENDORS_FILE = OUTPUT_DIR / "explored_vendors.json"

# Gemini 提示词
KEYWORD_PROMPT = """You are an automotive EMC/EMI and reliability testing expert. Generate 50 search keywords for finding PDF documents related to ISO 7637 transient immunity, EMC/EMI testing, and automotive electronics reliability qualification (especially for bidirectional buck-boost converters).

Requirements:
1. Cover standards: ISO 7637-1/2/3, ISO 16750, CISPR 25, IEC 61000-4-x, IEC 62132, SAE J1113
2. Include test types: transient immunity, conducted emission, radiated emission, ESD, surge, BCI, DPI
3. Include protection design: TVS diode, EMI filter, common mode choke, ferrite bead, clamping circuit
4. Include reliability: AEC-Q100, HTOL, HTSL, thermal cycling, vibration, HALT, HASS, FMEA
5. Include applications: automotive ECU, bidirectional buck-boost, DC-DC converter EMC, 12V/24V/48V system
6. Include document types: application note, design guide, test report, compliance guide, white paper
7. Keep keywords general, suitable for web searches, avoid specific part numbers

FORMAT RULES (CRITICAL):
- Output ONLY keywords, ONE per line
- Each keyword: 2-6 words
- NO numbers, NO bullets, NO explanations, NO questions
- NO UI text like "Here are the keywords" or "Would you like"
- Just plain text keywords, each on a new line

Example output:
ISO 7637 transient immunity test
automotive EMC compliance guide
TVS diode selection automotive
CISPR 25 radiated emission measurement
load dump protection design
ESD protection CAN bus automotive
AEC-Q100 qualification test
automotive EMI filter design
bulk current injection BCI test
ISO 16750 electrical test automotive

Now generate 50 keywords following this EXACT format:"""

VENDOR_PROMPT = """你是一个汽车电子EMC/EMI和可靠性测试领域的专家。请列出以下类别的全球主要厂商和机构的官方网站域名：

已知厂商包括但不限于：
- Littelfuse (littelfuse.com) - TVS保护器件
- Bourns (bourns.com) - 瞬态保护
- Nexperia (nexperia.com) - ESD保护
- Murata (murata.com) - EMI滤波器
- TDK (tdk.com) - EMC元器件

请补充更多厂商（至少30个），特别是：
1. TVS/ESD保护器件厂商（如Vishay, Semtech, ProTek等）
2. EMI滤波器/磁性元件厂商（如Würth, Laird, Fair-Rite等）
3. 汽车级半导体厂商（如TI, Infineon, NXP, ST, onsemi等）
4. EMC测试设备厂商（如Rohde & Schwarz, Keysight, TESEQ等）
5. EMC认证/测试实验室（如TÜV, DEKRA, Bureau Veritas等）
6. 连接器/线束EMC屏蔽厂商

格式要求（非常重要）：
- 必须每行一个厂商
- 格式：厂商名称: 域名
- 域名只包含主域名，不要www、http等
- 只输出厂商列表，不要序号、不要解释、不要问问题

示例格式：
Littelfuse: littelfuse.com
Bourns: bourns.com
Rohde Schwarz: rohde-schwarz.com
Murata: murata.com

现在请按照上述格式生成厂商列表："""


def setup_logger():
    """设置日志"""
    logger = logging.getLogger('KeywordExplorer')
    logger.setLevel(logging.INFO)
    
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    return logger


def parse_keywords(response_text: str) -> list:
    """解析 Gemini 返回的关键词"""
    keywords = []
    
    # === 第一步：清理和验证响应 ===
    # 检查是否包含Gemini UI文字（乱码或原文）
    ui_patterns = [
        '认识 gemini', 'gemini：你的', '私人', 'ai 助理', 'ai assistant',
        'google gemini', 'get started', 'welcome to', '欢迎使用',
        'sign in', '登录', 'account', '账号', 'settings', '设置',
        # 乱码模式（检测特定字符）
        '璁よ瘑', '鍔╃悊'
    ]
    
    response_lower = response_text.lower()
    if any(pattern in response_lower for pattern in ui_patterns):
        # 尝试清理这些内容
        for pattern in ui_patterns:
            if pattern in response_lower:
                # 查找并移除包含该模式的整行
                lines = response_text.split('\n')
                cleaned_lines = []
                for line in lines:
                    if pattern not in line.lower():
                        cleaned_lines.append(line)
                response_text = '\n'.join(cleaned_lines)
    
    # === 第二步：按行分割和预处理 ===
    lines = response_text.strip().split('\n')
    
    # 对每一行都检查长度，超长的进行分割
    processed_lines = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # 如果这行超过100字符，尝试智能分割
        if len(line) > 100:
            # 尝试按常见分隔符分割
            split_done = False
            for separator in [', ', '; ', ' / ', '  ']:
                if separator in line:
                    parts = [s.strip() for s in line.split(separator) if s.strip()]
                    # 只有当分割后每个部分都不太长时才接受
                    if all(len(p) <= 100 for p in parts):
                        processed_lines.extend(parts)
                        split_done = True
                        break
            
            # 如果分隔符分割失败，按空格分词重组（每3词一组）
            if not split_done:
                words = line.split()
                i = 0
                while i < len(words):
                    # 固定3个词一组
                    phrase = ' '.join(words[i:i+3])
                    if len(phrase) >= 8:  # 至少8个字符
                        processed_lines.append(phrase)
                    i += 3
                # 跳过这个超长行的原始文本
                continue
        
        # 正常长度的行直接添加
        processed_lines.append(line)
    
    lines = processed_lines
    
    # === 第三步：逐行解析和过滤 ===
    for line in lines:
        line = line.strip()
        if not line or len(line) < 5:
            continue
        
        # 移除序号和标记
        line = line.lstrip('0123456789.-*•→ \t')
        line = line.strip('`*_?？:：')
        
        # 强制ASCII检查（技术关键词应该是英文）
        # 允许少量非ASCII字符（如破折号），但主体必须是ASCII
        ascii_ratio = sum(1 for c in line if ord(c) < 128) / len(line)
        if ascii_ratio < 0.8:  # 至少80%是ASCII字符
            continue
        
        # 过滤问句和说明文字
        skip_phrases = [
            'would you', 'do you', 'should i', 'can i', 'here is', 'here are',
            'following', 'example', 'format:', 'requirement', 'generate',
            '需要', '是否', '以下', '示例', '格式', '生成', '关键词'
        ]
        if any(phrase in line.lower() for phrase in skip_phrases):
            continue
        
        # 过滤Gemini的自我介绍
        if any(word in line.lower() for word in ['gemini', 'google', 'assistant']):
            continue
        
        # 技术关键词验证：必须包含技术相关词汇
        technical_words = [
            # EMC/EMI 相关
            'emc', 'emi', 'esd', 'transient', 'immunity', 'emission',
            'conducted', 'radiated', 'susceptibility', 'interference',
            'suppression', 'filter', 'shielding', 'coupling', 'decoupling',
            # 标准相关
            'iso', 'cispr', 'iec', 'sae', 'aec', 'jedec',
            '7637', '16750', '61000', '62132', '61967', 'j1113',
            # 保护器件
            'tvs', 'varistor', 'clamp', 'suppressor', 'protection',
            'choke', 'ferrite', 'bead', 'capacitor', 'inductor',
            # 可靠性测试
            'reliability', 'qualification', 'htol', 'htsl', 'halt', 'hass',
            'thermal', 'cycling', 'vibration', 'humidity', 'fmea',
            'mission', 'profile', 'lifetime', 'stress',
            # 汽车电子
            'automotive', 'vehicle', 'ecu', 'cmix', 'module',
            'load dump', 'cold crank', 'pulse', 'surge', 'burst',
            # 通用技术词
            'power', 'voltage', 'current', 'converter', 'regulator',
            'design', 'test', 'measurement', 'compliance', 'standard',
            'pcb', 'layout', 'simulation', 'spice', 'model',
            'can', 'lin', 'bus', 'connector', 'harness',
            'buck', 'boost', 'dc-dc', 'switching', 'controller',
            'bci', 'dpi', 'tem', 'stripline', 'probe',
            'datasheet', 'application', 'guide', 'reference', 'note'
        ]
        has_technical = any(word in line.lower() for word in technical_words)
        
        # 或者包含常见的文档类型词
        doc_types = ['datasheet', 'application note', 'user guide', 'reference',
                     'design guide', 'test report', 'white paper', 'compliance guide',
                     'technical note', 'selection guide']
        has_doc_type = any(dtype in line.lower() for dtype in doc_types)
        
        # 必须有技术词或文档类型
        if not (has_technical or has_doc_type):
            continue
        
        # 长度限制
        if 5 < len(line) < 100:
            keywords.append(line)
    
    return keywords


def parse_vendors(response_text: str) -> dict:
    """解析 Gemini 返回的厂商信息"""
    vendors = {}
    lines = response_text.strip().split('\n')
    
    for line in lines:
        line = line.strip()
        if not line or ':' not in line:
            continue
        
        # 分割厂商名和域名
        parts = line.split(':', 1)
        if len(parts) != 2:
            continue
        
        vendor_name = parts[0].strip()
        domain = parts[1].strip()
        
        # 清理域名（移除 www, http等）
        domain = domain.replace('http://', '').replace('https://', '')
        domain = domain.replace('www.', '')
        domain = domain.split('/')[0]  # 只保留域名部分
        
        if domain and '.' in domain:
            vendors[vendor_name] = domain
    
    return vendors


def explore_keywords(logger, headless=False):
    """探索新关键词"""
    logger.info("="*70)
    logger.info("开始探索新关键词...")
    logger.info("="*70)
    
    # 读取已使用的关键词
    used_keywords = set()
    used_file = OUTPUT_DIR / "used_keywords.json"
    if used_file.exists():
        try:
            with open(used_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                used_keywords = set(data.get('used', []))
                logger.info(f"📋 已使用 {len(used_keywords)} 个关键词")
        except Exception as e:
            logger.warning(f"⚠️  读取已使用关键词失败: {e}")
    
    # 动态构建提示词
    prompt = KEYWORD_PROMPT
    if used_keywords:
        # 取最近使用的20个作为示例
        recent_used = list(used_keywords)[-20:]
        used_text = ", ".join(recent_used[:10])  # 只显示前10个
        prompt += f"\n\n⚠️ 避免重复这些已用过的关键词: {used_text}"
        prompt += "\n请生成完全不同的新关键词！"
    
    generator = GeminiKeywordGenerator(logger=logger, headless=headless, response_timeout=120)
    
    try:
        # 启动浏览器
        generator.start()
        
        # 检查登录状态
        if not generator.check_login_status():
            logger.error("❌ 无法登录 Gemini")
            return []
        
        # 发送提示词
        response = generator.send_prompt(prompt)
        
        if not response:
            logger.error("未获得响应")
            return []
        
        logger.info(f"\n收到响应:\n{response[:500]}...\n")
        
        # 解析关键词
        new_keywords = parse_keywords(response)
        logger.info(f"解析得到 {len(new_keywords)} 个新关键词")
        
        # 过滤掉已使用的
        if used_keywords:
            original_count = len(new_keywords)
            new_keywords = [k for k in new_keywords if k not in used_keywords]
            filtered = original_count - len(new_keywords)
            if filtered > 0:
                logger.info(f"🔄 过滤掉 {filtered} 个重复关键词")
        
        # 读取现有关键词列表
        existing_keywords = []
        if KEYWORDS_FILE.exists():
            try:
                with open(KEYWORDS_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    raw_existing = data.get('keywords', [])
                    # 过滤现有关键词：只保留长度合理的（10-100字符）
                    existing_keywords = [k for k in raw_existing if 10 <= len(k) <= 100]
                    removed_old = len(raw_existing) - len(existing_keywords)
                    if removed_old > 0:
                        logger.info(f"🧹 清理掉 {removed_old} 个旧的无效关键词")
            except Exception as e:
                logger.warning(f"读取现有关键词失败: {e}")
        
        # 合并新旧关键词（去重）
        all_keywords = existing_keywords + new_keywords
        # 保持顺序并去重
        seen = set()
        unique_keywords = []
        for k in all_keywords:
            if k not in seen:
                seen.add(k)
                unique_keywords.append(k)
        
        # 保存结果
        data = {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'keywords': unique_keywords,
            'count': len(unique_keywords),
            'new_added': len(new_keywords)
        }
        
        with open(KEYWORDS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"✅ 关键词已保存到: {KEYWORDS_FILE}")
        logger.info(f"   总计: {len(unique_keywords)} 个 (新增: {len(new_keywords)} 个)")
        
        return new_keywords
        
    finally:
        generator.stop()


def explore_vendors(logger, headless=False):
    """探索新厂商"""
    logger.info("="*70)
    logger.info("开始探索新厂商...")
    logger.info("="*70)
    
    generator = GeminiKeywordGenerator(logger=logger, headless=headless, response_timeout=120)
    
    try:
        # 启动浏览器
        generator.start()
        
        # 检查登录状态
        if not generator.check_login_status():
            logger.error("❌ 无法登录 Gemini")
            return {}
        
        # 发送提示词
        response = generator.send_prompt(VENDOR_PROMPT)
        
        if not response:
            logger.error("未获得响应")
            return {}
        
        logger.info(f"\n收到响应:\n{response[:500]}...\n")
        
        # 解析厂商
        vendors = parse_vendors(response)
        logger.info(f"解析得到 {len(vendors)} 个厂商")
        
        # 保存结果
        data = {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'vendors': vendors,
            'count': len(vendors)
        }
        
        with open(VENDORS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"✅ 厂商已保存到: {VENDORS_FILE}")
        
        return vendors
        
    finally:
        generator.stop()


def main():
    """主函数"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    logger = setup_logger()
    
    print("="*70)
    print("关键词和厂商探索器")
    print("使用 Google Gemini 自动生成搜索关键词和厂商列表")
    print("="*70)
    print()
    
    # 选择模式
    print("请选择探索模式:")
    print("1. 探索新关键词 (智能避开已用关键词)")
    print("2. 探索新厂商")
    print("3. 全部探索")
    print("4. 持续探索模式 (无限循环生成新关键词)")
    
    choice = input("\n请输入选项 (1-4): ").strip()
    
    # 是否使用无头模式
    headless_input = input("是否使用无头模式? (y/n，首次使用建议 n): ").strip().lower()
    headless = headless_input == 'y'
    
    if choice == '4':
        # 持续探索模式
        print("\n" + "="*70)
        print("🔄 持续探索模式")
        print("将每隔 5 分钟自动生成新关键词")
        print("按 Ctrl+C 停止")
        print("="*70)
        
        cycle_count = 0
        while True:
            try:
                cycle_count += 1
                print(f"\n{'='*70}")
                print(f"第 {cycle_count} 轮探索")
                print(f"{'='*70}")
                
                keywords = explore_keywords(logger, headless)
                print(f"\n✅ 本轮新增 {len(keywords)} 个关键词")
                
                print("\n⏳ 等待 5 分钟后进行下一轮探索...")
                print("   (在此期间可以运行 start_vendor_batch*.bat)")
                time.sleep(300)  # 5分钟
                
            except KeyboardInterrupt:
                print("\n\n👋 用户中断，停止探索")
                break
            except Exception as e:
                logger.error(f"探索出错: {e}")
                print("\n⏳ 等待 1 分钟后重试...")
                time.sleep(60)
    
    elif choice in ['1', '3']:
        keywords = explore_keywords(logger, headless)
        print(f"\n✅ 探索到 {len(keywords)} 个新关键词")
        if keywords:
            print("\n示例关键词:")
            for kw in keywords[:10]:
                print(f"  - {kw}")
        
        time.sleep(5)  # 等待5秒再进行下一个任务
    
    if choice in ['2', '3']:
        vendors = explore_vendors(logger, headless)
        print(f"\n✅ 探索到 {len(vendors)} 个厂商")
        if vendors:
            print("\n示例厂商:")
            for name, domain in list(vendors.items())[:10]:
                print(f"  - {name}: {domain}")
    
    print("\n" + "="*70)
    print("探索完成！")
    print(f"关键词文件: {KEYWORDS_FILE}")
    print(f"厂商文件: {VENDORS_FILE}")
    print("="*70)


if __name__ == '__main__':
    main()
