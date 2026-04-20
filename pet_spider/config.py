"""
配置文件 - 小红书自动化脚本
用户可以在这里修改页面元素选择器和其他参数
"""

# 浏览器配置
BROWSER_TYPE = 'chrome'  # 'safari' 或 'chrome'
HEADLESS = False  # 无头模式（仅Chrome支持）

# Cookie配置
COOKIE_FILE = 'cookies.json'  # Cookie文件路径

# 页面元素选择器（可能需要根据小红书页面更新）
SELECTORS = {
    # 搜索框
    'search_box': 'input[placeholder*="搜索"], input.search-input',
    # 搜索按钮
    'search_button': 'button.search-btn, .search-icon, .ant-btn-primary',
    # 筛选按钮 - 小红书Vue组件样式
    'filter_button': '[data-v-eb91fffe] .filter-icon, .reds-icon.filter-icon, [data-v-eb91fffe][class*="filter"], button[class*="filter"], div[class*="filter"][role="button"], [data-testid="filter-button"], [data-testid*="filter"]',
    # 时间筛选标签（如"发布时间"）
    'time_label': '//*[contains(text(), "发布时间") or contains(text(), "发帖时间") or contains(text(), "时间筛选")]',
    # 时间筛选选项：一天内
    'time_filter': '//*[contains(text(), "一天内") or contains(text(), "24小时") or contains(text(), "1天内") or contains(text(), "今天") or contains(text(), "今日") or contains(text(), "最近一天")]',
    # 排序筛选：最新
    'sort_filter': '//*[contains(text(), "最新") or contains(text(), "按时间") or contains(text(), "时间排序") or contains(text(), "最新发布") or contains(text(), "最新发帖") or contains(text(), "最近发布")]',
    # 标签容器（筛选选项）
    'tag_container': '.tag-container, .tags-container, .filter-options, .filter-panel .tags, .filters-wrapper .tags',
    # 标签项
    'tag_item': '.tags, .tag-item, .filter-tag, [class*="tag"]',
    # 激活的标签
    'active_tag': '.tags.active, .tag-item.active, [class*="tag"].active, .active[class*="tag"]',
    # 应用筛选按钮
    'apply_button': 'button.ant-btn-primary, button.apply-btn, .confirm-btn, .filter-panel button, .filter-container button',
    # 帖子容器
    'post_container': '.note-item, .card, .post-item',
    # 帖子图片 - 排除头像图片
    'post_image': 'img[src*="xhs"]:not([class*="avatar"]), .note-item img:not([class*="avatar"]), .card img:not([class*="avatar"]), .swiper-wrapper img, .image-container img',
    # 发帖时间
    'post_time': '[class*="time"], [class*="Time"], time, .date, .timestamp, .note-item time, .card time',
    # 发帖人ID
    'post_user': '[class*="user"], [class*="author"], [class*="name"], .username, .author-name, .note-item .user-info, .card .user-info',
    # 帖子链接
    'post_link': 'a[href*="/explore/"], a[href*="/note/"], .note-item a, .card a',
    # 用户头像（登录状态检测）
    'user_avatar': '.avatar, .user-avatar, .profile-icon',
    # 登录按钮（未登录时显示）
    'login_button': 'button.login-btn, a.login-link'
}

# 滚动加载配置
SCROLL_CONFIG = {
    'scroll_times': 10,  # 滚动次数
    'scroll_pause': 2.0,  # 每次滚动后暂停时间（秒）
    'load_more_text': '没有更多了',  # 页面底部提示文本
    'initial_load_count': 18,  # 初始加载帖子数量（不滚动时）
    'increment_per_scroll': 9,  # 每次滚动新增帖子数量
}

# 数据提取配置
DATA_EXTRACT_CONFIG = {
    'max_posts': 10,  # 最大提取帖子数量（0表示无限制）
    'download_images': True,  # 是否下载图片
    'image_dir': 'gallery',  # 图片保存目录
    'save_metadata': True,  # 是否保存元数据
    'metadata_file': 'posts_metadata.json',  # 元数据保存文件
    'image_naming': 'sequential',  # 图片命名方式：sequential（顺序）或 post_id（帖子ID）
}

# 等待时间配置（秒）
WAIT_TIMEOUT = 20  # 元素等待超时时间
PAGE_LOAD_WAIT = 5  # 页面加载等待时间

# 调试配置
DEBUG = True  # 是否打印调试信息
SAVE_SCREENSHOT = False  # 是否在出错时保存截图
SCREENSHOT_DIR = 'screenshots'  # 截图保存目录