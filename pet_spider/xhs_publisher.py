"""
小红书一键发布模块
独立浏览器实例，与爬虫模块完全隔离

功能：基于Selenium实现小红书图文自动发布，含浏览器复用、Cookie登录检测、JS点击上传与发布
"""

import os
import json
import time
import logging
from pathlib import Path
from typing import Optional, Dict, Any

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class XHSPublisher:
    """小红书发布器 - 独立浏览器实例"""

    # 独立存储路径，与爬虫完全隔离
    BASE_DIR = Path("./chrome_data/publish")
    COOKIE_PATH = BASE_DIR / "cookies.json"
    USER_DATA_DIR = BASE_DIR / "user_data"

    # 小红书创作平台URL
    CREATOR_URL = "https://creator.xiaohongshu.com/"
    LOGIN_URL_KEYWORD = "login"

    # 类级别变量，用于保持浏览器实例
    _shared_driver: Optional[webdriver.Chrome] = None
    _last_activity_time: float = 0
    _browser_timeout: int = 300  # 浏览器保持打开的时间（秒）

    def __init__(self):
        self.driver: Optional[webdriver.Chrome] = None
        self._ensure_dirs()

    def _is_browser_alive(self) -> bool:
        """检查浏览器是否还活着"""
        if XHSPublisher._shared_driver is None:
            return False
        try:
            # 尝试获取当前URL来检查浏览器是否响应
            XHSPublisher._shared_driver.current_url
            return True
        except Exception:
            return False

    def _get_or_create_browser(self) -> webdriver.Chrome:
        """获取现有浏览器或创建新浏览器"""
        current_time = time.time()

        # 检查是否有可用的共享浏览器
        if self._is_browser_alive():
            # 检查是否超时
            if current_time - XHSPublisher._last_activity_time < self._browser_timeout:
                logger.info("复用现有浏览器实例")
                self.driver = XHSPublisher._shared_driver
                return self.driver
            else:
                # 超时了，关闭旧浏览器
                logger.info("浏览器超时，关闭旧实例")
                try:
                    XHSPublisher._shared_driver.quit()
                except:
                    pass
                XHSPublisher._shared_driver = None

        # 创建新浏览器
        logger.info("创建新浏览器实例")
        self.driver = self._create_new_browser()
        XHSPublisher._shared_driver = self.driver
        XHSPublisher._last_activity_time = current_time
        return self.driver

    def _create_new_browser(self) -> webdriver.Chrome:
        """创建新的浏览器实例"""
        logger.info("正在启动 Chrome 浏览器...")

        chrome_options = Options()

        # 使用独立的用户数据目录
        chrome_options.add_argument(f"--user-data-dir={self.USER_DATA_DIR.absolute()}")

        # 其他必要配置
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)

        # 窗口大小
        chrome_options.add_argument("--window-size=1400,900")

        try:
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            logger.info("浏览器启动成功")
            return driver
        except Exception as e:
            logger.warning(f"webdriver_manager 下载失败: {e}，尝试使用系统 PATH 中的 chromedriver")
            try:
                driver = webdriver.Chrome(options=chrome_options)
                driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                logger.info("浏览器启动成功（使用系统 chromedriver）")
                return driver
            except Exception as e2:
                logger.error(f"浏览器启动失败: {e2}")
                raise

    def _ensure_dirs(self):
        """确保目录存在"""
        self.BASE_DIR.mkdir(parents=True, exist_ok=True)
        self.USER_DATA_DIR.mkdir(parents=True, exist_ok=True)

    def start_browser(self) -> webdriver.Chrome:
        """启动或复用 Chrome 浏览器"""
        self.driver = self._get_or_create_browser()
        return self.driver

    def close_browser(self, force: bool = False):
        """
        关闭浏览器

        Args:
            force: 是否强制关闭（True 时关闭共享实例）
        """
        if force and XHSPublisher._shared_driver:
            logger.info("强制关闭浏览器...")
            try:
                XHSPublisher._shared_driver.quit()
            except Exception as e:
                logger.warning(f"关闭浏览器时出错: {e}")
            finally:
                XHSPublisher._shared_driver = None
                self.driver = None
        elif self.driver and self.driver != XHSPublisher._shared_driver:
            # 只关闭非共享的浏览器实例
            try:
                self.driver.quit()
            except:
                pass
            finally:
                self.driver = None

    def check_login_status(self) -> bool:
        """检查登录状态"""
        if not self.driver:
            raise RuntimeError("浏览器未启动")

        logger.info("检查登录状态...")
        self.driver.get(self.CREATOR_URL)
        time.sleep(3)

        current_url = self.driver.current_url
        logger.info(f"当前URL: {current_url}")

        # 如果URL包含login，说明未登录
        if self.LOGIN_URL_KEYWORD in current_url.lower():
            logger.info("未登录，需要登录")
            return False

        # 检查是否存在登录后的元素（比如用户头像或创作者中心标识）
        try:
            # 等待页面加载，检查是否有发布笔记按钮
            WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.XPATH, "//span[contains(text(), '发布笔记')]"))
            )
            logger.info("已登录")
            return True
        except Exception:
            # 再尝试其他可能的登录标识
            try:
                self.driver.find_element(By.CSS_SELECTOR, ".user-info, .avatar, .creator-center")
                logger.info("已登录")
                return True
            except Exception:
                logger.info("未检测到登录标识，视为未登录")
                return False

    def save_cookies(self):
        """保存 cookies 到文件"""
        if not self.driver:
            return

        try:
            cookies = self.driver.get_cookies()
            with open(self.COOKIE_PATH, 'w', encoding='utf-8') as f:
                json.dump(cookies, f, ensure_ascii=False, indent=2)
            logger.info(f"Cookies 已保存到 {self.COOKIE_PATH}")
        except Exception as e:
            logger.error(f"保存 cookies 失败: {e}")

    def load_cookies(self) -> bool:
        """从文件加载 cookies"""
        if not self.COOKIE_PATH.exists():
            logger.info("Cookie 文件不存在")
            return False

        try:
            with open(self.COOKIE_PATH, 'r', encoding='utf-8') as f:
                cookies = json.load(f)

            for cookie in cookies:
                # 移除可能导致问题的字段
                cookie.pop('sameSite', None)
                try:
                    self.driver.add_cookie(cookie)
                except Exception as e:
                    logger.warning(f"添加 cookie 失败: {e}")

            logger.info("Cookies 已加载")
            return True
        except Exception as e:
            logger.error(f"加载 cookies 失败: {e}")
            return False

    def _click_publish_note_button(self) -> bool:
        """点击发布笔记按钮"""
        try:
            logger.info("点击发布笔记按钮...")

            # 尝试多种定位方式
            selectors = [
                "//span[contains(text(), '发布笔记')]/ancestor::button",
                "//span[contains(text(), '发布笔记')]/parent::*",
                "button:has(span:contains('发布笔记'))",
                "[data-v-7d2ed9a2]",  # 从截图看到的属性
            ]

            for selector in selectors:
                try:
                    if selector.startswith("//"):
                        element = WebDriverWait(self.driver, 3).until(
                            EC.element_to_be_clickable((By.XPATH, selector))
                        )
                    elif selector.startswith("["):
                        element = WebDriverWait(self.driver, 3).until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                        )
                    else:
                        continue

                    element.click()
                    logger.info("发布笔记按钮已点击")
                    time.sleep(2)
                    return True
                except Exception:
                    continue

            logger.error("无法点击发布笔记按钮")
            return False

        except Exception as e:
            logger.error(f"点击发布笔记按钮失败: {e}")
            return False

    def _upload_image(self, image_path: str) -> bool:
        """上传图片"""
        try:
            logger.info(f"上传图片: {image_path}")

            # 检查文件是否存在
            if not os.path.exists(image_path):
                logger.error(f"图片文件不存在: {image_path}")
                return False

            # 转换为绝对路径
            abs_path = os.path.abspath(image_path)

            # 1. 先点击"上传图文"选项卡
            logger.info("点击上传图文选项卡...")
            tab_clicked = False

            # 方法1: 使用 JavaScript 点击（最可靠）
            try:
                # 等待页面加载完成
                time.sleep(2)
                # 使用 JS 找到包含"上传图文"的元素并点击其父级
                js_result = self.driver.execute_script("""
                    var spans = document.querySelectorAll('span.title');
                    for (var i = 0; i < spans.length; i++) {
                        if (spans[i].textContent.includes('上传图文')) {
                            var parent = spans[i].closest('div.creator-tab') || spans[i].parentElement;
                            if (parent) {
                                parent.click();
                                return 'clicked: ' + parent.className;
                            }
                        }
                    }
                    // 如果没找到，尝试直接点击 span
                    for (var i = 0; i < spans.length; i++) {
                        if (spans[i].textContent.includes('上传图文')) {
                            spans[i].click();
                            return 'clicked span directly';
                        }
                    }
                    return 'not found';
                """)
                logger.info(f"JS 点击结果: {js_result}")
                if js_result != 'not found':
                    tab_clicked = True
                    time.sleep(3)
            except Exception as e:
                logger.warning(f"JS 点击失败: {e}")

            # 方法2: 使用 XPath 作为备用
            if not tab_clicked:
                image_text_selectors = [
                    "//span[contains(@class, 'title') and contains(text(), '上传图文')]/parent::div[contains(@class, 'creator-tab')]",
                    "//span[contains(text(), '上传图文')]/ancestor::div[contains(@class, 'creator-tab')]",
                    "//div[contains(@class, 'creator-tab')]//span[contains(text(), '上传图文')]/..",
                    "//span[contains(text(), '上传图文')]/..",
                ]

                for selector in image_text_selectors:
                    try:
                        tab = WebDriverWait(self.driver, 3).until(
                            EC.presence_of_element_located((By.XPATH, selector))
                        )
                        self.driver.execute_script("arguments[0].click();", tab)
                        logger.info(f"已点击上传图文选项卡: {selector}")
                        tab_clicked = True
                        time.sleep(3)
                        break
                    except Exception as e:
                        logger.warning(f"选择器 {selector} 失败: {e}")
                        continue

            if tab_clicked:
                logger.info("上传图文选项卡点击成功")
            else:
                logger.warning("未能点击上传图文选项卡，尝试继续...")

            # 等待一下确保页面切换完成
            time.sleep(3)

            # 2. 等待文件输入框出现
            file_input = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='file'].upload-input"))
            )

            # 发送文件路径
            file_input.send_keys(abs_path)
            logger.info("图片已选择，等待上传...")

            # 等待图片上传完成（等待预览出现或URL变化）
            time.sleep(5)  # 增加等待时间

            # 检查是否有图片预览出现
            try:
                # 等待编辑界面元素出现
                WebDriverWait(self.driver, 15).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".image-preview, .uploaded-image, [contenteditable='true'], .editor-content"))
                )
                logger.info("图片上传成功，编辑界面已加载")

                # 额外等待确保页面稳定
                time.sleep(3)
                return True
            except Exception as e:
                logger.warning(f"未检测到图片预览，但可能已上传: {e}")
                # 再等待一下
                time.sleep(5)
                return True

        except Exception as e:
            logger.error(f"上传图片失败: {e}")
            return False

    def _check_and_fill_title(self) -> bool:
        """检查并填写标题（从正文提取前20字作为标题）"""
        try:
            logger.info("检查标题...")
            # 尝试找到标题输入框
            title_selectors = [
                "input[placeholder*='标题']",
                "input[placeholder*='topic']",
                ".title-input input",
                "[data-field='title'] input",
            ]

            for selector in title_selectors:
                try:
                    title_input = WebDriverWait(self.driver, 3).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    # 检查是否已填写
                    current_value = title_input.get_attribute('value') or ''
                    if not current_value.strip():
                        # 标题为空，从正文提取前20字
                        # 先获取正文内容
                        content_elem = self.driver.execute_script("""
                            var editors = document.querySelectorAll('[contenteditable="true"]');
                            if (editors.length > 0) {
                                return editors[0].innerText || editors[0].textContent;
                            }
                            return '';
                        """)
                        if content_elem:
                            title = content_elem[:20] + ('...' if len(content_elem) > 20 else '')
                            title_input.clear()
                            title_input.send_keys(title)
                            logger.info(f"已自动填写标题: {title}")
                            time.sleep(1)
                    else:
                        logger.info("标题已填写")
                    return True
                except Exception:
                    continue

            logger.info("未找到标题输入框或无需填写")
            return True
        except Exception as e:
            logger.warning(f"检查标题时出错: {e}")
            return True  # 标题不是必须的，出错也继续

    def _input_content(self, content: str) -> bool:
        """输入正文内容"""
        try:
            logger.info("输入正文内容...")

            # 等待更长时间，确保编辑页面完全加载
            time.sleep(5)

            # 尝试多种方式定位正文编辑框
            selectors = [
                "div[contenteditable='true']",
                "[data-placeholder*='正文']",
                "[data-placeholder*='内容']",
                ".editor-content",
                "#content",
                "textarea",
            ]

            editor = None
            for selector in selectors:
                try:
                    editor = WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    logger.info(f"找到编辑框: {selector}")
                    break
                except Exception:
                    continue

            if not editor:
                logger.error("无法找到正文编辑框")
                return False

            # 滚动到元素可见
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", editor)
            time.sleep(1)

            # 点击编辑框激活
            editor.click()
            time.sleep(0.5)

            # 使用 JavaScript 设置内容（更可靠）
            self.driver.execute_script("""
                arguments[0].innerHTML = arguments[1];
                arguments[0].dispatchEvent(new Event('input', { bubbles: true }));
                arguments[0].dispatchEvent(new Event('change', { bubbles: true }));
            """, editor, content.replace('\n', '<br>'))

            logger.info("正文内容已输入")
            time.sleep(1)
            return True

        except Exception as e:
            logger.error(f"输入正文失败: {e}")
            return False

    def _click_publish_button(self) -> bool:
        """点击底部的发布按钮"""
        try:
            logger.info("=== 新版代码：点击底部的发布按钮 ===")

            # 等待确保编辑页面完全加载
            time.sleep(3)

            # 滚动到底部让发布按钮可见
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)

            # 先调试：列出所有包含"发布"的按钮及其位置
            debug_btns = self.driver.execute_script("""
                var buttons = document.querySelectorAll('button, .d-button');
                var results = [];
                buttons.forEach(function(btn) {
                    var text = btn.textContent.trim();
                    if (text.includes('发布')) {
                        var rect = btn.getBoundingClientRect();
                        results.push({
                            text: text,
                            top: rect.top,
                            left: rect.left,
                            className: btn.className,
                            isVisible: rect.height > 0 && rect.width > 0
                        });
                    }
                });
                return results;
            """)
            logger.info(f"所有包含'发布'的按钮: {debug_btns}")

            # 方法：找页面最底部的红色"发布"按钮
            # 策略：找所有包含"发布"文字的按钮，选择在页面最下方的那个
            try:
                result = self.driver.execute_script("""
                    var buttons = document.querySelectorAll('button, .d-button');
                    var publishButtons = [];

                    buttons.forEach(function(btn) {
                        var text = btn.textContent.trim();
                        // 只要文字是"发布"（不是"发布笔记"）
                        if (text === '发布' || (text.includes('发布') && !text.includes('笔记'))) {
                            var rect = btn.getBoundingClientRect();
                            if (rect.height > 0 && rect.width > 0) {
                                publishButtons.push({
                                    element: btn,
                                    top: rect.top,
                                    text: text
                                });
                            }
                        }
                    });

                    if (publishButtons.length === 0) {
                        return 'no publish buttons found';
                    }

                    // 按位置排序，取最下面的（top值最大的）
                    publishButtons.sort(function(a, b) {
                        return b.top - a.top;
                    });

                    // 点击最底部的按钮
                    var targetBtn = publishButtons[0];
                    targetBtn.element.scrollIntoView({block: 'center', behavior: 'smooth'});
                    setTimeout(function() {
                        targetBtn.element.click();
                    }, 200);

                    return 'clicked button at top=' + targetBtn.top + ', text="' + targetBtn.text + '"';
                """)
                logger.info(f"点击结果: {result}")
                if result and 'no publish' not in result:
                    time.sleep(8)
                    return True

            except Exception as e:
                logger.warning(f"找最底部发布按钮失败: {e}")

            logger.error("所有方法都无法点击发布按钮")
            return False

        except Exception as e:
            logger.error(f"点击发布按钮失败: {e}")
            return False

    def _wait_for_publish_result(self, timeout: int = 60) -> Dict[str, Any]:
        """等待发布结果"""
        logger.info(f"开始等待发布结果，超时时间: {timeout}秒")
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                current_url = self.driver.current_url
                elapsed = int(time.time() - start_time)

                # 每10秒记录一次当前状态
                if elapsed % 10 == 0 and elapsed > 0:
                    logger.info(f"等待发布中... {elapsed}秒")

                # 检查是否跳转到笔记详情页（发布成功的最可靠标志）
                if "/note/" in current_url:
                    logger.info(f"发布成功，跳转至笔记详情页: {current_url}")
                    return {"success": True, "url": current_url}

                # 检查是否跳转回创作者主页（发布成功后可能刷新回主页）
                if "/creator" in current_url and "/note/" not in current_url:
                    # 检查是否不在编辑页（没有发布按钮和编辑框）
                    try:
                        is_editor_page = self.driver.execute_script("""
                            var publishBtn = document.querySelector('button.d-button');
                            var editor = document.querySelector('div[contenteditable="true"]');
                            return publishBtn && publishBtn.textContent.includes('发布') && editor;
                        """)
                        if not is_editor_page:
                            logger.info(f"发布成功，页面已跳转回创作者主页: {current_url}")
                            return {"success": True, "url": current_url}
                    except:
                        pass

                # 检查是否有发布成功的弹窗或提示（使用更精确的检测）
                # 尝试查找常见的成功提示元素
                try:
                    # 查找可能的成功提示元素 - 扩展检测关键词
                    success_indicators = self.driver.execute_script("""
                        // 查找包含成功关键词的元素，且不是按钮
                        var successKeywords = ['发布成功', '已发布成功', '发布成功啦', '已发布', '发布完成', '发送成功'];
                        var elements = document.querySelectorAll('div, span, p, .toast, .message, .success, .d-toast');
                        for (var i = 0; i < elements.length; i++) {
                            var text = elements[i].textContent || '';
                            var tagName = elements[i].tagName.toLowerCase();
                            // 排除按钮和输入框
                            if (tagName !== 'button' && tagName !== 'input' && tagName !== 'textarea') {
                                for (var j = 0; j < successKeywords.length; j++) {
                                    if (text.includes(successKeywords[j])) {
                                        return {found: true, text: text, tag: tagName};
                                    }
                                }
                            }
                        }
                        // 额外检查：页面是否出现成功图标（绿勾等）
                        var successIcons = document.querySelectorAll('.d-icon-check, .icon-success, [class*="success"], [class*="Success"]');
                        if (successIcons.length > 0) {
                            return {found: true, text: '检测到成功图标', tag: 'icon'};
                        }
                        return {found: false};
                    """)

                    if success_indicators.get('found'):
                        logger.info(f"检测到发布成功提示: {success_indicators.get('text')}")
                        return {"success": True, "url": current_url}
                except Exception as e:
                    logger.debug(f"检测成功提示时出错: {e}")

                # 检查是否出现发布成功后的按钮（如"重新编辑"、"查看笔记"）
                try:
                    post_success_buttons = self.driver.execute_script("""
                        var buttons = document.querySelectorAll('button, .d-button, a');
                        var successTexts = ['重新编辑', '查看笔记', '查看详情', '再写一篇'];
                        for (var i = 0; i < buttons.length; i++) {
                            var text = buttons[i].textContent || '';
                            for (var j = 0; j < successTexts.length; j++) {
                                if (text.includes(successTexts[j])) {
                                    return {found: true, text: text};
                                }
                            }
                        }
                        return {found: false};
                    """)
                    if post_success_buttons.get('found'):
                        logger.info(f"检测到发布成功后的按钮: {post_success_buttons.get('text')}")
                        return {"success": True, "url": current_url}
                except Exception as e:
                    logger.debug(f"检测成功按钮时出错: {e}")

                # 检查是否有错误提示
                error_keywords = ["发布失败", "上传失败", "网络错误", "请重试", "无法发布"]
                page_text = self.driver.page_source.lower()
                for keyword in error_keywords:
                    if keyword in page_text:
                        logger.error(f"检测到错误提示: {keyword}")
                        return {"success": False, "error": f"发布失败: {keyword}"}

                time.sleep(2)

            except Exception as e:
                logger.warning(f"等待发布结果时出错: {e}")
                time.sleep(1)

        logger.error("等待发布结果超时")
        # 超时前截图保存以便调试
        try:
            screenshot_path = "./chrome_data/publish/timeout_screenshot.png"
            self.driver.save_screenshot(screenshot_path)
            logger.info(f"超时截图已保存: {screenshot_path}")
        except:
            pass
        return {"success": False, "error": "发布超时，请手动检查"}

    def publish_note(self, image_path: str, content: str, wait_for_login: bool = False) -> Dict[str, Any]:
        """
        发布笔记的主流程

        Args:
            image_path: 图片文件路径（相对路径或绝对路径）
            content: 笔记正文内容
            wait_for_login: 是否等待用户登录（首次调用应为False，让用户手动登录后再调用）

        Returns:
            dict: 包含 status, message, url(可选) 的结果
        """
        result = {
            "status": "error",
            "message": "",
        }

        try:
            # 1. 启动浏览器
            self.start_browser()

            # 2. 检查登录状态
            is_logged_in = self.check_login_status()

            if not is_logged_in:
                # 尝试加载 cookie
                if self.load_cookies():
                    self.driver.refresh()
                    time.sleep(3)
                    is_logged_in = self.check_login_status()

                if not is_logged_in:
                    # 打开登录页面让用户登录
                    logger.info("打开小红书登录页面...")
                    self.driver.get("https://creator.xiaohongshu.com/")

                    result["status"] = "need_login"
                    result["message"] = "请在打开的浏览器中完成小红书登录，然后再次点击发布按钮"
                    result["browser_opened"] = True
                    # 重要：不关闭浏览器，让用户在浏览器里登录
                    # 浏览器实例会保持运行，因为我们在 finally 中检查 status
                    return result

            # 保存当前登录状态的 cookie
            self.save_cookies()

            # 保存当前登录状态的 cookie
            self.save_cookies()

            # 更新活动时间
            XHSPublisher._last_activity_time = time.time()

            # 3. 处理图片路径
            # 如果传入的是相对路径（如 /static/posters/xxx.jpg）
            if image_path.startswith("/static/"):
                image_path = image_path.lstrip("/")
            if not os.path.isabs(image_path):
                image_path = os.path.join(os.getcwd(), image_path)

            # 4. 点击发布笔记
            if not self._click_publish_note_button():
                result["message"] = "无法点击发布笔记按钮"
                return result

            # 5. 上传图片
            if not self._upload_image(image_path):
                result["message"] = "图片上传失败"
                return result

            # 6. 输入正文
            if not self._input_content(content):
                result["message"] = "输入正文失败"
                return result

            # 7. 点击发布按钮
            if not self._click_publish_button():
                result["message"] = "无法点击发布按钮"
                return result

            logger.info("发布按钮已点击，等待6秒...")
            time.sleep(6)

            # 8. 返回成功
            result["status"] = "success"
            result["message"] = "发布成功"
            result["url"] = ""

            return result

        except Exception as e:
            logger.exception("发布过程中发生异常")
            result["message"] = f"发布异常: {str(e)}"
            return result

        finally:
            # 发布成功或出错时，强制关闭浏览器
            # 需要登录时，保持浏览器打开让用户登录
            status = result.get("status")
            if status == "success":
                logger.info("发布成功，关闭浏览器")
                self.close_browser(force=True)
            elif status == "error":
                logger.info("发布出错，关闭浏览器")
                self.close_browser(force=True)
            elif status == "need_login":
                logger.info("等待用户登录，保持浏览器打开")
                # 不关闭浏览器，让它保持运行
                pass


# 便捷函数，供外部调用
def publish_to_xiaohongshu(image_path: str, content: str) -> Dict[str, Any]:
    """
    一键发布到小红书的便捷函数

    Args:
        image_path: 图片路径
        content: 笔记内容

    Returns:
        dict: 发布结果
    """
    publisher = XHSPublisher()
    return publisher.publish_note(image_path, content)


if __name__ == "__main__":
    # 测试代码
    test_result = publish_to_xiaohongshu(
        image_path="./static/posters/test.jpg",
        content="测试寻宠文案\n#寻宠 #宠物丢失"
    )
    print(test_result)
