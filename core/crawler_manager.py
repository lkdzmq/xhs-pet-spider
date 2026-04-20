"""
爬虫管理模块
处理小红书数据爬取功能

功能：设计CrawlerManager类，使用子进程运行爬虫，支持非阻塞启动、实时日志监控与三级安全停止
"""

import os
import sys
import queue
import subprocess
import signal
import threading
import time
from datetime import datetime

# 检查爬虫脚本
CRAWLER_SCRIPT = os.path.join('pet_spider', 'xhs_automation.py')
CRAWLER_AVAILABLE = os.path.exists(CRAWLER_SCRIPT)

if not CRAWLER_AVAILABLE:
    print(f"警告: 爬虫脚本不存在: {CRAWLER_SCRIPT}")


class CrawlerManager:
    """管理爬虫任务（使用子进程）"""

    def __init__(self):
        self.log_queue = queue.Queue()
        self.crawler_process = None
        self.is_running = False
        self.reader_thread = None
        self.last_success = False

    def log(self, message):
        """添加日志消息"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_msg = f"[{timestamp}] {message}"
        self.log_queue.put(log_msg)
        print(log_msg)

    def run_crawler_task(self, keyword, max_posts, browser_type='chrome', headless=True):
        """运行爬虫任务（在子进程中执行）"""
        self.is_running = True
        self.last_success = False
        self.log(f"开始爬虫任务: 关键词='{keyword}', 数量={max_posts}")

        try:
            script_path = os.path.join('pet_spider', 'xhs_automation.py')
            if not os.path.exists(script_path):
                self.log(f"错误: 爬虫脚本不存在")
                return

            cmd = [
                sys.executable, script_path,
                '--keyword', keyword,
                '--max-posts', str(max_posts),
                '--browser', browser_type,
            ]

            if headless and browser_type == 'chrome':
                cmd.append('--headless')

            cmd.extend(['--output-dir', './gallery'])

            self.crawler_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                bufsize=1,
                universal_newlines=True,
                cwd=os.path.dirname(os.path.dirname(__file__))
            )

            self.reader_thread = threading.Thread(
                target=self.read_process_output,
                args=(self.crawler_process,),
                daemon=True
            )
            self.reader_thread.start()

            while True:
                try:
                    return_code = self.crawler_process.wait(timeout=0.5)
                    if return_code is not None:
                        break
                except subprocess.TimeoutExpired:
                    if self.crawler_process.poll() is not None:
                        break
                    continue

            return_code = self.crawler_process.poll()
            if return_code == 0:
                self.log("✅ 爬取成功完成")
                self.last_success = True
            else:
                self.log(f"⚠️ 爬虫任务结束，返回码: {return_code}")

        except Exception as e:
            self.log(f"❌ 爬虫任务出错: {e}")
        finally:
            self.is_running = False
            self.crawler_process = None
            self.reader_thread = None

    def read_process_output(self, process):
        """读取子进程输出"""
        for line in iter(process.stdout.readline, ''):
            if line:
                line = line.rstrip('\n')
                if line:
                    keywords = ['成功', '完成', '失败', '错误', '爬取', '下载', '提取']
                    if any(kw in line.lower() for kw in keywords):
                        self.log(line)
        process.stdout.close()

    def start_crawler(self, keyword, max_posts, browser_type='chrome', headless=True):
        """启动爬虫任务（非阻塞）"""
        if self.is_running:
            return "⏳ 已有爬虫任务正在运行"

        crawler_thread = threading.Thread(
            target=self.run_crawler_task,
            args=(keyword, max_posts, browser_type, headless),
            daemon=True
        )
        crawler_thread.start()
        return "🚀 开始爬取数据"

    def stop_crawler(self):
        """停止爬虫任务"""
        if self.crawler_process and self.is_running:
            self.log("正在停止爬虫...")
            try:
                self.crawler_process.send_signal(signal.SIGINT)
                time.sleep(2)
                if self.crawler_process.poll() is None:
                    self.crawler_process.terminate()
                    time.sleep(1)
                    if self.crawler_process.poll() is None:
                        self.crawler_process.kill()
                self.log("✅ 爬虫已停止")
            except Exception as e:
                self.log(f"停止出错: {e}")
            finally:
                self.is_running = False
                self.crawler_process = None
                return "✅ 已停止"
        else:
            return "ℹ️ 没有运行中的爬虫任务"

    def get_logs(self):
        """获取所有日志消息"""
        logs = []
        while not self.log_queue.empty():
            try:
                logs.append(self.log_queue.get_nowait())
            except queue.Empty:
                break
        return "\n".join(logs)

    def get_status(self):
        """获取爬虫状态"""
        if self.is_running:
            return "🔄 爬虫运行中..."
        elif self.last_success:
            return "✅ 上次爬取成功"
        else:
            return "⏸️ 就绪"


# 全局爬虫管理器
crawler_manager = CrawlerManager() if CRAWLER_AVAILABLE else None


def start_crawler_ui(keyword, max_posts, browser_type):
    """Gradio界面调用启动爬虫"""
    if not CRAWLER_AVAILABLE:
        return "❌ 爬虫功能不可用"

    if not keyword or not max_posts:
        return "❌ 请输入关键词和数量"

    try:
        max_posts_int = int(max_posts)
        if max_posts_int <= 0:
            return "❌ 数量必须大于0"
    except ValueError:
        return "❌ 数量必须为整数"

    result = crawler_manager.start_crawler(
        keyword=keyword,
        max_posts=max_posts_int,
        browser_type=browser_type,
        headless=True
    )
    return result


def get_crawler_status():
    """获取爬虫状态"""
    if not CRAWLER_AVAILABLE:
        return "❌ 爬虫功能不可用"
    return crawler_manager.get_status()


def stop_crawler_ui():
    """停止爬虫"""
    if not CRAWLER_AVAILABLE:
        return "❌ 爬虫功能不可用", ""
    result = crawler_manager.stop_crawler()
    logs = crawler_manager.get_logs()
    return result, logs
