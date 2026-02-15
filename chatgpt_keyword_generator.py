#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gemini 关键词生成器
通过 Selenium 控制 Chrome 访问 Google Gemini，自动生成 DC-DC 相关搜索关键词

作者: AI 助手
版本: 2.0.0
日期: 2026-01-26
Python: 3.10+
依赖: selenium, webdriver-manager
"""

import json
import logging
import os
import re
import shutil
import time
from pathlib import Path
from typing import Dict, List, Optional, Set

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

try:
    from webdriver_manager.chrome import ChromeDriverManager
    WEBDRIVER_MANAGER_AVAILABLE = True
except ImportError:
    WEBDRIVER_MANAGER_AVAILABLE = False


class GeminiKeywordGenerator:
    """使用 Google Gemini 生成搜索关键词"""
    
    def __init__(self, logger: Optional[logging.Logger] = None, headless: bool = False, response_timeout: int = 60):
        """
        初始化 Gemini 关键词生成器
        
        Args:
            logger: 日志记录器
            headless: 是否使用无头模式 (首次登录建议 False)
            response_timeout: 等待响应的超时时间（秒），默认60秒
        """
        self.logger = logger or logging.getLogger(__name__)
        self.headless = headless
        self.response_timeout = response_timeout
        self.driver = None
        self.is_logged_in = False
    
    @staticmethod
    def clear_webdriver_cache():
        """清理 webdriver-manager 缓存 (解决中断导致的损坏问题)"""
        try:
            # webdriver-manager 的缓存路径
            if os.name == 'nt':  # Windows
                cache_path = Path.home() / '.wdm'
            else:  # Linux/Mac
                cache_path = Path.home() / '.wdm'
            
            if cache_path.exists():
                shutil.rmtree(cache_path)
                return True
        except Exception:
            pass
        return False
        
    def setup_driver(self) -> webdriver.Chrome:
        """设置 Chrome 浏览器"""
        chrome_options = Options()
        
        # 基础配置
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument("--disable-infobars")
        chrome_options.add_argument("--disable-gpu")
        
        # 增强反检测
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # 设置更真实的 User-Agent
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36')
        
        # Headless 模式
        if self.headless:
            chrome_options.add_argument("--headless=new")
        else:
            chrome_options.add_argument("--start-maximized")
        
        # 下载设置
        prefs = {
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True
        }
        chrome_options.add_experimental_option("prefs", prefs)
        
        driver = None
        last_errors = []
        
        # 方案1: 使用 Selenium 内置驱动管理（最稳定，无需网络）
        try:
            self.logger.info("📦 方案1: 使用 Selenium 内置驱动管理...")
            driver = webdriver.Chrome(options=chrome_options)
            self.logger.info("✅ 方案1 成功")
        except Exception as e1:
            last_errors.append(f"方案1: {e1}")
            self.logger.warning(f"⚠️ 方案1 失败: {e1}")
            
            # 方案2: 尝试使用 ChromeDriverManager (需要网络)
            if WEBDRIVER_MANAGER_AVAILABLE:
                try:
                    self.logger.info("📦 方案2: 使用 ChromeDriverManager...")
                    
                    # 如果之前有中断，先清理缓存
                    try:
                        from webdriver_manager.core.cache import CacheManager
                        service = Service(ChromeDriverManager(cache_manager=CacheManager()).install())
                    except Exception:
                        service = Service(ChromeDriverManager().install())
                    
                    driver = webdriver.Chrome(service=service, options=chrome_options)
                    self.logger.info("✅ 方案2 成功")
                except KeyboardInterrupt:
                    raise
                except Exception as e2:
                    last_errors.append(f"方案2: {e2}")
                    self.logger.warning(f"⚠️ 方案2 失败: {e2}")
                    
                    # 方案2b: 清理缓存后重试
                    try:
                        self.logger.info("📦 方案2b: 清理缓存后重试...")
                        if self.clear_webdriver_cache():
                            self.logger.info("   已清理 webdriver-manager 缓存")
                        
                        service = Service(ChromeDriverManager().install())
                        driver = webdriver.Chrome(service=service, options=chrome_options)
                        self.logger.info("✅ 方案2b 成功")
                    except KeyboardInterrupt:
                        raise
                    except Exception as e2b:
                        last_errors.append(f"方案2b: {e2b}")
                        self.logger.warning(f"⚠️ 方案2b 失败: {e2b}")
            else:
                last_errors.append("方案2: webdriver-manager 未安装")
                self.logger.warning("⚠️ webdriver-manager 未安装，跳过方案2")
            
            # 方案3: 查找本地 chromedriver
            if not driver:
                try:
                    self.logger.info("📦 方案3: 查找本地 chromedriver...")
                    local_paths = [
                        Path("chromedriver.exe"),
                        Path.cwd() / "chromedriver.exe",
                        Path(__file__).parent / "chromedriver.exe"
                    ]
                    
                    for path in local_paths:
                        if path.exists():
                            self.logger.info(f"   找到: {path}")
                            service = Service(str(path))
                            driver = webdriver.Chrome(service=service, options=chrome_options)
                            self.logger.info("✅ 方案3 成功")
                            break
                    
                    if not driver:
                        last_errors.append("方案3: 未找到本地 chromedriver.exe")
                        self.logger.warning("⚠️ 未找到本地 chromedriver.exe")
                except KeyboardInterrupt:
                    raise
                except Exception as e3:
                    last_errors.append(f"方案3: {e3}")
                    self.logger.warning(f"⚠️ 方案3 失败: {e3}")
        
        # 如果所有方案都失败
        if not driver:
            self.logger.error("❌ 所有方案均失败")
            for i, err in enumerate(last_errors, 1):
                self.logger.error(f"   {err}")
            self.logger.info("\n💡 解决建议：")
            self.logger.info("   1. 更新 Chrome 浏览器到最新版本")
            self.logger.info("   2. 运行: python download_chromedriver.py")
            self.logger.info("   3. 或手动下载 chromedriver:")
            self.logger.info("      https://googlechromelabs.github.io/chrome-for-testing/")
            self.logger.info("   4. 将 chromedriver.exe 放到项目目录或添加到 PATH")
            raise Exception("无法启动 Chrome 浏览器")
        
        if driver:
            try:
                # 增强的反自动化检测措施
                driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                    "source": """
                        // 隐藏 webdriver 属性
                        Object.defineProperty(navigator, 'webdriver', {
                            get: () => undefined
                        });
                        
                        // 覆盖 Chrome 相关属性
                        window.navigator.chrome = {
                            runtime: {}
                        };
                        
                        // 覆盖权限查询
                        const originalQuery = window.navigator.permissions.query;
                        window.navigator.permissions.query = (parameters) => (
                            parameters.name === 'notifications' ?
                                Promise.resolve({ state: Notification.permission }) :
                                originalQuery(parameters)
                        );
                        
                        // 覆盖插件信息
                        Object.defineProperty(navigator, 'plugins', {
                            get: () => [1, 2, 3, 4, 5]
                        });
                        
                        // 覆盖语言信息
                        Object.defineProperty(navigator, 'languages', {
                            get: () => ['en-US', 'en']
                        });
                        
                        // 移除自动化相关的属性
                        delete navigator.__proto__.webdriver;
                    """
                })
                
                if not self.headless:
                    driver.maximize_window()
                
                self.logger.info("✅ Chrome 浏览器启动成功")
                return driver
            except Exception as e:
                self.logger.error(f"❌ 浏览器配置失败: {e}")
                if driver:
                    driver.quit()
                raise
        else:
            raise Exception("无法创建 Chrome 驱动实例")
    
    def start(self):
        """启动浏览器"""
        if self.driver is None:
            self.logger.info("🚀 启动 Chrome 浏览器...")
            self.driver = self.setup_driver()
            time.sleep(2)
    
    def stop(self):
        """停止浏览器"""
        if self.driver:
            self.logger.info("🛑 关闭浏览器...")
            try:
                self.driver.quit()
            except Exception as e:
                self.logger.debug(f"关闭浏览器时出错（可忽略）: {e}")
            finally:
                self.driver = None
                self.is_logged_in = False
    
    def check_login_status(self, max_wait_time: int = 300) -> bool:
        """
        检查 Gemini 登录状态
        
        Args:
            max_wait_time: 等待登录的最长时间（秒），默认5分钟
            
        Returns:
            是否已登录
        """
        try:
            if not self.driver:
                return False
            
            # 访问 Gemini
            self.logger.info("🌐 正在访问 Google Gemini...")
            self.driver.get("https://gemini.google.com/")
            time.sleep(3)
            
            # 检查是否需要登录
            current_url = self.driver.current_url
            
            if "accounts.google.com" in current_url or "signin" in current_url:
                self._wait_for_login(max_wait_time)
                return self.check_login_status(max_wait_time)
            
            # 检查是否在 Gemini 界面
            if "gemini.google.com" in current_url:
                self.logger.info("✅ Gemini 已登录")
                self.is_logged_in = True
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"❌ 检查登录状态失败: {e}")
            return False
    
    def _wait_for_login(self, max_wait_time: int = 300):
        """
        等待用户完成登录
        
        Args:
            max_wait_time: 最长等待时间（秒）
        """
        self.logger.info("")
        self.logger.info("=" * 70)
        self.logger.info("🔑 需要登录 Google Gemini")
        self.logger.info("=" * 70)
        self.logger.info("")
        self.logger.info("📋 请在打开的浏览器窗口中完成以下步骤：")
        self.logger.info("   1. 输入你的 Google 账号和密码")
        self.logger.info("   2. 完成任何必要的验证（如果有）")
        self.logger.info("   3. 等待进入 Gemini 界面")
        self.logger.info("")
        self.logger.info("💡 程序会自动检测登录完成，无需手动操作")
        self.logger.info(f"⏱️  最长等待时间：{max_wait_time // 60} 分钟")
        self.logger.info("")
        self.logger.info("=" * 70)
        self.logger.info("")
        
        # 循环检测登录状态
        start_time = time.time()
        check_interval = 3  # 每3秒检查一次
        last_log_time = start_time
        
        while time.time() - start_time < max_wait_time:
            try:
                current_url = self.driver.current_url
                
                # 检查是否已经登录成功
                if "gemini.google.com" in current_url:
                    if "accounts.google.com" not in current_url and "signin" not in current_url:
                        self.logger.info("")
                        self.logger.info("=" * 70)
                        self.logger.info("✅ 检测到登录成功！")
                        self.logger.info("=" * 70)
                        self.logger.info("")
                        time.sleep(2)  # 等待页面完全加载
                        return
                
                # 每30秒显示一次等待提示
                if time.time() - last_log_time > 30:
                    elapsed = int(time.time() - start_time)
                    remaining = max_wait_time - elapsed
                    self.logger.info(f"⏳ 等待登录中... (已等待 {elapsed}秒，剩余 {remaining}秒)")
                    last_log_time = time.time()
                
                time.sleep(check_interval)
                
            except Exception as e:
                self.logger.debug(f"检测登录状态时出错: {e}")
                time.sleep(check_interval)
        
        # 超时
        self.logger.warning("")
        self.logger.warning("=" * 70)
        self.logger.warning(f"⚠️  等待超时（{max_wait_time}秒）")
        self.logger.warning("=" * 70)
        self.logger.warning("")
        self.logger.warning("请选择：")
        self.logger.warning("  1. 按 Enter - 继续等待")
        self.logger.warning("  2. 按 Ctrl+C - 退出程序")
        self.logger.warning("")
        
        try:
            input("按 Enter 继续等待...")
            self._wait_for_login(max_wait_time)  # 递归继续等待
        except KeyboardInterrupt:
            self.logger.info("\n❌ 用户取消登录")
            raise
    
    def send_prompt(self, prompt: str, wait_time: Optional[int] = None) -> Optional[str]:
        """
        发送 prompt 到 Gemini 并获取响应
        
        Args:
            prompt: 要发送的提示词
            wait_time: 最长等待时间（秒），如果未指定则使用实例的 response_timeout
            
        Returns:
            Gemini 的响应文本，失败返回 None
        """
        # 使用传入的 wait_time，否则使用实例默认值
        if wait_time is None:
            wait_time = self.response_timeout
        
        try:
            # 查找输入框（Gemini 使用 rich-textarea 和 contenteditable）
            self.logger.info("📝 查找输入框...")
            try:
                # Gemini 使用 .ql-editor 类（Quill 编辑器）
                textarea = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".ql-editor"))
                )
            except:
                try:
                    # 备用：rich-textarea 内的 contenteditable
                    textarea = WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "rich-textarea [contenteditable='true']"))
                    )
                except:
                    # 最后尝试：任何 contenteditable 元素
                    textarea = WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "[contenteditable='true']"))
                    )
            
            # 输入 prompt
            self.logger.info(f"💬 发送 prompt: {prompt[:100]}...")
            
            # 清空并输入文本
            if textarea.tag_name.lower() == "textarea":
                textarea.clear()
                textarea.send_keys(prompt)
            else:
                # 对于 contenteditable 元素
                self.driver.execute_script("arguments[0].textContent = arguments[1]", textarea, prompt)
                # 触发 input 事件以启用发送按钮
                self.driver.execute_script("arguments[0].dispatchEvent(new Event('input', { bubbles: true }));", textarea)
            
            time.sleep(1)
            
            # 尝试查找并点击发送按钮
            try:
                send_button = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "button.send-button"))
                )
                send_button.click()
                self.logger.info("✅ 已点击发送按钮")
            except:
                try:
                    # 备用：查找带有 Send 标签的按钮
                    send_button = self.driver.find_element(By.CSS_SELECTOR, "button[aria-label*='Send']")
                    send_button.click()
                    self.logger.info("✅ 已点击发送按钮（备用方法）")
                except:
                    # 如果找不到按钮，使用 Enter 键
                    textarea.send_keys(Keys.RETURN)
                    self.logger.info("✅ 已使用 Enter 键发送")
            
            # 等待响应
            self.logger.info("⏳ 等待 Gemini 响应...")
            time.sleep(5)  # 初始等待
            
            # 等待生成完成
            max_wait = wait_time
            elapsed = 0
            last_content = ""
            stable_count = 0  # 内容稳定计数器
            
            while elapsed < max_wait:
                # 查找最新的响应（尝试多种选择器）
                try:
                    messages = None
                    selector_used = None
                    
                    # 定义所有可能的选择器（按优先级）
                    selectors = [
                        (By.TAG_NAME, "message-content", "message-content"),
                        (By.TAG_NAME, "model-response", "model-response"),
                        (By.CSS_SELECTOR, ".model-response-text", ".model-response-text"),
                        (By.CSS_SELECTOR, ".markdown", ".markdown"),
                        (By.CSS_SELECTOR, "[data-test-id*='response']", "[data-test-id*='response']"),
                        (By.CSS_SELECTOR, ".response-container", ".response-container"),
                        (By.TAG_NAME, "marked-list", "marked-list"),
                        (By.CSS_SELECTOR, ".message-content", ".message-content"),
                        (By.CSS_SELECTOR, "[class*='response']", "[class*='response']"),
                        (By.CSS_SELECTOR, "[class*='message']", "[class*='message']"),
                    ]
                    
                    # 尝试所有选择器
                    for by_method, selector_value, selector_name in selectors:
                        try:
                            elements = self.driver.find_elements(by_method, selector_value)
                            if elements:
                                # 过滤掉用户输入的消息，只保留AI响应
                                valid_elements = []
                                for elem in elements:
                                    text = elem.text.strip()
                                    # 基本过滤：内容长度 > 10 且不是用户输入
                                    if text and len(text) > 10:
                                        valid_elements.append(elem)
                                
                                if valid_elements:
                                    messages = valid_elements
                                    selector_used = selector_name
                                    break
                        except:
                            continue
                    
                    if messages:
                        # 获取最新消息
                        latest_message = messages[-1]
                        current_content = latest_message.text.strip()
                        
                        # 首次找到内容时记录
                        if current_content and not last_content:
                            self.logger.info(f"📝 找到响应内容 (使用选择器: {selector_used})")
                        
                        # 检查是否停止生成
                        if current_content and current_content == last_content:
                            stable_count += 1
                            # 内容连续3次不变，认为生成完成
                            if stable_count >= 3:
                                self.logger.info("✅ 响应生成完成")
                                return current_content
                        else:
                            stable_count = 0  # 重置计数器
                        
                        last_content = current_content
                    else:
                        # 所有选择器都失败 - 尝试 JavaScript 备用方案
                        if elapsed > 15 and elapsed % 10 == 0:
                            self.logger.warning(f"⚠️  等待 {elapsed}s，仍未找到响应元素")
                            
                            # 第一次警告时保存调试信息
                            if elapsed == 20:
                                try:
                                    # 保存截图
                                    screenshot_path = Path("debug_gemini_screenshot.png")
                                    self.driver.save_screenshot(str(screenshot_path))
                                    self.logger.info(f"📸 已保存页面截图: {screenshot_path}")
                                    
                                    # 保存页面源代码
                                    html_path = Path("debug_gemini_page.html")
                                    with open(html_path, 'w', encoding='utf-8') as f:
                                        f.write(self.driver.page_source)
                                    self.logger.info(f"💾 已保存页面源代码: {html_path}")
                                except Exception as debug_error:
                                    self.logger.debug(f"保存调试信息失败: {debug_error}")
                            
                            # 尝试用 JavaScript 获取页面文本内容
                            try:
                                self.logger.debug("🔍 尝试使用 JavaScript 提取页面内容...")
                                js_content = self.driver.execute_script("""
                                    // 尝试获取所有可能包含响应的元素
                                    const selectors = [
                                        'message-content',
                                        'model-response', 
                                        '.markdown',
                                        '[data-test-id*="response"]',
                                        '.message-content'
                                    ];
                                    
                                    for (let selector of selectors) {
                                        const elements = document.querySelectorAll(selector);
                                        if (elements.length > 0) {
                                            const lastElem = elements[elements.length - 1];
                                            const text = lastElem.textContent || lastElem.innerText;
                                            if (text && text.trim().length > 50) {
                                                return text.trim();
                                            }
                                        }
                                    }
                                    return null;
                                """)
                                
                                if js_content:
                                    self.logger.info(f"✅ JavaScript 成功提取内容 ({len(js_content)} 字符)")
                                    last_content = js_content
                            except Exception as js_error:
                                self.logger.debug(f"JavaScript 提取失败: {js_error}")
                
                except Exception as e:
                    self.logger.debug(f"等待响应中: {e}")
                
                time.sleep(2)
                elapsed += 2
            
            # 超时但有内容
            if last_content:
                self.logger.warning(f"⚠️  等待超时 ({wait_time}s)，返回已获取的内容")
                return last_content
            
            self.logger.error(f"❌ 未能获取响应 (超时: {wait_time}s)")
            self.logger.error("💡 建议：")
            self.logger.error("   1. 检查 Gemini 页面是否正常加载")
            self.logger.error("   2. 尝试手动在浏览器中发送一条测试消息")
            self.logger.error("   3. 查看浏览器控制台是否有错误")
            self.logger.error("   4. 如果是网络问题，可能需要增加等待时间")
            return None
            
        except Exception as e:
            self.logger.error(f"❌ 发送 prompt 失败: {e}")
            return None
    
    def extract_keywords_from_response(self, response: str) -> List[str]:
        """
        从 Gemini 响应中提取关键词
        
        Args:
            response: Gemini 的响应文本
            
        Returns:
            提取的关键词列表
        """
        keywords = []
        
        self.logger.debug(f"📄 原始响应长度: {len(response)} 字符")
        self.logger.debug(f"📄 响应前300字符: {response[:300]}")
        
        # === 额外验证：检测是否是无效响应 ===
        # 如果响应太短或包含明显的界面文字，拒绝
        invalid_phrases = [
            'gemini', '你的', '私人', 'ai 助理', 'google', 
            '登录', 'sign in', 'account', 'settings',
            '设置', '帮助', 'help', 'tutorial', '教程',
            '开始使用', 'get started', 'welcome', '欢迎'
        ]
        
        response_lower = response.lower()
        suspicious_count = sum(1 for phrase in invalid_phrases if phrase in response_lower)
        
        # 如果响应太短(<50字符)或包含3个以上无效短语，认为不是有效的关键词列表
        if len(response.strip()) < 50 or suspicious_count >= 3:
            self.logger.error(f"❌ 检测到无效响应（可能是页面文字而非AI回复）")
            self.logger.error(f"   响应内容: {response[:200]}")
            self.logger.error(f"   可疑短语数: {suspicious_count}")
            return []
        
        # 优先匹配编号列表格式（最常见）
        pattern_numbered = r'^\s*(\d+)\.\s*(.+?)(?:\n|$)'
        matches = re.findall(pattern_numbered, response, re.MULTILINE)
        
        if matches:
            self.logger.debug(f"✅ 找到编号列表格式，共 {len(matches)} 项")
            for num, keyword in matches:
                keyword = keyword.strip()
                # 清理多余内容
                keyword = re.sub(r'\s*filetype:pdf\s*$', '', keyword, flags=re.IGNORECASE)
                keyword = keyword.strip('"\'`')
                
                # === 增强验证：必须包含技术关键词 ===
                # 至少包含以下之一：数字、常见技术术语、型号
                technical_patterns = [
                    r'\d+',  # 包含数字
                    r'\b(?:converter|power|supply|buck|boost|regulator|controller|driver|ic|chip|circuit)\b',  # 技术术语
                    r'\b[A-Z]{2,}\d{4,}\b',  # IC型号模式 (例如 TPS5460)
                ]
                
                has_technical = any(re.search(pattern, keyword, re.IGNORECASE) for pattern in technical_patterns)
                
                # 验证关键词有效性
                if 5 < len(keyword) < 150 and has_technical:
                    # 排除明显的说明文字
                    if not any(x in keyword.lower() for x in ['example', 'generate', 'keyword', 'format', 'here is', 'following', 'gemini', '助理']):
                        # 重新添加 filetype:pdf
                        if 'filetype:pdf' not in keyword.lower():
                            keyword = f"{keyword} filetype:pdf"
                        keywords.append(keyword)
        
        # 如果编号格式失败，尝试其他格式
        if not keywords:
            self.logger.debug("⚠️  未找到编号格式，尝试其他模式")
            
            # 尝试匹配 filetype:pdf 结尾的行
            pattern_filetype = r'(?:^|\n)\s*(?:\d+\.\s*)?(.+?filetype:pdf)\s*(?:\n|$)'
            matches = re.findall(pattern_filetype, response, re.IGNORECASE | re.MULTILINE)
            
            if matches:
                self.logger.debug(f"✅ 找到 filetype:pdf 格式，共 {len(matches)} 项")
                for match in matches:
                    keyword = match.strip()
                    keyword = re.sub(r'^\d+\.\s*', '', keyword)  # 移除编号
                    keyword = keyword.strip('"\'`')
                    
                    # 技术关键词验证
                    has_technical = any(re.search(pattern, keyword, re.IGNORECASE) 
                                       for pattern in [r'\d+', r'\b(?:converter|power|supply|buck|boost)\b'])
                    
                    if 10 < len(keyword) < 150 and has_technical and keyword not in keywords:
                        keywords.append(keyword)
        
        # 最后的回退方案：按行分割
        if not keywords:
            self.logger.debug("⚠️  使用行分割回退方案")
            lines = response.split('\n')
            for line in lines:
                line = line.strip()
                # 跳过空行和明显的说明文字
                if not line or len(line) < 10:
                    continue
                if any(x in line.lower() for x in ['example', 'generate', 'keyword', 'format', 'requirement', ':', 'here', 'following', 'gemini', '助理']):
                    continue
                
                # 去除编号和标记
                line = re.sub(r'^[\d\-*•]+[\.\)]\s*', '', line)
                line = line.strip('"\'`')
                
                # 技术关键词验证
                has_technical = any(re.search(pattern, line, re.IGNORECASE) 
                                   for pattern in [r'\d+', r'\b(?:converter|power|supply|buck|boost)\b'])
                
                if 10 < len(line) < 150 and has_technical:
                    # 确保有 filetype:pdf
                    if 'filetype:pdf' not in line.lower():
                        line = f"{line} filetype:pdf"
                    if line not in keywords:
                        keywords.append(line)
        
        self.logger.info(f"📋 提取到 {len(keywords)} 个关键词")
        if keywords:
            for i, kw in enumerate(keywords[:5], 1):
                self.logger.debug(f"   {i}. {kw}")
            if len(keywords) > 5:
                self.logger.debug(f"   ... 还有 {len(keywords) - 5} 个")
        else:
            self.logger.warning(f"⚠️  未能提取关键词，响应内容可能格式不正确")
            self.logger.warning(f"响应示例: {response[:500]}")
        
        return keywords
    
    def generate_keywords(
        self, 
        context: Optional[Dict] = None,
        num_keywords: int = 20,
        focus_areas: Optional[List[str]] = None
    ) -> List[str]:
        """
        生成新的搜索关键词
        
        Args:
            context: 上下文信息（已下载文件统计、已用关键词等）
            num_keywords: 期望生成的关键词数量
            focus_areas: 重点关注的领域
            
        Returns:
            生成的关键词列表
        """
        if not self.is_logged_in:
            if not self.check_login_status():
                self.logger.error("❌ Gemini 未登录，无法生成关键词")
                return []
        
        # 构建 prompt
        prompt = self._build_prompt(context, num_keywords, focus_areas)
        
        # 发送 prompt
        response = self.send_prompt(prompt)
        
        if not response:
            return []
        
        # 提取关键词
        keywords = self.extract_keywords_from_response(response)
        
        # 限制数量
        if len(keywords) > num_keywords:
            keywords = keywords[:num_keywords]
        
        return keywords
    
    def _build_prompt(
        self, 
        context: Optional[Dict], 
        num_keywords: int,
        focus_areas: Optional[List[str]]
    ) -> str:
        """构建发送给 Gemini 的优化 prompt"""
        
        base_prompt = f"""Generate {num_keywords} search keywords for finding DC-DC converter PDF technical documents.

