# 小红书爬虫与自动化发布工具

基于 Selenium 的小红书（Xiaohongshu）数据爬取与图文自动发布工具。

## 功能特性

- **帖子爬取**：支持关键词搜索、时间筛选（一天内）、排序筛选（最新），自动滚动加载并提取帖子内容
- **图片下载**：自动过滤头像图片，按顺序或帖子ID命名保存
- **元数据保存**：提取帖子文本、发布时间、用户ID、图片URL等信息，保存为 JSON 格式，支持追加去重
- **图文发布**：支持自动登录创作者平台并发布图文笔记
- **浏览器支持**：Chrome（推荐）、Safari
- **无头模式**：Chrome 支持无头模式，可在后台运行

## 目录结构

```
.
├── pet_spider/
│   ├── xhs_automation.py   # 主爬虫脚本
│   ├── xhs_publisher.py    # 图文自动发布模块
│   └── config.py           # 爬虫配置（选择器、滚动次数等）
├── core/
│   └── crawler_manager.py  # 爬虫管理器（子进程封装、日志监控）
├── cookies_example.json    # Cookie 配置模板
├── requirements.txt
└── README.md
```

## 安装

1. 克隆仓库

```bash
git clone https://github.com/YOUR_USERNAME/xhs-pet-spider.git
cd xhs-pet-spider
```

2. 安装依赖

```bash
pip install -r requirements.txt
```

3. 安装浏览器驱动

- **Chrome**：脚本会自动通过 `webdriver-manager` 下载驱动，也可手动安装 [ChromeDriver](https://chromedriver.chromium.org/)
- **Safari**：在 Safari 中启用"允许远程自动化"（Safari -> 设置 -> 高级 -> 勾选"在菜单栏中显示开发菜单"，然后 开发 -> 允许远程自动化）

## 配置 Cookie

小红书需要登录后才能正常使用搜索和发布功能。

1. 使用浏览器登录 [xiaohongshu.com](https://www.xiaohongshu.com)
2. 导出 Cookie 为 JSON 格式（可通过浏览器开发者工具或 EditThisCookie 等扩展）
3. 将 Cookie 保存为 `cookies.json` 放在项目根目录

Cookie 格式示例见 [cookies_example.json](cookies_example.json)。

## 使用方式

### 1. 命令行直接运行爬虫

```bash
python pet_spider/xhs_automation.py --keyword "深圳 走丢 小狗" --max-posts 10
```

常用参数：

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--keyword` | 搜索关键词（必填） | - |
| `--cookies` | Cookie 文件路径 | `cookies.json` |
| `--browser` | 浏览器类型：`chrome` / `safari` | `chrome` |
| `--headless` | 无头模式（仅 Chrome） | `False` |
| `--max-posts` | 最大提取帖子数（0=无限制） | 配置值 |
| `--scroll-times` | 滚动加载次数 | 配置值 |
| `--no-images` | 不下载图片 | `False` |
| `--output-dir` | 图片保存目录 | `gallery/` |

### 2. 通过 CrawlerManager 调用（非阻塞）

```python
from core.crawler_manager import CrawlerManager

manager = CrawlerManager()
manager.start_crawler(
    keyword="深圳 走丢 小狗",
    max_posts=10,
    browser_type='chrome',
    headless=True
)

# 获取日志
print(manager.get_logs())

# 获取状态
print(manager.get_status())

# 停止爬虫
manager.stop_crawler()
```

### 3. 发布图文到小红书

```python
from pet_spider.xhs_publisher import publish_to_xiaohongshu

result = publish_to_xiaohongshu(
    image_path="./poster.jpg",
    content="这是一条测试笔记\n#测试 #小红书"
)

print(result)
```

首次发布需要手动在弹出的浏览器中完成登录，登录态会自动保存到 `chrome_data/publish/cookies.json`。

## 配置文件说明

[config.py](pet_spider/config.py) 中包含以下可调整项：

- `BROWSER_TYPE`：默认浏览器
- `HEADLESS`：是否开启无头模式
- `SELECTORS`：页面元素 CSS/XPath 选择器（小红书页面更新时可在此调整）
- `SCROLL_CONFIG`：滚动次数、暂停时间等
- `DATA_EXTRACT_CONFIG`：最大提取数、是否下载图片、命名方式等

## 输出说明

- **图片**：默认保存到 `gallery/` 目录，命名格式为 `post_001_img_01.jpg`
- **元数据**：保存为 `posts_metadata.json`，包含帖子ID、文本、链接、时间、用户ID、图片URL等
- **日志**：控制台实时输出爬取进度

## 注意事项

1. **Cookie 有效期**：小红书 Cookie 可能会过期，如遇登录失败请重新导出
2. **页面结构变化**：小红书页面更新可能导致选择器失效，可在 `config.py` 中调整
3. **频率控制**：建议合理设置滚动次数和提取数量，避免请求过于频繁
4. **法律合规**：请遵守相关法律法规及平台用户协议，仅用于学习和合法用途

## 免责声明

本工具仅供学习研究使用，使用者需自行承担因使用本工具而产生的全部责任和后果。请尊重平台规则，合理使用爬虫技术。
