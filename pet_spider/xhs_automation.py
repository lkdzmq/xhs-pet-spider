#!/usr/bin/env python3
"""
小红书自动化脚本
功能：启动浏览器、维持登录状态、搜索关键词、筛选最新帖子、滚动加载更多内容
支持浏览器：Chrome（默认）、Safari（备选）
"""

import json
import math
import time
import sys
import os
import urllib.request
import urllib.parse
from typing import Optional, List, Dict
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# 导入配置
try:
    import config
except ImportError:
    # 如果config.py不存在，使用默认配置
    config = None


class XHSAutomation:
    def __init__(self, browser_type: str = 'chrome', headless: bool = False):
        """
        初始化浏览器驱动

        Args:
            browser_type: 浏览器类型，'chrome' 或 'safari'
            headless: 是否使用无头模式（仅Chrome支持）
        """
        self.browser_type = browser_type.lower()
        self.headless = headless
        self.driver = None
        self.wait = None

    def start_browser(self):
        """启动浏览器"""
        if self.browser_type == 'safari':
            # Safari需要先在浏览器中启用"允许远程自动化"
            # 打开Safari -> 偏好设置 -> 高级 -> 勾选"在菜单栏中显示开发菜单"
            # 然后：开发 -> 允许远程自动化
            try:
                self.driver = webdriver.Safari()
            except Exception as e:
                print(f"启动Safari失败: {e}")
                print("请确保：")
                print("1. Safari浏览器已安装")
                print("2. 已启用'允许远程自动化'（Safari -> 开发 -> 允许远程自动化）")
                print("3. 如果仍失败，尝试使用Chrome：browser_type='chrome'")
                sys.exit(1)

        elif self.browser_type == 'chrome':
            from selenium.webdriver.chrome.options import Options
            chrome_options = Options()
            # macOS Chrome path
            chrome_options.binary_location = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
            if self.headless:
                chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            # 防止检测自动化
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)

            try:
                from webdriver_manager.chrome import ChromeDriverManager
                from selenium.webdriver.chrome.service import Service
                service = Service(ChromeDriverManager().install())
                self.driver = webdriver.Chrome(service=service, options=chrome_options)
            except Exception as e:
                # 如果webdriver_manager未安装或下载失败，使用系统PATH中的chromedriver
                print(f"警告: webdriver_manager失败 ({e})，使用系统PATH中的chromedriver")
                self.driver = webdriver.Chrome(options=chrome_options)
        else:
            raise ValueError(f"不支持的浏览器类型: {self.browser_type}")

        # 设置浏览器窗口大小（调大窗口）
        try:
            self.driver.set_window_size(1200, 800)
            print(f"已设置窗口大小: 1200x800")
        except Exception as e:
            print(f"设置窗口大小失败: {e}")
            try:
                # 尝试最大化窗口作为备选
                self.driver.maximize_window()
                print("已最大化窗口")
            except Exception as e2:
                print(f"最大化窗口也失败: {e2}")

        self.wait = WebDriverWait(self.driver, 20)
        print(f"{self.browser_type.capitalize()}浏览器启动成功")

    def load_cookies(self, cookie_file: str):
        """
        从JSON文件加载Cookie

        Args:
            cookie_file: JSON文件路径，包含Cookie列表
        """
        try:
            with open(cookie_file, 'r', encoding='utf-8') as f:
                cookies = json.load(f)

            # 首先访问小红书域名，以便设置Cookie
            self.driver.get('https://www.xiaohongshu.com')
            time.sleep(2)

            # 添加每个Cookie
            for cookie in cookies:
                # 确保domain字段正确
                if 'domain' in cookie and cookie['domain']:
                    # 如果domain以.开头，去除点号以便Selenium接受
                    if cookie['domain'].startswith('.'):
                        cookie['domain'] = cookie['domain'][1:]
                try:
                    self.driver.add_cookie(cookie)
                except Exception as e:
                    print(f"添加Cookie失败: {cookie.get('name', 'unknown')}, 错误: {e}")

            # 刷新页面使Cookie生效
            self.driver.refresh()
            time.sleep(3)
            print(f"已从 {cookie_file} 加载 {len(cookies)} 个Cookie")

        except FileNotFoundError:
            print(f"Cookie文件不存在: {cookie_file}")
            print("请导出小红书登录Cookie为JSON格式")
            sys.exit(1)
        except json.JSONDecodeError:
            print(f"Cookie文件格式错误: {cookie_file}")
            print("请确保是有效的JSON格式")
            sys.exit(1)

    def is_logged_in(self) -> bool:
        """检查是否已登录"""
        try:
            # 尝试查找登录后的用户元素，例如用户头像或用户名
            # 这里需要根据小红书实际页面调整选择器
            user_elements = self.driver.find_elements(By.CSS_SELECTOR, '.avatar, .user-avatar, .profile-icon')
            if user_elements:
                return True

            # 或者检查是否存在登录按钮
            login_buttons = self.driver.find_elements(By.CSS_SELECTOR, 'button.login-btn, a.login-link')
            if not login_buttons:
                return True

            # 如果URL包含登录页面，说明未登录
            if 'login' in self.driver.current_url.lower():
                return False

            return True
        except:
            return False

    def search_keyword(self, keyword: str):
        """
        搜索关键词

        Args:
            keyword: 搜索关键词，如"深圳 走丢 小狗"
        """
        print(f"\n=== 开始搜索: {keyword} ===")

        # 记录当前URL
        original_url = self.driver.current_url
        print(f"搜索前URL: {original_url}")

        try:
            # 等待搜索框出现
            search_box = self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'input[placeholder*="搜索"], input.search-input'))
            )
            search_box.clear()
            search_box.send_keys(keyword)
            print(f"已输入搜索关键词: {keyword}")

            # 等待搜索按钮并点击
            search_btn = self.wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, 'button.search-btn, .search-icon, .ant-btn-primary'))
            )

            # 检查搜索按钮信息
            btn_text = search_btn.text.strip() if search_btn.text else ''
            btn_class = search_btn.get_attribute('class') or ''
            print(f"搜索按钮文本: '{btn_text}', class: '{btn_class}'")

            search_btn.click()
            print("已点击搜索")

            # 等待搜索结果加载
            print("等待搜索结果加载...")
            time.sleep(5)

            # 检查是否成功跳转到搜索结果页
            current_url = self.driver.current_url
            print(f"搜索后URL: {current_url}")

            # 检查URL是否包含搜索相关标识
            if 'search_result' not in current_url and 'search' not in current_url.lower():
                print("警告: 可能未成功跳转到搜索结果页")
                print(f"当前页面标题: {self.driver.title}")

                # 尝试备用方法
                print("尝试备用搜索方法...")
                self._fallback_search(keyword)
            else:
                print("成功跳转到搜索结果页")
                print(f"页面标题: {self.driver.title}")

        except TimeoutException as e:
            print(f"搜索超时: {e}")
            print("尝试备用搜索方法...")
            self._fallback_search(keyword)
        except Exception as e:
            print(f"搜索过程中出错: {e}")
            print("尝试备用搜索方法...")
            self._fallback_search(keyword)

    def _fallback_search(self, keyword):
        """备用搜索方法：直接访问搜索URL"""
        print(f"使用备用搜索方法: {keyword}")
        encoded_keyword = keyword.replace(' ', '%20')
        search_url = f'https://www.xiaohongshu.com/search_result?keyword={encoded_keyword}'

        print(f"直接访问搜索URL: {search_url}")
        self.driver.get(search_url)
        time.sleep(5)

        current_url = self.driver.current_url
        print(f"备用搜索后URL: {current_url}")
        print(f"页面标题: {self.driver.title}")

        if 'search_result' not in current_url and 'search' not in current_url.lower():
            print("警告: 备用搜索方法也可能失败")
            print("可能需要手动检查页面状态")

    def _get_selector(self, key, default=None):
        """获取选择器，支持回退到默认值"""
        if config and hasattr(config, 'SELECTORS') and key in config.SELECTORS:
            return config.SELECTORS[key]
        return default

    def _check_filter_panel(self):
        """检查筛选面板是否可见"""
        try:
            print("\n=== 检查筛选面板 ===")

            # 方法1: 查找筛选面板
            panel_selectors = [
                '.filter-panel',
                '.filter-container',
                '.filters-wrapper',
                '[class*="filter-panel"]',
                '[class*="filter-container"]',
                '[data-v-eb91fffe][class*="filter-panel"]',
                '[data-v-eb91fffe][class*="filter-container"]',
                '.ant-dropdown',  # Ant Design下拉组件
                '.ant-popover',   # Ant Design弹出框
                '.dropdown-menu', # 通用下拉菜单
                '.popover-content', # 弹出内容
                '.modal-content', # 模态框内容
                '.dialog-content', # 对话框内容
                '[role="dialog"]', # 对话框角色
                '[role="menu"]',   # 菜单角色
                '[role="listbox"]' # 列表框角色
            ]

            for selector in panel_selectors:
                panels = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if panels:
                    panel = panels[0]
                    if panel.is_displayed():
                        print(f"方法1: 找到筛选面板: {selector}")
                        print(f"面板可见性: {panel.is_displayed()}")
                        print(f"面板文本前200字符: {panel.text[:200]}")
                        return True
                    else:
                        print(f"方法1: 找到隐藏面板: {selector}")

            # 方法2: 查找所有显示状态为block或visible的元素
            print("\n方法2: 查找所有显示状态为block或visible的div元素...")
            visible_divs = self.driver.find_elements(By.CSS_SELECTOR, 'div[style*="display: block"], div[style*="display:flex"], div[style*="display: grid"], div[style*="visibility: visible"]')

            if visible_divs:
                print(f"找到 {len(visible_divs)} 个显示状态为block/flex/grid/visible的div")

                # 检查这些div是否包含筛选相关文本
                for i, div in enumerate(visible_divs[:5]):  # 只检查前5个
                    try:
                        div_text = div.text.strip()
                        if div_text and ('筛选' in div_text or 'filter' in div_text.lower() or '时间' in div_text or '排序' in div_text):
                            print(f"  可疑div {i+1}: 包含筛选文本 '{div_text[:50]}'")
                            print(f"  位置: {div.location}, 大小: {div.size}")
                            return True
                    except:
                        continue

            # 方法3: 检查页面中是否有筛选选项
            print("\n方法3: 查找筛选选项元素...")
            filter_options = self.driver.find_elements(By.XPATH, "//*[contains(text(), '一天内') or contains(text(), '24小时') or contains(text(), '发布时间') or contains(text(), '发帖时间') or contains(text(), '最新') or contains(text(), '排序')]")
            if filter_options:
                print(f"找到 {len(filter_options)} 个筛选选项元素")
                for i, option in enumerate(filter_options[:5]):
                    try:
                        if option.is_displayed():
                            print(f"  选项 {i+1}: '{option.text[:50]}' (显示: {option.is_displayed()}, 位置: {option.location})")
                            return True
                        else:
                            print(f"  选项 {i+1}: '{option.text[:50]}' (隐藏)")
                    except:
                        print(f"  选项 {i+1}: 检查失败")

            # 方法4: 查找最近添加的DOM元素（动态加载的面板）
            print("\n方法4: 查找最近添加的DOM元素...")
            try:
                # 通过JavaScript查找最近添加的具有较大z-index的元素
                script = """
                var elements = document.querySelectorAll('div, section, aside, nav, dialog');
                var candidates = [];
                for (var i = 0; i < elements.length; i++) {
                    var elem = elements[i];
                    var style = window.getComputedStyle(elem);
                    var zIndex = parseInt(style.zIndex) || 0;
                    var display = style.display;
                    var visibility = style.visibility;
                    var opacity = parseFloat(style.opacity) || 1;

                    // 检查是否可见
                    var isVisible = elem.offsetWidth > 0 && elem.offsetHeight > 0 &&
                                   display !== 'none' && visibility !== 'hidden' && opacity > 0;

                    if (isVisible && zIndex > 1000) {
                        candidates.push({
                            element: elem,
                            zIndex: zIndex,
                            text: elem.textContent.substring(0, 100)
                        });
                    }
                }

                // 按z-index排序
                candidates.sort(function(a, b) {
                    return b.zIndex - a.zIndex;
                });

                return candidates.slice(0, 5);
                """

                candidates = self.driver.execute_script(script)
                if candidates and len(candidates) > 0:
                    print(f"找到 {len(candidates)} 个高z-index元素:")
                    for i, candidate in enumerate(candidates):
                        print(f"  元素 {i+1}: z-index={candidate['zIndex']}, 文本='{candidate['text'][:50]}'")

                        # 检查是否包含筛选相关文本
                        if '筛选' in candidate['text'] or 'filter' in candidate['text'].lower():
                            print(f"    包含筛选文本，可能是筛选面板")
                            return True
            except Exception as e:
                print(f"方法4执行出错: {e}")

            # 方法5: 检查是否有点击后的视觉变化（通过截图对比）
            print("\n方法5: 检查页面视觉变化...")
            try:
                # 获取当前页面所有元素的边界框
                script2 = """
                var elements = document.querySelectorAll('div[class*="filter"], div[data-testid*="filter"], .ant-dropdown, .ant-popover');
                var results = [];
                for (var i = 0; i < elements.length; i++) {
                    var elem = elements[i];
                    var rect = elem.getBoundingClientRect();
                    if (rect.width > 0 && rect.height > 0) {
                        results.push({
                            className: elem.className,
                            id: elem.id || '',
                            width: rect.width,
                            height: rect.height,
                            top: rect.top,
                            left: rect.left,
                            text: elem.textContent.substring(0, 50)
                        });
                    }
                }
                return results;
                """

                filter_elements = self.driver.execute_script(script2)
                if filter_elements and len(filter_elements) > 0:
                    print(f"找到 {len(filter_elements)} 个筛选相关元素:")
                    for i, elem in enumerate(filter_elements[:3]):
                        print(f"  元素 {i+1}: class='{elem['className']}', id='{elem['id']}'")
                        print(f"    大小: {elem['width']}x{elem['height']}, 位置: ({elem['left']}, {elem['top']})")
                        print(f"    文本: '{elem['text']}'")
            except Exception as e:
                print(f"方法5执行出错: {e}")

            print("\n=== 检查完成: 未找到可见的筛选面板或选项 ===")
            return False

        except Exception as e:
            print(f"检查筛选面板时出错: {e}")
            return False

    def _debug_page_structure(self):
        """调试页面结构，打印筛选相关区域的HTML"""
        print("\n=== 调试页面结构 ===")

        try:
            # 1. 获取整个页面的HTML（精简版）
            page_html = self.driver.page_source
            print(f"页面HTML总长度: {len(page_html)} 字符")

            # 2. 查找筛选按钮附近的HTML结构
            print("\n查找筛选按钮附近的HTML结构:")
            filter_buttons = self.driver.find_elements(By.CSS_SELECTOR, '[class*="filter"], [data-testid*="filter"]')
            for i, btn in enumerate(filter_buttons):
                btn_html = btn.get_attribute('outerHTML')
                print(f"\n筛选按钮 {i+1} HTML (前500字符):")
                print(btn_html[:500])

                # 获取父元素的HTML
                try:
                    parent = btn.find_element(By.XPATH, "./..")
                    parent_html = parent.get_attribute('outerHTML')
                    print(f"父元素HTML (前800字符):")
                    print(parent_html[:800])
                except:
                    print("无法获取父元素HTML")

            # 3. 查找所有可能的下拉/弹出组件
            print("\n查找所有下拉/弹出组件:")
            popup_selectors = [
                '.ant-dropdown',
                '.ant-popover',
                '.dropdown-menu',
                '.popover-content',
                '.modal',
                '.dialog',
                '[role="dialog"]',
                '[role="menu"]',
                '[role="listbox"]'
            ]

            for selector in popup_selectors:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    print(f"\n找到 {len(elements)} 个 '{selector}' 元素:")
                    for j, elem in enumerate(elements[:2]):
                        if elem.is_displayed():
                            elem_html = elem.get_attribute('outerHTML')
                            print(f"元素 {j+1} (显示中) HTML (前1000字符):")
                            print(elem_html[:1000])
                        else:
                            print(f"元素 {j+1} (隐藏)")

            # 4. 查找所有包含时间或排序文本的元素
            print("\n查找包含筛选文本的元素:")
            filter_texts = ['发布时间', '发帖时间', '一天内', '24小时', '最新', '排序', 'filter', '筛选', '过滤']

            for text in filter_texts:
                try:
                    elements = self.driver.find_elements(By.XPATH, f"//*[contains(text(), '{text}')]")
                    if elements:
                        print(f"\n包含 '{text}' 的元素 ({len(elements)} 个):")
                        for j, elem in enumerate(elements[:3]):
                            if elem.is_displayed():
                                elem_html = elem.get_attribute('outerHTML')
                                print(f"元素 {j+1} (显示): '{elem.text[:50]}'")
                                print(f"HTML (前300字符): {elem_html[:300]}")
                except:
                    pass

            # 5. 检查页面body的class和data属性
            print("\n页面body属性:")
            body = self.driver.find_element(By.TAG_NAME, 'body')
            body_class = body.get_attribute('class') or ''
            body_data_attrs = []
            for i in range(10):
                attr = body.get_attribute(f'data-v-{i:06x}')
                if attr:
                    body_data_attrs.append(f'data-v-{i:06x}')

            print(f"body class: '{body_class}'")
            print(f"body data属性: {body_data_attrs}")

            print("\n=== 调试完成 ===")

        except Exception as e:
            print(f"调试页面结构时出错: {e}")

    def _debug_filter_structure(self):
        """专门调试筛选器结构，获取详细的筛选面板HTML"""
        print("\n=== 详细筛选器结构调试 ===")

        try:
            # 1. 获取当前页面所有可见元素的边界信息
            print("1. 页面中所有包含'筛选'、'filter'、'时间'、'排序'文本的元素:")
            search_texts = ['筛选', 'filter', '时间', '排序', '最新', '一天内', '24小时', '发布时间', '发帖时间']

            for text in search_texts:
                try:
                    elements = self.driver.find_elements(By.XPATH, f"//*[contains(text(), '{text}')]")
                    if elements:
                        print(f"\n  '{text}' 相关元素 ({len(elements)} 个):")
                        for i, elem in enumerate(elements[:5]):  # 只显示前5个
                            try:
                                location = elem.location
                                size = elem.size
                                tag = elem.tag_name
                                elem_class = elem.get_attribute('class') or ''
                                elem_id = elem.get_attribute('id') or ''
                                text_content = elem.text.strip()[:50] if elem.text else ''

                                print(f"    元素 {i+1}: <{tag}> id='{elem_id}' class='{elem_class}'")
                                print(f"        文本: '{text_content}'")
                                print(f"        位置: ({location['x']}, {location['y']}) 大小: {size['width']}x{size['height']}")
                                print(f"        显示: {elem.is_displayed()}, 启用: {elem.is_enabled()}")

                                # 如果是按钮或可点击元素，获取更多属性
                                if tag in ['button', 'a', 'div', 'span']:
                                    role = elem.get_attribute('role') or ''
                                    onclick = elem.get_attribute('onclick') or ''
                                    data_testid = elem.get_attribute('data-testid') or ''
                                    if role or onclick or data_testid:
                                        print(f"        角色: '{role}', onclick: '{onclick[:50]}', data-testid: '{data_testid}'")
                            except:
                                print(f"    元素 {i+1}: 获取信息失败")
                except Exception as e:
                    print(f"  搜索文本'{text}'时出错: {e}")

            # 2. 获取筛选按钮及周围完整HTML结构（向上3级父元素）
            print("\n2. 筛选按钮及其周围结构:")
            filter_selectors = [
                '[class*="filter"]',
                '[data-testid*="filter"]',
                '[data-v-eb91fffe][class*="filter"]',
                '[data-v-eb91fffe] .filter-icon',
                '.reds-icon.filter-icon'
            ]

            for selector in filter_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        print(f"\n  选择器 '{selector}' 找到 {len(elements)} 个元素:")
                        for i, elem in enumerate(elements[:3]):  # 只检查前3个
                            try:
                                # 获取元素本身及其向上3级父元素的完整HTML
                                print(f"\n    元素 {i+1}:")

                                # 当前元素
                                elem_html = elem.get_attribute('outerHTML')
                                print(f"      当前元素HTML (前500字符):")
                                print(f"      {elem_html[:500]}")

                                # 父元素
                                parent = elem.find_element(By.XPATH, "./..")
                                parent_html = parent.get_attribute('outerHTML')
                                print(f"      父元素HTML (前800字符):")
                                print(f"      {parent_html[:800]}")

                                # 祖父元素
                                grandparent = parent.find_element(By.XPATH, "./..")
                                grandparent_html = grandparent.get_attribute('outerHTML')
                                print(f"      祖父元素HTML (前1000字符):")
                                print(f"      {grandparent_html[:1000]}")

                                # 曾祖父元素
                                great_grandparent = grandparent.find_element(By.XPATH, "./..")
                                great_grandparent_html = great_grandparent.get_attribute('outerHTML')
                                print(f"      曾祖父元素HTML (前1200字符):")
                                print(f"      {great_grandparent_html[:1200]}")

                            except Exception as e:
                                print(f"      获取元素 {i+1} 结构时出错: {e}")
                except Exception as e:
                    print(f"  选择器 '{selector}' 执行出错: {e}")

            # 3. 查找所有可能的弹出层/下拉层
            print("\n3. 查找所有弹出层/下拉层:")
            popup_selectors = [
                'div[style*="display: block"]',
                'div[style*="visibility: visible"]',
                'div[class*="dropdown"]',
                'div[class*="popover"]',
                'div[class*="modal"]',
                'div[class*="dialog"]',
                'div[class*="overlay"]',
                'div[role="dialog"]',
                'div[role="menu"]',
                'div[role="listbox"]',
                'div[class*="ant-dropdown"]',
                'div[class*="ant-popover"]',
                'div[class*="ant-select-dropdown"]',
                'div[class*="ant-picker-dropdown"]'
            ]

            for selector in popup_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        print(f"\n  选择器 '{selector}' 找到 {len(elements)} 个元素:")
                        for i, elem in enumerate(elements[:2]):  # 只检查前2个
                            try:
                                is_displayed = elem.is_displayed()
                                location = elem.location
                                size = elem.size
                                elem_html = elem.get_attribute('outerHTML')

                                print(f"    元素 {i+1}: 显示={is_displayed}, 位置={location}, 大小={size}")
                                print(f"    HTML (前800字符):")
                                print(f"    {elem_html[:800]}")
                            except:
                                print(f"    元素 {i+1}: 获取信息失败")
                except Exception as e:
                    print(f"  选择器 '{selector}' 执行出错: {e}")

            # 4. 检查页面是否有iframe
            print("\n4. 检查页面iframe:")
            try:
                iframes = self.driver.find_elements(By.TAG_NAME, 'iframe')
                if iframes:
                    print(f"  找到 {len(iframes)} 个iframe:")
                    for i, iframe in enumerate(iframes):
                        try:
                            iframe_id = iframe.get_attribute('id') or ''
                            iframe_class = iframe.get_attribute('class') or ''
                            iframe_src = iframe.get_attribute('src') or ''
                            print(f"    iframe {i+1}: id='{iframe_id}', class='{iframe_class}', src='{iframe_src[:100]}'")
                        except:
                            print(f"    iframe {i+1}: 获取信息失败")
                else:
                    print("  未找到iframe")
            except Exception as e:
                print(f"  检查iframe时出错: {e}")

            # 5. 保存当前页面HTML到文件（用于离线分析）
            print("\n5. 保存页面HTML到文件...")
            try:
                import os
                from datetime import datetime

                # 创建debug目录
                debug_dir = os.path.join(os.path.dirname(__file__), 'debug_html')
                if not os.path.exists(debug_dir):
                    os.makedirs(debug_dir)

                # 生成文件名
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"page_debug_{timestamp}.html"
                filepath = os.path.join(debug_dir, filename)

                # 保存完整HTML
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(self.driver.page_source)

                print(f"  页面HTML已保存到: {filepath}")

                # 保存精简版（只包含body内容）
                try:
                    body_html = self.driver.find_element(By.TAG_NAME, 'body').get_attribute('outerHTML')
                    body_filename = f"body_debug_{timestamp}.html"
                    body_filepath = os.path.join(debug_dir, body_filename)

                    with open(body_filepath, 'w', encoding='utf-8') as f:
                        f.write(body_html)

                    print(f"  Body HTML已保存到: {body_filepath}")
                except:
                    print("  保存Body HTML失败")

            except Exception as e:
                print(f"  保存HTML文件时出错: {e}")

            print("\n=== 详细筛选器调试完成 ===")

        except Exception as e:
            print(f"详细筛选器结构调试时出错: {e}")

    def apply_filters(self, keyword=None):
        """应用筛选条件：发帖时间-一天内，排序依据-最新"""
        print("\n>>> ENTER apply_filters method <<<")
        if keyword is None:
            # 如果没有提供keyword，尝试从调用栈获取
            import inspect
            frame = inspect.currentframe()
            try:
                # 查找run方法中的keyword
                while frame:
                    if frame.f_code.co_name == 'run' and 'keyword' in frame.f_locals:
                        keyword = frame.f_locals['keyword']
                        break
                    frame = frame.f_back
            finally:
                del frame
        try:
            # 获取筛选按钮选择器
            filter_selector = self._get_selector('filter_button', '.filter, .filter-btn, .ant-dropdown-trigger, [data-testid="filter"], [class*="filter"], .filter-icon, [class*="filter-icon"], .reds-icon.filter-icon, [data-v-eb91fffe][class*="filter"], [data-v-eb91fffe] .filter-icon')

            print(f"尝试使用选择器查找筛选按钮: {filter_selector}")

            # ========== 调试日志开始 ==========
            print("\n=== [调试] 页面状态检查 ===")
            current_url = self.driver.current_url
            print(f"[调试] 当前页面URL: {current_url}")

            # 测试各种选择器
            print("\n[调试] 测试各种选择器:")
            test_selectors = [
                '.filter',
                '[data-v-eb91fffe].filter',
                '.filter-icon',
                '[class*="filter"]',
                'span'
            ]
            for sel in test_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, sel)
                    print(f"  选择器 '{sel}': 找到 {len(elements)} 个元素")
                    if len(elements) > 0 and len(elements) <= 3:
                        for i, el in enumerate(elements):
                            text = el.text[:30] if el.text else ''
                            class_name = el.get_attribute('class') or ''
                            print(f"    [{i}] tag={el.tag_name}, class={class_name[:50]}, text={text}")
                except Exception as e:
                    print(f"  选择器 '{sel}': 错误 - {e}")

            # 查找包含"筛选"文本的所有元素
            print("\n[调试] 查找包含'筛选'文本的元素:")
            try:
                all_elements = self.driver.find_elements(By.XPATH, "//*[contains(text(), '筛选') or contains(text(), '已筛选')]")
                print(f"  找到 {len(all_elements)} 个包含'筛选'文本的元素")
                for i, el in enumerate(all_elements[:5]):
                    text = el.text.strip() if el.text else ''
                    class_name = el.get_attribute('class') or ''
                    parent = el.find_element(By.XPATH, "./..")
                    parent_class = parent.get_attribute('class') or ''
                    print(f"    [{i}] tag={el.tag_name}, text='{text}', class={class_name[:50]}, parent_class={parent_class[:50]}")
            except Exception as e:
                print(f"  查找失败: {e}")

            print("=== [调试] 页面状态检查结束 ===\n")
            # ========== 调试日志结束 ==========

            # 首先检查当前页面是否在搜索结果页
            if 'search_result' not in current_url and 'search' not in current_url.lower():
                print("警告: 当前页面可能不是搜索结果页")
                print("可能搜索未成功或页面已跳转")

            if 'search_result' not in current_url and 'search' not in current_url.lower():
                print("警告: 当前页面可能不是搜索结果页")
                print("可能搜索未成功或页面已跳转")

                if keyword:
                    print("尝试直接访问搜索结果页...")
                    encoded_keyword = keyword.replace(' ', '%20')
                    search_url = f'https://www.xiaohongshu.com/search_result?keyword={encoded_keyword}'
                    self.driver.get(search_url)
                    time.sleep(5)
                    print(f"已跳转到: {self.driver.current_url}")
                else:
                    print("错误: keyword为空，无法直接访问搜索结果页")
                    print("请确保搜索步骤成功执行")

            # 在点击前先查找所有匹配的元素，打印详细信息
            print("\n查找所有匹配的按钮元素:")
            all_buttons = self.driver.find_elements(By.CSS_SELECTOR, filter_selector)
            print(f"找到 {len(all_buttons)} 个匹配元素")

            for i, btn in enumerate(all_buttons):
                btn_text = btn.text.strip() if btn.text else ''
                btn_class = btn.get_attribute('class') or ''
                btn_tag = btn.tag_name
                btn_href = btn.get_attribute('href') or ''
                btn_data_testid = btn.get_attribute('data-testid') or ''
                btn_onclick = btn.get_attribute('onclick') or ''

                print(f"\n按钮 {i+1}:")
                print(f"  标签: <{btn_tag}>")
                print(f"  文本: '{btn_text}'")
                print(f"  class: '{btn_class}'")
                print(f"  href: '{btn_href[:50]}'")
                print(f"  data-testid: '{btn_data_testid}'")
                print(f"  onclick: '{btn_onclick[:50]}'")
                print(f"  是否可点击: {btn.is_enabled()} and {btn.is_displayed()}")

            # 策略1：优先点击包含"筛选"文本的DIV元素
            target_button = None
            click_strategy = None

            for btn in all_buttons:
                btn_text = btn.text.strip() if btn.text else ''
                btn_class = btn.get_attribute('class') or ''
                btn_tag = btn.tag_name.lower()

                # 策略1：优先选择包含"筛选"文本的DIV
                if btn_tag == 'div' and '筛选' in btn_text:
                    target_button = btn
                    click_strategy = "策略1: 点击包含'筛选'文本的DIV"
                    print(f"\n{click_strategy}: '{btn_text}' (class: '{btn_class}')")
                    break

            # 策略2：如果没有找到，尝试点击SVG图标
            if not target_button:
                for btn in all_buttons:
                    btn_class = btn.get_attribute('class') or ''
                    btn_tag = btn.tag_name.lower()

                    if btn_tag == 'svg' and 'filter-icon' in btn_class:
                        target_button = btn
                        click_strategy = "策略2: 点击filter-icon SVG图标"
                        print(f"\n{click_strategy}: class='{btn_class}'")
                        break

            # 策略3：如果没有找到，选择第一个元素
            if not target_button and all_buttons:
                target_button = all_buttons[0]
                btn_text = target_button.text.strip() if target_button.text else ''
                btn_class = target_button.get_attribute('class') or ''
                btn_tag = target_button.tag_name.lower()
                click_strategy = f"策略3: 点击第一个元素 ({btn_tag})"
                print(f"\n{click_strategy}: '{btn_text}' (class: '{btn_class}')")

            if not target_button:
                print("警告: 未找到筛选按钮，跳过筛选步骤")
                print("将直接提取当前页面帖子...")
                return

            # 点击前保存当前URL
            before_url = self.driver.current_url
            print(f"点击前URL: {before_url}")

            # 方法1：尝试JavaScript点击（更可靠）
            print(f"尝试方法1: JavaScript点击")
            # 先滚动到视图
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", target_button)
            time.sleep(0.5)
            self.driver.execute_script("arguments[0].click();", target_button)
            print("已点击按钮")

            # 等待面板出现
            print("等待筛选面板出现...")
            time.sleep(3)

            # 检查面板是否出现
            panel_found = self._check_filter_panel()

            if not panel_found:
                print("方法1失败：筛选面板未出现")
                print("尝试方法2: 使用JavaScript点击")

                # 方法2：使用JavaScript点击
                self.driver.execute_script("arguments[0].click();", target_button)
                time.sleep(3)
                panel_found = self._check_filter_panel()

                if not panel_found:
                    print("方法2失败：筛选面板仍未出现")
                    print("尝试方法3: 点击父元素")

                    # 方法3：尝试点击父元素
                    try:
                        parent = target_button.find_element(By.XPATH, "./..")
                        if parent:
                            parent.click()
                            time.sleep(3)
                            panel_found = self._check_filter_panel()
                    except:
                        print("方法3失败：无法点击父元素")

                # 等待并检查URL是否变化
                after_url = self.driver.current_url
                print(f"点击后URL: {after_url}")

                if before_url != after_url:
                    print(f"警告: 页面跳转，从 {before_url} 到 {after_url}")

                    # 如果是跳转到探索页，返回搜索结果页
                    if 'explore' in after_url:
                        print("检测到跳转到探索页，返回搜索结果页...")
                        self.driver.back()
                        time.sleep(3)
                        print(f"返回后URL: {self.driver.current_url}")

                        # 重新尝试查找筛选按钮
                        return self.apply_filters(keyword=keyword)

            # 检查筛选面板是否出现
            if not panel_found:
                print("警告: 筛选面板未出现，无法进行筛选")
                print("将尝试直接查找筛选选项...")

                # 调试：保存当前页面HTML结构
                self._debug_page_structure()
                self._debug_filter_structure()

            # 选择"发帖时间-一天内"
            print("\n=== 尝试选择'一天内'选项 ===")
            one_day_selected = False

            # 方法1: 查找标签形式的选项
            try:
                tag_item_selector = self._get_selector('tag_item', '[data-v-eb91fffe].tags, .tags, .tag-item, .filter-tag, [class*="tag"]')
                all_tags = self.driver.find_elements(By.CSS_SELECTOR, tag_item_selector)
                print(f"找到 {len(all_tags)} 个标签元素")

                for i, tag in enumerate(all_tags):
                    if one_day_selected:
                        break
                    tag_text = tag.text.strip() if tag.text else ''
                    tag_class = tag.get_attribute('class') or ''
                    if not tag_text:
                        continue
                    print(f"  标签 {i+1}: '{tag_text}' (class: '{tag_class}')")

                    time_keywords = ['一天内', '24小时', '1天内', '今天', '今日']
                    for keyword in time_keywords:
                        if keyword in tag_text:
                            if '\n' in tag_text or len(tag_text) > 10:
                                print(f"  跳过父容器: '{tag_text[:50]}...'")
                                continue
                            print(f"  找到时间选项: '{tag_text}'")
                            self.driver.execute_script("arguments[0].click();", tag)
                            print(f"  已点击时间选项: '{tag_text}'")
                            time.sleep(2)
                            try:
                                new_class = tag.get_attribute('class') or ''
                                if 'active' in new_class:
                                    print(f"  ✓ 验证成功：'{tag_text}'已被选中")
                                    one_day_selected = True
                                    break
                                else:
                                    print(f"  ⚠️ 点击后未变成active状态")
                            except:
                                print(f"  ⚠️ 无法验证点击状态，假设成功")
                                one_day_selected = True
                                break
            except Exception as e:
                print(f"方法1失败: {e}")

            # 方法2: 使用 data-hp-kind 属性精确定位
            if not one_day_selected:
                try:
                    one_day_elem = self.driver.find_element(By.CSS_SELECTOR, '[data-hp-kind="filter-tag--一天内"]')
                    print("方法2: 使用 data-hp-kind 找到'一天内'元素")
                    parent = one_day_elem.find_element(By.XPATH, "ancestor::div[@data-v-eb91fffe][contains(@class, 'tags')]")
                    print(f"  找到真正的按钮，class: {parent.get_attribute('class')}")
                    self.driver.execute_script("arguments[0].click();", parent)
                    print("  已点击'一天内'选项（通过 data-hp-kind 定位）")
                    one_day_selected = True
                    time.sleep(1)
                except Exception as e:
                    print(f"方法2失败: {e}")

            # 方法3: 直接找包含"一天内"文本的元素
            if not one_day_selected:
                try:
                    one_day_elements = self.driver.find_elements(By.XPATH, "//*[text()='一天内']")
                    print(f"方法3: 找到 {len(one_day_elements)} 个'一天内'文本元素")
                    for elem in one_day_elements:
                        if one_day_selected:
                            break
                        parent = elem.find_element(By.XPATH, "./..")
                        parent_class = parent.get_attribute('class') or ''
                        has_data_attr = parent.get_attribute('data-v-eb91fffe') is not None
                        if 'tags' in parent_class and has_data_attr:
                            print(f"  点击'一天内'选项")
                            self.driver.execute_script("arguments[0].click();", parent)
                            one_day_selected = True
                            time.sleep(1)
                            break
                except Exception as e:
                    print(f"方法3失败: {e}")

            # Fallback: 如果DOM点击都失败，尝试直接刷新URL带参数
            if not one_day_selected:
                print("⚠️ DOM点击未能选中'一天内'，尝试URL参数回退...")
                try:
                    current_url = self.driver.current_url
                    if 'search_result' in current_url:
                        import urllib.parse as urlparse
                        parsed = urlparse.urlparse(current_url)
                        qs = urlparse.parse_qs(parsed.query)
                        qs['publish_time'] = ['one_day']
                        qs['sort'] = ['general']
                        new_query = urlparse.urlencode(qs, doseq=True)
                        new_url = urlparse.urlunparse(parsed._replace(query=new_query))
                        self.driver.get(new_url)
                        time.sleep(4)
                        print(f"已使用URL参数回退刷新: {self.driver.current_url}")
                        one_day_selected = True
                except Exception as e:
                    print(f"URL参数回退失败: {e}")

            # 选择"排序依据-最新"
            print("\n=== 尝试选择'最新'排序 ===")
            latest_selected = False  # 成功标志

            # 方法0: 使用新的小红书结构 - div.tags 包含 span[data-v-eb91fffe]
            try:
                # 查找所有带有 data-v-eb91fffe 的 .tags 元素
                latest_tags = self.driver.find_elements(By.CSS_SELECTOR, '[data-v-eb91fffe].tags')
                print(f"方法0: 找到 {len(latest_tags)} 个 tags 元素")

                for tag in latest_tags:
                    if latest_selected:
                        break
                    tag_text = tag.text.strip() if tag.text else ''
                    if tag_text and '最新' in tag_text:
                        # 检查是否是单独的选项（不是包含多个选项的父容器）
                        if '\n' in tag_text or len(tag_text) > 5:
                            print(f"  跳过父容器: '{tag_text[:50]}...'")
                            continue
                        print(f"  找到'最新'选项: '{tag_text}'")
                        self.driver.execute_script("arguments[0].click();", tag)
                        print("  已点击'最新'选项")
                        latest_selected = True
                        time.sleep(1)
                        break
            except Exception as e:
                print(f"排序方法0失败: {e}")

            # 方法1: 查找排序下拉菜单
            if not latest_selected:
                try:
                    sort_selectors = [
                        '.sort-select',
                        '.sort-dropdown',
                        '[class*="sort"]',
                        '[data-testid*="sort"]',
                        'select',  # 原生下拉框
                        'option[value*="latest"]',  # 最新选项
                        'option[value*="time"]'     # 时间排序选项
                    ]

                    for selector in sort_selectors:
                        if latest_selected:
                            break
                        sort_elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        if sort_elements:
                            print(f"找到排序元素: {selector}")
                            for elem in sort_elements:
                                if '最新' in elem.text or '时间' in elem.text or 'latest' in elem.text.lower():
                                    print(f"  点击排序选项: {elem.text[:50]}")
                                    self.driver.execute_script("arguments[0].click();", elem)
                                    latest_selected = True
                                    time.sleep(1)
                                    break
                            break
                except Exception as e:
                    print(f"排序方法1失败: {e}")

            # 方法2: 直接查找"最新"文本
            if not latest_selected:
                try:
                    latest_texts = ['最新', '最新发布', '最新发帖', '时间排序', '按时间']
                    for text in latest_texts:
                        if latest_selected:
                            break
                        elements = self.driver.find_elements(By.XPATH, f"//*[contains(text(), '{text}')]")
                        if elements:
                            print(f"找到 {len(elements)} 个包含'{text}'的元素")
                            for elem in elements:
                                if elem.is_displayed() and elem.is_enabled():
                                    print(f"  点击排序: {elem.text[:50]}")
                                    self.driver.execute_script("arguments[0].click();", elem)
                                    latest_selected = True
                                    time.sleep(1)
                                    break
                            break
                except Exception as e:
                    print(f"排序方法2失败: {e}")

            # 方法3: 查找按钮或链接形式的排序
            try:
                sort_buttons = self.driver.find_elements(By.CSS_SELECTOR, 'button, a, .btn, .button, [role="button"]')
                print(f"找到 {len(sort_buttons)} 个按钮/链接元素")

                for btn in sort_buttons:
                    btn_text = btn.text.strip() if btn.text else ''
                    if btn_text and ('最新' in btn_text or '时间' in btn_text):
                        print(f"  找到排序按钮: {btn_text}")
                        btn.click()
                        time.sleep(1)
                        break
            except Exception as e:
                print(f"排序方法3失败: {e}")

            # 点击确认或应用按钮（如果有）
            print("\n=== 尝试应用筛选条件 ===")
            try:
                apply_selector = self._get_selector('apply_button', 'button.ant-btn-primary, button.apply-btn, .confirm-btn, .filter-panel button, .filter-container button, .filters-wrapper button')
                apply_buttons = self.driver.find_elements(By.CSS_SELECTOR, apply_selector)

                if apply_buttons:
                    print(f"找到 {len(apply_buttons)} 个应用按钮")
                    for btn in apply_buttons:
                        if btn.is_displayed() and btn.is_enabled():
                            print(f"  点击应用按钮: {btn.text[:30]}")
                            btn.click()
                            time.sleep(2)
                            break
                else:
                    print("未找到应用按钮，可能自动应用或不需要确认")
            except Exception as e:
                print(f"应用筛选条件时出错: {e}")

            print("\n筛选流程完成")

            # 1. 点击页面空白处关闭筛选面板（如果还开着）
            print("尝试点击页面空白处关闭筛选面板...")
            try:
                # 点击body元素
                body = self.driver.find_element(By.TAG_NAME, 'body')
                body.click()
                print("已点击页面空白处")
            except Exception as e:
                print(f"点击空白处失败: {e}")

            # 2. 等待筛选生效（用户建议停留两秒）
            print("等待筛选生效（3秒）...")
            time.sleep(3)

            # 3. 验证筛选是否生效（不强制刷新，避免重置筛选状态）
            print("验证筛选条件是否已应用...")
            self.verify_filters_applied()

            # 4. 等待页面内容完全加载
            print("等待页面内容完全加载（2秒）...")
            time.sleep(2)

        except TimeoutException as e:
            print(f"筛选按钮未找到: {e}")
            print("可能页面结构已变化，将尝试直接查找元素...")

            # 直接查找所有可能元素
            try:
                all_elements = self.driver.find_elements(By.CSS_SELECTOR, '[class*="filter"], [class*="Filter"], [data-testid*="filter"], [data-testid*="Filter"]')
                print(f"找到 {len(all_elements)} 个可能包含'filter'的元素")
                for i, elem in enumerate(all_elements[:5]):  # 只显示前5个
                    print(f"  {i+1}. class: '{elem.get_attribute('class')}', text: '{elem.text[:30]}'")
            except:
                pass

    def verify_filters_applied(self):
        """验证筛选条件是否已应用"""
        print("\n=== 验证筛选条件 ===")

        # 1. 检查URL是否有筛选参数
        current_url = self.driver.current_url
        print(f"当前URL: {current_url}")

        # 小红书常见筛选参数
        filter_keywords = ['time=', 'sort=', 'filter=', 'latest', 'day', '24h', 'time_filter', 'sort_type']
        for keyword in filter_keywords:
            if keyword in current_url.lower():
                print(f"✓ URL包含筛选参数: {keyword}")

        # 2. 检查页面上的筛选状态标签
        try:
            # 查找激活的筛选标签
            active_selector = self._get_selector('active_tag', '.tags.active, .tag-item.active, .filter-tag.active')
            active_tags = self.driver.find_elements(By.CSS_SELECTOR, active_selector)

            if active_tags:
                print(f"找到 {len(active_tags)} 个激活的筛选标签:")
                for tag in active_tags:
                    tag_text = tag.text.strip() if tag.text else ''
                    if tag_text:
                        print(f"  ✓ {tag_text[:50]}")
            else:
                print("未找到激活的筛选标签，可能筛选未生效")

                # 尝试查找任何显示筛选状态的元素
                filter_status_texts = ['一天内', '24小时', '最新', '按时间', '发布时间', '发帖时间']
                for text in filter_status_texts:
                    elements = self.driver.find_elements(By.XPATH, f"//*[contains(text(), '{text}')]")
                    if elements:
                        for elem in elements:
                            if elem.is_displayed():
                                print(f"  找到筛选状态文本: '{elem.text[:50]}'")
        except Exception as e:
            print(f"检查筛选状态时出错: {e}")

        # 3. 等待页面内容刷新
        print("等待页面刷新（3秒）...")
        time.sleep(3)

    def scroll_to_load_more(self, scroll_times: int = 10, scroll_pause: float = 2.0):
        """
        滚动加载更多内容

        Args:
            scroll_times: 滚动次数
            scroll_pause: 每次滚动后的暂停时间（秒）
        """
        if scroll_times <= 0:
            print("跳过滚动加载 (scroll_times <= 0)")
            return

        print(f"开始滚动加载，预计滚动 {scroll_times} 次...")

        for i in range(scroll_times):
            # 滚动到底部
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            print(f"第 {i+1}/{scroll_times} 次滚动完成")

            # 等待新内容加载
            time.sleep(scroll_pause)

            # 检查是否有"加载更多"或"没有更多内容"的提示
            page_html = self.driver.page_source
            if '没有更多了' in page_html or 'No more' in page_html:
                print("已加载所有内容")
                break

        print(f"滚动完成，共加载了 {scroll_times} 次")

    def scroll_to_extract_posts(self, target_count: int = 10, max_scroll: int = 20,
                               scroll_pause: float = 2.0, download_images: bool = True,
                               image_dir: str = None) -> List[Dict]:
        """
        滚动并实时提取帖子，直到达到目标数量或最大滚动次数

        Args:
            target_count: 目标提取帖子数量（0表示无限制）
            max_scroll: 最大滚动次数
            scroll_pause: 每次滚动后的暂停时间（秒）
            download_images: 是否下载图片
            image_dir: 图片保存目录

        Returns:
            提取的帖子列表
        """
        if target_count == 0:
            print("目标数量为0，跳过滚动提取")
            return []

        print(f"\n=== 开始滚动提取帖子 ===")
        print(f"目标数量: {target_count}, 最大滚动次数: {max_scroll}")

        extracted_posts = []
        seen_post_ids = set()
        consecutive_no_new = 0  # 连续没有新帖子的次数
        max_consecutive_no_new = 3  # 最大连续无新帖子次数

        # === 新增：提取初始页面帖子 ===
        print("\n=== 提取初始页面帖子 ===")
        initial_posts = self.extract_posts_metadata_only(max_posts=0)
        initial_new_count = 0

        for post in initial_posts:
            post_id = post.get('post_id')
            if post_id and post_id not in seen_post_ids:
                seen_post_ids.add(post_id)
                extracted_posts.append(post)
                initial_new_count += 1

        print(f"初始页面: 找到 {len(initial_posts)} 个帖子，去重后新增 {initial_new_count} 个")
        print(f"当前总计: {len(extracted_posts)} 个帖子")

        # 检查是否已达到目标数量
        if target_count > 0 and len(extracted_posts) >= target_count:
            extracted_posts = extracted_posts[:target_count]
            print(f"初始页面已满足目标数量 {target_count}")
            # 设置 max_scroll = 0 跳过滚动循环
            max_scroll = 0

        # === 继续滚动提取 ===
        print(f"\n=== 开始滚动提取，还需 {max(0, target_count - len(extracted_posts))} 个帖子 ===")

        for scroll_num in range(1, max_scroll + 1):
            print(f"\n滚动 #{scroll_num}/{max_scroll}")

            # 滚动到底部
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

            # 等待新内容加载
            time.sleep(scroll_pause)

            # 提取当前页面所有帖子的元数据（不下载图片）
            current_posts = self.extract_posts_metadata_only(max_posts=0)

            # 去重并统计新帖子
            new_posts_count = 0
            for post in current_posts:
                post_id = post.get('post_id')
                if post_id and post_id not in seen_post_ids:
                    # 这是新帖子
                    seen_post_ids.add(post_id)
                    extracted_posts.append(post)
                    new_posts_count += 1

                    # 检查是否达到目标数量
                    if target_count > 0 and len(extracted_posts) >= target_count:
                        print(f"已达到目标数量 {target_count}")
                        break

            print(f"本次滚动后: 总帖子 {len(extracted_posts)}, 新帖子 {new_posts_count}")

            # 检查是否达到目标数量
            if target_count > 0 and len(extracted_posts) >= target_count:
                extracted_posts = extracted_posts[:target_count]
                break

            # 检查是否没有新帖子
            if new_posts_count == 0:
                consecutive_no_new += 1
                print(f"本次滚动未发现新帖子，连续 {consecutive_no_new} 次")

                if consecutive_no_new >= max_consecutive_no_new:
                    print(f"连续 {max_consecutive_no_new} 次滚动未发现新帖子，停止滚动")
                    break
            else:
                consecutive_no_new = 0  # 重置计数器

            # 检查是否已加载所有内容
            page_html = self.driver.page_source
            if '没有更多了' in page_html or 'No more' in page_html:
                print("已加载所有内容")
                break

        print(f"\n滚动提取完成，共提取 {len(extracted_posts)} 个帖子")

        # 如果需要下载图片，现在下载
        if download_images and extracted_posts:
            print(f"开始下载图片...")
            image_dir = self.create_gallery_directory(image_dir)

            # 从配置获取图片命名方式
            image_naming = 'sequential'
            if config and hasattr(config, 'DATA_EXTRACT_CONFIG'):
                image_naming = config.DATA_EXTRACT_CONFIG.get('image_naming', 'sequential')

            for i, post in enumerate(extracted_posts):
                image_urls = post.get('image_urls', [])
                downloaded_images = []

                if image_urls:
                    print(f"  帖子 {i+1}: 下载 {len(image_urls)} 张图片")

                    for j, img_url in enumerate(image_urls):
                        try:
                            # 生成文件名
                            if image_naming == 'post_id' and post['post_id']:
                                filename = f"{post['post_id']}_{j+1:02d}.jpg"
                            else:
                                filename = f"scroll_post_{i+1:03d}_img_{j+1:02d}.jpg"

                            save_path = os.path.join(image_dir, filename)

                            if self.download_image(img_url, save_path):
                                downloaded_images.append({
                                    'original_url': img_url,
                                    'filename': filename,
                                    'save_path': save_path
                                })
                                print(f"    ✓ 已下载: {filename}")
                            else:
                                print(f"    图片下载失败: {img_url}")
                        except Exception as e:
                            print(f"    处理图片时出错: {e}")
                else:
                    print(f"  帖子 {i+1}: 无图片")

                post['downloaded_images'] = downloaded_images

                # 短暂暂停
                time.sleep(0.3)

            total_images = sum(len(post.get('downloaded_images', [])) for post in extracted_posts)
            print(f"共下载 {total_images} 张图片到 {image_dir}/ 目录")
        else:
            # 即使不下载图片，也要添加空列表
            for post in extracted_posts:
                post['downloaded_images'] = []

        return extracted_posts

    def get_current_posts(self) -> List[Dict]:
        """获取当前页面中的帖子信息（示例）"""
        posts = []
        try:
            # 这里需要根据小红书实际页面结构调整选择器
            post_elements = self.driver.find_elements(By.CSS_SELECTOR, '.note-item, .card, .post-item')

            for i, post in enumerate(post_elements):
                try:
                    post_data = {
                        'index': i,
                        'text': post.text[:100] if post.text else '',  # 截取前100字符
                        'element': post.get_attribute('outerHTML')[:200]  # 保存部分HTML
                    }
                    posts.append(post_data)
                except:
                    continue

            print(f"当前页面找到 {len(posts)} 个帖子")
        except Exception as e:
            print(f"获取帖子信息时出错: {e}")

        return posts

    def extract_post_details(self, post_element) -> Optional[Dict]:
        """
        从单个帖子元素中提取详细信息

        Args:
            post_element: 帖子元素

        Returns:
            包含帖子详情的字典，如果提取失败则返回None
        """
        try:
            # 获取帖子基本信息
            post_text = post_element.text.strip() if post_element.text else ''

            # 如果文本包含"大家都在搜"等非帖子内容，跳过
            if post_text and ('大家都在搜' in post_text or '热门搜索' in post_text or '热门推荐' in post_text):
                print(f"跳过非帖子元素: {post_text[:50]}")
                return None

            # 如果文本为空，尝试使用innerText获取
            if not post_text:
                try:
                    post_text = post_element.get_attribute('innerText') or post_element.get_attribute('textContent') or ''
                    post_text = post_text.strip()
                except:
                    pass

            # 获取帖子链接
            link = None
            try:
                link_elements = post_element.find_elements(By.CSS_SELECTOR, self._get_selector('post_link', 'a[href*="/explore/"], a[href*="/note/"]'))
                if link_elements:
                    link = link_elements[0].get_attribute('href')
            except:
                pass

            # 获取发帖时间和用户ID（小红书通常显示为"用户名 时间"的格式）
            post_time = None
            user_id = None

            # 方法1：尝试分别查找时间和用户元素
            try:
                # 先尝试查找时间元素
                time_elements = post_element.find_elements(By.CSS_SELECTOR, self._get_selector('post_time', '[class*="time"], time, .date, .timestamp, .publish-time, .created-at'))
                if time_elements:
                    time_text = time_elements[0].text.strip()
                    # 如果时间文本包含常见的emoji或用户名，尝试分离
                    if '昨天' in time_text or '小时前' in time_text or '分钟前' in time_text or '今天' in time_text:
                        # 这看起来像是纯时间文本，但可能包含用户名前缀
                        # 例如："抒月🌟37分钟前"
                        # 尝试提取时间部分
                        import re
                        time_patterns = [
                            r'昨天\s*\d{1,2}:\d{2}',  # 昨天 18:31
                            r'\d{1,2}小时前',         # 3小时前
                            r'\d{1,2}分钟前',         # 5分钟前
                            r'今天\s*\d{1,2}:\d{2}',  # 今天 12:30
                            r'\d{1,2}天前',           # 2天前
                        ]
                        time_match = None
                        for pattern in time_patterns:
                            match = re.search(pattern, time_text)
                            if match:
                                time_match = match.group()
                                break
                        if time_match:
                            # 提取时间部分
                            post_time = time_match
                            # 剩余部分可能是用户名
                            remaining = time_text.replace(time_match, '').strip()
                            if remaining and not user_id:
                                user_id = remaining
                        else:
                            # 未匹配到时间模式，保持原样
                            post_time = time_text
                    else:
                        # 可能包含了用户名和时间，尝试分离
                        # 常见的格式: "用户名昨天 18:31" 或 "用户名 昨天 18:31"
                        post_time = time_text
                else:
                    # 如果没找到单独的时间元素，可能和时间一起显示
                    pass
            except:
                pass

            # 尝试查找用户元素
            try:
                user_elements = post_element.find_elements(By.CSS_SELECTOR, self._get_selector('post_user', '[class*="user"], [class*="author"], .username, .author-name, .user-name, .nickname'))
                if user_elements:
                    user_text = user_elements[0].text.strip()
                    user_id = user_text
            except:
                pass

            # 如果帖子文本为空，尝试从所有子元素收集文本
            if not post_text:
                try:
                    # 获取所有子元素的文本
                    all_texts = []
                    child_elements = post_element.find_elements(By.XPATH, ".//*")
                    for child in child_elements:
                        child_text = child.text.strip() if child.text else ''
                        if child_text:
                            all_texts.append(child_text)
                    # 合并去重（保留顺序）
                    seen = set()
                    unique_texts = []
                    for text in all_texts:
                        if text not in seen:
                            seen.add(text)
                            unique_texts.append(text)
                    post_text = ' '.join(unique_texts).strip()
                    if post_text:
                        print(f"从子元素重构文本，长度: {len(post_text)}")
                except Exception as e:
                    print(f"从子元素收集文本时出错: {e}")

            # 方法2：如果时间和用户ID都为空或相同，尝试从帖子文本中提取
            if (not post_time and not user_id) or (post_time == user_id):
                try:
                    # 尝试查找包含用户名和时间的组合元素
                    # 小红书常见格式：整个帖子文本包含用户名和时间信息

                    # 查找时间模式：昨天 HH:MM、X小时前、X分钟前
                    import re

                    # 时间模式
                    time_patterns = [
                        r'昨天\s*\d{1,2}:\d{2}',  # 昨天 18:31
                        r'\d{1,2}小时前',         # 3小时前
                        r'\d{1,2}分钟前',         # 5分钟前
                        r'今天\s*\d{1,2}:\d{2}',  # 今天 12:30
                        r'\d{1,2}月\d{1,2}日',    # 3月28日
                        r'\d{1,2}天前',           # 2天前
                    ]

                    for pattern in time_patterns:
                        match = re.search(pattern, post_text)
                        if match:
                            post_time = match.group()
                            break

                    # 如果找到时间，尝试提取时间前的文本作为用户名
                    if post_time and ('昨天' in post_time or '小时前' in post_time or '分钟前' in post_time or '今天' in post_time):
                        # 查找时间前面的文本作为用户名
                        time_index = post_text.find(post_time)
                        if time_index > 0:
                            # 提取时间前的文本，可能是用户名
                            potential_username = post_text[:time_index].strip()
                            # 清理可能的特殊字符和emoji
                            if potential_username and len(potential_username) > 1:
                                user_id = potential_username
                except:
                    pass

            # 获取图片URL - 过滤掉头像图片
            image_urls = []
            try:
                img_elements = post_element.find_elements(By.CSS_SELECTOR, self._get_selector('post_image', 'img[src*="xhs"], img'))
                for img in img_elements:
                    src = img.get_attribute('src')
                    if src and ('http' in src or '//' in src):
                        # 过滤头像图片：排除包含avatar关键字的URL
                        if 'avatar' in src.lower():
                            print(f"    [过滤] 跳过头像图片: {src[:60]}...")
                            continue
                        # 过滤用户头像特有的尺寸模式
                        # 头像通常很小，如 40x40, 60x60, 100x100
                        import re
                        size_match = re.search(r'(\d+)x(\d+)', src)
                        if size_match:
                            width, height = int(size_match.group(1)), int(size_match.group(2))
                            # 如果图片小于120像素，可能是头像
                            if width < 120 and height < 120:
                                print(f"    [过滤] 跳过小尺寸图片({width}x{height}): {src[:60]}...")
                                continue
                        image_urls.append(src)
            except Exception as e:
                print(f"    提取图片URL时出错: {e}")

            # === 改进的帖子ID生成逻辑 ===
            post_id = None

            # 方法1: 优先使用帖子链接中的唯一标识符
            if link:
                import re
                # 尝试从链接中提取帖子ID
                # 小红书链接格式: https://www.xiaohongshu.com/explore/69c7c53a0000000023011901
                # 或: https://www.xiaohongshu.com/note/...
                explore_match = re.search(r'/explore/([a-f0-9]+)', link)
                note_match = re.search(r'/note/([a-f0-9]+)', link)

                if explore_match:
                    post_id = explore_match.group(1)
                    # 如果ID太长，取前12个字符（保持与现有格式相似）
                    if len(post_id) > 12:
                        post_id = post_id[:12]
                elif note_match:
                    post_id = note_match.group(1)
                    if len(post_id) > 12:
                        post_id = post_id[:12]

            # 方法2: 如果无法从链接提取，使用用户ID + 时间 + 文本前200字符的哈希
            if not post_id:
                import hashlib
                # 使用更稳定的特征组合
                stable_features = ""
                if user_id:
                    stable_features += user_id
                if post_time:
                    stable_features += post_time
                if post_text:
                    # 使用文本前200字符（比原来的100字符更稳定）
                    stable_features += post_text[:200]

                if stable_features:
                    post_id = hashlib.md5(stable_features.encode('utf-8')).hexdigest()[:12]
                else:
                    # 最后回退到原始方法
                    content_for_hash = f"{post_text[:100]}{link}"
                    if content_for_hash:
                        post_id = hashlib.md5(content_for_hash.encode('utf-8')).hexdigest()[:8]

            # 如果仍然没有ID，生成一个随机ID
            if not post_id:
                import random
                post_id = f"post_{random.randint(100000, 999999)}"

            # 清理用户ID，去除混杂的非用户ID内容
            if user_id:
                original_user_id = user_id
                cleaned = False

                # 规则0：专门处理时间后缀（最高优先级）
                # 移除"X小时前"、"X分钟前"、"昨天"等时间后缀
                import re
                time_patterns = [
                    r'\d{1,2}小时前$',  # 1小时前
                    r'\d{1,2}分钟前$',  # 5分钟前
                    r'昨天\s*\d{1,2}:\d{2}$',  # 昨天 18:31
                    r'今天\s*\d{1,2}:\d{2}$',  # 今天 12:30
                    r'\d{1,2}月\d{1,2}日$',    # 3月28日
                    r'\d{1,2}天前$',           # 2天前
                ]

                for pattern in time_patterns:
                    match = re.search(pattern, user_id)
                    if match:
                        # 移除匹配到的时间部分
                        time_part = match.group()
                        user_id = user_id.replace(time_part, '').strip()
                        cleaned = True
                        break

                # 如果清理后以标点结尾，去除标点
                if cleaned:
                    import string
                    punctuation = string.punctuation + '·！【】（）#@'
                    user_id = user_id.rstrip(punctuation).strip()

                # 规则1：如果包含中文分隔符，取分隔符之后的部分（优先级从高到低）
                # 常见模式：位置·标题！用户名 或 【标题】用户名
                if not cleaned:
                    separators = ['·', '！', '】', '）', '】', '】', '】', '【', '（', '(']
                    for sep in separators:
                        if sep in user_id:
                            parts = user_id.split(sep)
                            # 取最后一个非空部分
                            for part in reversed(parts):
                                if part.strip():
                                    user_id = part.strip()
                                    cleaned = True
                                    break
                            if cleaned:
                                break

                # 规则2：如果包含空格，尝试分割，取可能是用户名的部分
                if not cleaned and ' ' in user_id:
                    parts = user_id.split()
                    # 假设用户名是最后一部分或较短的部分
                    for part in reversed(parts):
                        if 2 <= len(part) <= 10:  # 用户名通常2-10字符
                            user_id = part
                            cleaned = True
                            break
                    if not cleaned:
                        # 取最后一部分
                        user_id = parts[-1]
                        cleaned = True

                # 规则3：如果仍然过长（>12字符），尝试提取最后的中文/英文单词
                if len(user_id) > 12:
                    import re
                    # 匹配连续的中文字符、字母、数字、emoji
                    matches = re.findall(r'[\u4e00-\u9fff\U0001F300-\U0001F9FF]+|[A-Za-z0-9_]+', user_id)
                    if matches:
                        # 取最后一个匹配项
                        user_id = matches[-1]
                        cleaned = True

                # 规则4：去除开头结尾的标点
                import string
                punctuation = string.punctuation + '·！【】（）#@'
                user_id = user_id.strip(punctuation)

                # 如果清理后为空，恢复原值
                if not user_id:
                    user_id = original_user_id
                # 可选：打印清理日志
                elif original_user_id != user_id and len(original_user_id) > len(user_id):
                    print(f"清理用户ID: '{original_user_id}' -> '{user_id}'")

            return {
                'post_id': post_id,
                'text': post_text[:500] if post_text else '',  # 限制文本长度
                'link': link,
                'time': post_time,
                'user_id': user_id,
                'image_urls': image_urls,
                'num_images': len(image_urls),
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
            }
        except Exception as e:
            print(f"提取帖子详情时出错: {e}")
            return None

    def download_image(self, url: str, save_path: str) -> bool:
        """
        下载图片到指定路径

        Args:
            url: 图片URL
            save_path: 保存路径

        Returns:
            是否下载成功
        """
        try:
            # 设置请求头，模拟浏览器
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Referer': 'https://www.xiaohongshu.com/'
            }

            # 创建请求
            req = urllib.request.Request(url, headers=headers)

            # 下载图片
            with urllib.request.urlopen(req, timeout=30) as response:
                if response.status == 200:
                    with open(save_path, 'wb') as f:
                        f.write(response.read())
                    return True
                else:
                    print(f"下载失败，状态码: {response.status}")
                    return False
        except Exception as e:
            print(f"下载图片时出错 ({url}): {e}")
            return False

    def create_gallery_directory(self, image_dir: str = None) -> str:
        """
        创建gallery目录并返回路径

        Args:
            image_dir: 指定的目录路径，如果为None则使用配置或默认值

        Returns:
            创建的目录路径
        """
        # 确定目录路径：优先使用传入参数，其次使用配置，最后使用默认值
        if image_dir is None:
            if config and hasattr(config, 'DATA_EXTRACT_CONFIG'):
                image_dir = config.DATA_EXTRACT_CONFIG.get('image_dir', 'gallery')
            else:
                image_dir = 'gallery'

        # 创建目录
        if not os.path.exists(image_dir):
            os.makedirs(image_dir)
            print(f"已创建目录: {image_dir}")

        return image_dir

    def extract_all_posts(self, max_posts: int = 0, download_images: bool = None, image_dir: str = None) -> List[Dict]:
        """
        提取当前页面所有帖子的详细信息

        Args:
            max_posts: 最大提取数量（0表示无限制）
            download_images: 是否下载图片（None表示使用配置）
            image_dir: 图片保存目录（None表示使用配置）

        Returns:
            帖子详情列表
        """
        print("\n=== 开始提取帖子详细信息 ===")

        # 处理是否下载图片的参数
        should_download_images = True  # 默认值
        if download_images is not None:
            should_download_images = download_images
        elif config and hasattr(config, 'DATA_EXTRACT_CONFIG'):
            should_download_images = config.DATA_EXTRACT_CONFIG.get('download_images', True)

        print(f"是否下载图片: {'是' if should_download_images else '否'}")

        # 获取帖子容器元素
        post_elements = []
        try:
            post_container_selectors = [
                '.note-item',
                '.card',
                '.post-item',
            ]

            post_elements = []
            for selector in post_container_selectors:
                post_elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if post_elements:
                    print(f"使用选择器 '{selector}' 找到 {len(post_elements)} 个帖子容器")
                    break

        except Exception as e:
            print(f"查找帖子容器时出错: {e}")
            return []

        # 限制提取数量
        if max_posts > 0 and len(post_elements) > max_posts:
            post_elements = post_elements[:max_posts]
            print(f"限制提取前 {max_posts} 个帖子")

        # 过滤非帖子元素（如"大家都在搜"）
        filtered_elements = []
        for element in post_elements:
            try:
                text = element.text.strip() if element.text else ''
                if text and ('大家都在搜' in text or '热门搜索' in text or '热门推荐' in text):
                    print(f"过滤非帖子元素: {text[:50]}")
                    continue
                # 检查是否包含帖子链接
                link_elements = element.find_elements(By.CSS_SELECTOR, self._get_selector('post_link', 'a[href*="/explore/"], a[href*="/note/"]'))
                if not link_elements:
                    # 如果没有链接，可能不是真正的帖子，但暂时保留
                    pass
                filtered_elements.append(element)
            except Exception as e:
                print(f"过滤元素时出错: {e}")
                filtered_elements.append(element)  # 出错时保留

        post_elements = filtered_elements
        print(f"过滤后剩余 {len(post_elements)} 个帖子元素")

        # 提取每个帖子的详细信息
        all_posts = []
        image_dir = self.create_gallery_directory(image_dir)

        # 从配置获取图片命名方式
        image_naming = 'sequential'
        if config and hasattr(config, 'DATA_EXTRACT_CONFIG'):
            image_naming = config.DATA_EXTRACT_CONFIG.get('image_naming', 'sequential')

        for i, post_element in enumerate(post_elements):
            print(f"\n处理帖子 {i+1}/{len(post_elements)}...")

            # 提取帖子详情
            post_details = self.extract_post_details(post_element)
            if not post_details:
                print(f"  帖子 {i+1} 详情提取失败，跳过")
                continue

            # 下载图片
            image_urls = post_details.get('image_urls', [])
            downloaded_images = []

            if image_urls:
                print(f"  发现 {len(image_urls)} 张图片")

                if should_download_images:
                    print(f"  开始下载图片...")

                    for j, img_url in enumerate(image_urls):
                        try:
                            # 生成文件名
                            if image_naming == 'post_id' and post_details['post_id']:
                                filename = f"{post_details['post_id']}_{j+1:02d}.jpg"
                            else:
                                filename = f"post_{i+1:03d}_img_{j+1:02d}.jpg"

                            save_path = os.path.join(image_dir, filename)

                            print(f"  下载图片 {j+1}/{len(image_urls)}: {filename}")
                            if self.download_image(img_url, save_path):
                                downloaded_images.append({
                                    'original_url': img_url,
                                    'filename': filename,
                                    'save_path': save_path
                                })
                                print(f"    ✓ 已下载: {filename}")
                            else:
                                print(f"    图片下载失败: {img_url}")
                        except Exception as e:
                            print(f"    处理图片时出错: {e}")
                else:
                    print(f"  跳过图片下载（配置为不下载图片）")

                    # 即使不下载，也记录图片URL信息
                    for j, img_url in enumerate(image_urls):
                        downloaded_images.append({
                            'original_url': img_url,
                            'filename': None,
                            'save_path': None
                        })
            else:
                print(f"  未发现图片")

            # 添加下载的图片信息
            post_details['downloaded_images'] = downloaded_images

            all_posts.append(post_details)

            # 短暂暂停，避免请求过快
            time.sleep(0.5)

        print(f"\n=== 提取完成 ===")
        print(f"成功提取 {len(all_posts)} 个帖子的详细信息")
        if all_posts:
            total_images = sum(len(post.get('downloaded_images', [])) for post in all_posts)
            print(f"成功下载 {total_images} 张图片到 {image_dir}/ 目录")

        return all_posts

    def extract_posts_metadata_only(self, max_posts: int = 0) -> List[Dict]:
        """
        只提取帖子元数据，不下载图片
        用于滚动过程中快速提取帖子信息

        Args:
            max_posts: 最大提取数量（0表示无限制）

        Returns:
            帖子详情列表（不包含downloaded_images）
        """
        print(f"\n=== 提取帖子元数据（不下载图片） ===")

        # 获取帖子容器元素
        post_elements = []
        try:
            post_container_selectors = [
                '.note-item',
                '.card',
                '.post-item',
            ]

            post_elements = []
            for selector in post_container_selectors:
                post_elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if post_elements:
                    print(f"使用选择器 '{selector}' 找到 {len(post_elements)} 个帖子容器")
                    break

        except Exception as e:
            print(f"查找帖子容器时出错: {e}")
            return []

        # 限制提取数量
        if max_posts > 0 and len(post_elements) > max_posts:
            post_elements = post_elements[:max_posts]
            print(f"限制提取前 {max_posts} 个帖子")

        # 过滤非帖子元素（如"大家都在搜"）
        filtered_elements = []
        for element in post_elements:
            try:
                text = element.text.strip() if element.text else ''
                if text and ('大家都在搜' in text or '热门搜索' in text or '热门推荐' in text):
                    print(f"过滤非帖子元素: {text[:50]}")
                    continue
                # 检查是否包含帖子链接
                link_elements = element.find_elements(By.CSS_SELECTOR, self._get_selector('post_link', 'a[href*="/explore/"], a[href*="/note/"]'))
                if not link_elements:
                    # 如果没有链接，可能不是真正的帖子，但暂时保留
                    pass
                filtered_elements.append(element)
            except Exception as e:
                print(f"过滤元素时出错: {e}")
                filtered_elements.append(element)  # 出错时保留

        post_elements = filtered_elements
        print(f"过滤后剩余 {len(post_elements)} 个帖子元素")

        # 提取每个帖子的详细信息
        all_posts = []

        for post_element in post_elements:
            # 提取帖子详情
            post_details = self.extract_post_details(post_element)
            if not post_details:
                continue

            # 设置空下载列表，表示未下载图片
            post_details['downloaded_images'] = []

            all_posts.append(post_details)

            # 短暂暂停，避免请求过快
            time.sleep(0.2)

        print(f"成功提取 {len(all_posts)} 个帖子的元数据")
        return all_posts

    def save_metadata(self, posts: List[Dict], filename: str = None):
        """
        保存帖子元数据到JSON文件，支持追加数据而不是覆盖

        Args:
            posts: 帖子详情列表
            filename: 保存文件名（可选）
        """
        if not posts:
            print("没有帖子数据需要保存")
            return

        # 确定文件名
        if not filename:
            if config and hasattr(config, 'DATA_EXTRACT_CONFIG'):
                filename = config.DATA_EXTRACT_CONFIG.get('metadata_file', 'posts_metadata.json')
            else:
                filename = 'posts_metadata.json'

        # 尝试读取现有数据
        existing_data = None
        if os.path.exists(filename):
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
                print(f"读取到现有元数据文件: {filename}")
            except (json.JSONDecodeError, IOError) as e:
                print(f"读取现有元数据文件失败，将创建新文件: {e}")
                existing_data = None
        else:
            print(f"元数据文件不存在，将创建新文件: {filename}")

        # 准备新的帖子数据
        new_posts = []
        existing_post_ids = set()

        # 如果存在现有数据，获取已有的post_id集合
        if existing_data and 'posts' in existing_data:
            if existing_data['posts']:
                for post in existing_data['posts']:
                    post_id = post.get('post_id')
                    if post_id:
                        existing_post_ids.add(post_id)
                print(f"现有数据包含 {len(existing_post_ids)} 个唯一帖子")
            else:
                print("现有数据posts字段为空列表")
        elif existing_data:
            print("现有数据格式不正确，缺少posts字段")
            existing_data = None  # 当作新文件处理

        # 去重：只添加新帖子（基于post_id）
        added_count = 0
        duplicate_count = 0
        for post in posts:
            post_id = post.get('post_id')
            if not post_id:
                # 如果没有post_id，总是添加（但这种情况应该很少见）
                new_posts.append(post)
                added_count += 1
                continue

            if post_id in existing_post_ids:
                # 帖子已存在，跳过
                duplicate_count += 1
                if duplicate_count <= 5:  # 只显示前5个重复帖子
                    print(f"  跳过重复帖子: post_id={post_id}, user={post.get('user_id', '未知用户')[:20]}")
                elif duplicate_count == 6:
                    print(f"  还有更多重复帖子...")
            else:
                # 新帖子，添加到列表
                new_posts.append(post)
                existing_post_ids.add(post_id)  # 添加到集合避免同一批内的重复
                added_count += 1

        if duplicate_count > 0:
            print(f"跳过 {duplicate_count} 个重复帖子")

        if added_count == 0:
            print("没有新帖子需要保存")
            return

        # 合并数据
        if existing_data:
            # 合并现有帖子和新帖子
            all_posts = existing_data['posts'] + new_posts
            total_posts = len(all_posts)
            total_images = sum(len(post.get('downloaded_images', [])) for post in all_posts)

            # 更新元数据
            save_data = {
                'extraction_time': time.strftime('%Y-%m-%d %H:%M:%S'),
                'last_update_time': existing_data.get('extraction_time', '未知时间'),
                'total_posts': total_posts,
                'total_images': total_images,
                'posts': all_posts
            }
            print(f"追加 {added_count} 个新帖子到现有数据")
            print(f"合并后: 总计 {total_posts} 个帖子, {total_images} 张图片")
        else:
            # 创建新数据
            save_data = {
                'extraction_time': time.strftime('%Y-%m-%d %H:%M:%S'),
                'total_posts': len(new_posts),
                'total_images': sum(len(post.get('downloaded_images', [])) for post in new_posts),
                'posts': new_posts
            }
            print(f"保存 {added_count} 个新帖子")

        # 保存到JSON文件（使用临时文件+重命名，防止写入中断导致空文件）
        try:
            # 如果原文件存在且非空，先备份
            if os.path.exists(filename) and os.path.getsize(filename) > 0:
                backup_filename = filename + '.bak'
                try:
                    import shutil
                    shutil.copy2(filename, backup_filename)
                except Exception as e:
                    print(f"备份元数据文件失败: {e}")

            # 先写入临时文件
            temp_filename = filename + '.tmp'
            with open(temp_filename, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, ensure_ascii=False, indent=2)

            # 再原子重命名到目标文件
            os.replace(temp_filename, filename)
            print(f"元数据已保存到: {filename}")
        except Exception as e:
            print(f"保存元数据时出错: {e}")

    def run(self, keyword: str, cookie_file: str = 'cookies.json', **kwargs):
        """
        执行完整流程

        Args:
            keyword: 搜索关键词
            cookie_file: Cookie文件路径
            **kwargs: 额外参数，包括：
                scroll_times: 滚动次数（覆盖配置）
                max_posts: 最大提取帖子数量（覆盖配置）
                download_images: 是否下载图片（覆盖配置）
                image_dir: 图片保存目录（覆盖配置）
        """
        print("=" * 50)
        print(f"小红书自动化脚本启动")
        print(f"关键词: {keyword}")
        print(f"浏览器: {self.browser_type}")
        print("=" * 50)

        # 处理覆盖参数
        override_params = {}
        if kwargs:
            print("命令行覆盖参数:")
            if 'scroll_times' in kwargs and kwargs['scroll_times'] is not None:
                override_params['scroll_times'] = kwargs['scroll_times']
                print(f"  scroll_times: {kwargs['scroll_times']}")
            if 'max_posts' in kwargs and kwargs['max_posts'] is not None:
                override_params['max_posts'] = kwargs['max_posts']
                print(f"  max_posts: {kwargs['max_posts']}")
            if 'download_images' in kwargs and kwargs['download_images'] is not None:
                override_params['download_images'] = kwargs['download_images']
                print(f"  download_images: {kwargs['download_images']}")
            if 'image_dir' in kwargs and kwargs['image_dir'] is not None:
                override_params['image_dir'] = kwargs['image_dir']
                print(f"  image_dir: {kwargs['image_dir']}")

        try:
            print("\n[调试] 步骤1: 启动浏览器...")
            # 1. 启动浏览器
            self.start_browser()
            print("[调试] 步骤1完成: 浏览器已启动")

            print("\n[调试] 步骤2: 加载Cookie...")
            # 2. 加载Cookie并打开小红书
            self.load_cookies(cookie_file)
            print("[调试] 步骤2完成: Cookie已加载")

            print("\n[调试] 步骤3: 检查登录状态...")
            # 3. 检查登录状态
            login_status = self.is_logged_in()
            if login_status:
                print("✓ 登录状态：已登录")
            else:
                print("✗ 登录状态：未登录或Cookie可能已过期")
                print("警告：可能未成功登录，请检查Cookie是否有效")
                # 继续执行，因为有些操作可能不需要登录
            print("[调试] 步骤3完成")

            print("\n[调试] 步骤4: 搜索关键词...")
            # 4. 搜索关键词
            self.search_keyword(keyword)
            print("[调试] 步骤4完成: 搜索完成")

            print("\n[调试] 步骤5: 准备调用 apply_filters...")
            # 5. 应用筛选条件
            self.apply_filters(keyword=keyword)

            # 5.5 验证筛选是否生效
            self.verify_filters_applied()

            # 6. 提取帖子详细信息
            # 从配置获取参数，优先使用命令行参数
            max_posts = 0  # 0表示无限制
            if config and hasattr(config, 'DATA_EXTRACT_CONFIG'):
                max_posts = config.DATA_EXTRACT_CONFIG.get('max_posts', 0)

            # 使用命令行参数覆盖
            if 'max_posts' in override_params:
                max_posts = override_params['max_posts']

            print(f"目标提取帖子数量: {max_posts if max_posts > 0 else '无限制'}")

            # 处理是否下载图片的参数
            download_images_param = True  # 默认值
            if 'download_images' in override_params:
                download_images_param = override_params['download_images']
            elif config and hasattr(config, 'DATA_EXTRACT_CONFIG'):
                # 从配置获取默认值
                download_images_param = config.DATA_EXTRACT_CONFIG.get('download_images', True)

            # 处理图片目录参数
            image_dir_param = None
            if 'image_dir' in override_params:
                image_dir_param = override_params['image_dir']

            # 获取滚动参数
            scroll_times = 10  # 默认值
            scroll_pause = 2.0
            if config and hasattr(config, 'SCROLL_CONFIG'):
                scroll_times = config.SCROLL_CONFIG.get('scroll_times', 10)
                scroll_pause = config.SCROLL_CONFIG.get('scroll_pause', 2.0)

            # 使用命令行参数覆盖
            if 'scroll_times' in override_params:
                scroll_times = override_params['scroll_times']
                print(f"  使用命令行指定的滚动次数: {scroll_times}")
            else:
                print(f"  未指定滚动次数，使用配置或默认值: {scroll_times}")

            # 自动计算滚动次数（基于目标帖子数量）
            if max_posts > 0 and 'scroll_times' not in override_params:
                # 获取滚动配置参数
                initial_load = 18
                increment_per_scroll = 9
                if config and hasattr(config, 'SCROLL_CONFIG'):
                    initial_load = config.SCROLL_CONFIG.get('initial_load_count', 18)
                    increment_per_scroll = config.SCROLL_CONFIG.get('increment_per_scroll', 9)

                # 计算所需滚动次数
                if max_posts <= initial_load:
                    calculated_scroll = 0
                else:
                    # 向上取整计算滚动次数
                    calculated_scroll = math.ceil((max_posts - initial_load) / increment_per_scroll)

                # 更新滚动次数
                if scroll_times != calculated_scroll:
                    print(f"  根据目标数量 {max_posts} 自动计算滚动次数:")
                    print(f"    初始加载: {initial_load} 篇")
                    print(f"    每次滚动新增: {increment_per_scroll} 篇")
                    print(f"    需要滚动次数: {calculated_scroll} (原: {scroll_times})")
                    scroll_times = calculated_scroll
                else:
                    print(f"  滚动次数 {scroll_times} 已满足目标 {max_posts} 篇的需求")
            elif 'scroll_times' in override_params and max_posts > 0:
                print(f"  使用命令行指定的滚动次数 {scroll_times}，目标 {max_posts} 篇")
            elif max_posts == 0:
                print(f"  目标数量无限制，使用滚动次数: {scroll_times}")

            # 7. 执行帖子提取（根据是否需要滚动）
            if scroll_times > 0:
                print(f"\n开始滚动提取，最大滚动次数: {scroll_times}")
                print("注意：滚动可能会影响筛选状态，滚动前后将验证筛选条件")

                # 滚动前验证筛选状态
                print("滚动提取前验证筛选状态...")
                self.verify_filters_applied()

                # 使用新的滚动提取方法（方案一）
                posts = self.scroll_to_extract_posts(
                    target_count=max_posts,
                    max_scroll=scroll_times,
                    scroll_pause=scroll_pause,
                    download_images=download_images_param,
                    image_dir=image_dir_param
                )

                # 滚动后再次验证筛选状态
                print("滚动提取后验证筛选状态...")
                self.verify_filters_applied()
            else:
                print(f"\n跳过滚动，提取当前可见帖子")
                # 只提取当前可见的帖子
                posts = self.extract_all_posts(
                    max_posts=max_posts,
                    download_images=download_images_param,
                    image_dir=image_dir_param
                )

            # 验证提取的帖子时间是否符合筛选条件
            if posts:
                print(f"成功提取 {len(posts)} 个帖子")
                print("验证帖子时间是否符合'一天内'筛选:")

                valid_count = 0
                for i, post in enumerate(posts[:min(5, len(posts))]):  # 最多检查5个
                    post_time = post.get('time', '')
                    user_id = post.get('user_id', '')
                    if post_time:
                        print(f"  帖子{i+1}: 用户='{user_id[:20]}' 时间='{post_time}'")
                        # 检查是否包含"昨天"、"小时前"、"分钟前"等一天内标识
                        if ('昨天' in post_time or '小时前' in post_time or
                            '分钟前' in post_time or '今天' in post_time):
                            print(f"    ✓ 符合'一天内'筛选")
                            valid_count += 1
                        else:
                            print(f"    ⚠️ 可能不符合'一天内'筛选")

                if valid_count == 0 and len(posts) > 0:
                    print(f"警告: 提取的 {len(posts)} 个帖子中，没有符合'一天内'筛选的帖子")
                    print("可能原因: 1) 筛选未生效 2) 页面已刷新 3) 小红书时间显示格式变化")
            else:
                print("未提取到任何帖子")

            # 8. 保存元数据
            if posts:
                self.save_metadata(posts)

            # 8. 短暂保持浏览器打开，供用户查看
            print("\n自动化流程完成！")
            print("浏览器窗口保持打开，您可以在30秒内查看页面内容。")
            print("浏览器将在30秒后自动关闭，或按 Ctrl+C 提前关闭。")

            # 等待30秒后自动关闭
            try:
                time.sleep(30)
            except KeyboardInterrupt:
                print("\n用户提前中断，关闭浏览器...")
                raise

        except KeyboardInterrupt:
            print("\n用户中断，退出程序...")
        except Exception as e:
            print(f"程序执行出错: {e}")
            import traceback
            traceback.print_exc()
        finally:
            if self.driver:
                self.driver.quit()
                print("浏览器已关闭")


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='小红书自动化脚本')
    parser.add_argument('--keyword', type=str, required=True, help='搜索关键词，如"深圳 走丢 小狗"')
    parser.add_argument('--cookies', type=str, default='cookies.json', help='Cookie文件路径，默认为cookies.json')
    parser.add_argument('--browser', type=str, default='chrome', choices=['safari', 'chrome'], help='浏览器类型，默认为chrome')
    parser.add_argument('--headless', action='store_true', help='无头模式（仅Chrome支持）')
    parser.add_argument('--scroll-times', type=int, default=None, help='滚动加载次数（覆盖配置）')
    parser.add_argument('--max-posts', type=int, default=None, help='最大提取帖子数量（0表示无限制，覆盖配置）')
    parser.add_argument('--no-images', action='store_true', help='不下载图片')
    parser.add_argument('--output-dir', type=str, default=None, help='图片保存目录（覆盖配置）')

    args = parser.parse_args()

    # 创建自动化实例并运行
    automation = XHSAutomation(browser_type=args.browser, headless=args.headless)

    # 准备运行参数
    run_kwargs = {}
    if args.scroll_times is not None:
        run_kwargs['scroll_times'] = args.scroll_times
    if args.max_posts is not None:
        run_kwargs['max_posts'] = args.max_posts
    if args.no_images:
        run_kwargs['download_images'] = False
    if args.output_dir is not None:
        run_kwargs['image_dir'] = args.output_dir

    automation.run(keyword=args.keyword, cookie_file=args.cookies, **run_kwargs)


if __name__ == '__main__':
    main()