CRITICAL OUTPUT FORMAT - Reply ONLY with this exact format, no extra text:
1. keyword here filetype:pdf
2. keyword here filetype:pdf
3. keyword here filetype:pdf

Requirements for each keyword:
- Include specific IC models (e.g., TPS54620, LM2596, LTC3780) OR technical specs
- Mix these types:
  * IC datasheets: "[Part Number] datasheet filetype:pdf"
  * Application notes: "[Part Number] application note filetype:pdf"  
  * Design guides: "[Technology] design guide filetype:pdf"
  * Reference designs: "[Application] reference design filetype:pdf"
- Always end with "filetype:pdf"
- Use 3-7 words per keyword
- English only

Examples:
1. TPS54620 synchronous buck datasheet filetype:pdf
2. LM2596 step down converter application note filetype:pdf
3. automotive 48V to 12V DCDC design guide filetype:pdf
4. high efficiency buck boost converter datasheet filetype:pdf

NOW generate {num_keywords} DIFFERENT keywords following this exact format:"""
        
        # 添加重点关注领域
        if focus_areas and len(focus_areas) > 0:
            focus_text = ", ".join(focus_areas[:5])  # 只取前5个
            base_prompt += f"\n\nPriority topics: {focus_text}"
        
        # 添加上下文信息以避免重复
        if context:
            if "used_keywords" in context:
                used = context["used_keywords"][:10]  # 只显示最近10个
                if used:
                    used_text = ", ".join([kw.split()[0] for kw in used[:5]])  # 只显示关键词的第一个词
                    base_prompt += f"\n\nAvoid these recent topics: {used_text}"
            
            if "vendors" in context and len(context["vendors"]) > 5:
                # 如果已经有很多供应商，提示探索其他的
                base_prompt += f"\n\nTry different vendors or topics from usual."
        
        base_prompt += f"\n\nStart generating the {num_keywords} keywords now:"
        
        base_prompt += "\nGenerate the keyword list now:"
        
        return base_prompt
    
    def __enter__(self):
        """上下文管理器入口"""
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.stop()


def main():
    """测试函数"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    
    logger = logging.getLogger(__name__)
    
    # 测试关键词生成
    with GeminiKeywordGenerator(logger=logger, headless=False) as generator:
        if generator.check_login_status():
            # 测试生成
            context = {
                "downloaded_count": 45,
                "vendors": ["TI", "ST", "Analog Devices"],
                "used_keywords": ["LM5164 datasheet", "buck converter design"],
                "recent_topics": ["synchronous buck", "high efficiency DCDC"]
            }
            
            keywords = generator.generate_keywords(
                context=context,
                num_keywords=10,
                focus_areas=["automotive power", "high voltage DCDC"]
            )
            
            logger.info(f"\n生成的关键词:")
            for i, kw in enumerate(keywords, 1):
                logger.info(f"{i}. {kw}")


if __name__ == "__main__":
    main()
