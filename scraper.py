"""
小红书帖子监控脚本 - GitHub Actions 版本
使用 Playwright 爬取小红书搜索结果并推送到微信
"""

import json
import time
import requests
import urllib.parse
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

# 从环境变量读取配置（GitHub Actions 安全存储）
import os
XHS_COOKIE = os.environ['XHS_COOKIE']
SENDKEY = os.environ['SENDKEY']
KEYWORD = os.environ.get('KEYWORD', '华泰FINTECH 星战营 实习')
MAX_RESULTS = int(os.environ.get('MAX_RESULTS', '10'))

RESULT_FILE = "/tmp/latest.json"


def parse_cookie_string(cookie_str):
    """将 Cookie 字符串解析为 Playwright 可用的格式"""
    cookies = []
    for item in cookie_str.split("; "):
        if "=" in item:
            name, value = item.split("=", 1)
            cookies.append({
                "name": name.strip(),
                "value": value.strip(),
                "domain": ".xiaohongshu.com",
                "path": "/"
            })
    return cookies


def scrape_xhs():
    """使用 Playwright 爬取小红书搜索结果"""
    print(f"🔍 开始搜索关键词: {KEYWORD}")
    
    with sync_playwright() as p:
        # 启动浏览器（无头模式）
        browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        # 添加 Cookie
        cookies = parse_cookie_string(XHS_COOKIE)
        context.add_cookies(cookies)
        
        page = context.new_page()
        
        # 访问小红书搜索页面
        keyword_encoded = urllib.parse.quote(KEYWORD)
        search_url = f"https://www.xiaohongshu.com/search_result?keyword={keyword_encoded}&source=web_search_result_notes"
        print(f"🌐 访问搜索页面...")
        page.goto(search_url, timeout=60000)
        
        # 等待页面加载
        print("⏳ 等待页面加载...")
        time.sleep(8)
        
        # 尝试等待笔记卡片出现
        try:
            page.wait_for_selector("section.note-item", timeout=15000)
            print("✅ 页面加载完成，找到笔记卡片")
        except PlaywrightTimeout:
            print("⚠️  未找到笔记卡片，可能页面结构已变化")
            page.screenshot(path="/tmp/debug_screenshot.png")
            print("📸 已保存调试截图")
        
        # 提取帖子信息
        print("📊 提取帖子信息...")
        posts = page.evaluate("""() => {
            const items = document.querySelectorAll('section.note-item');
            const results = [];
            items.forEach(item => {
                const link = item.querySelector('a');
                const title = item.querySelector('.title');
                const desc = item.querySelector('.desc');
                const author = item.querySelector('.author');
                
                if (link) {
                    const href = link.getAttribute('href');
                    results.push({
                        title: title ? title.innerText.trim() : '无标题',
                        link: href.startsWith('http') ? href : 'https://www.xiaohongshu.com' + href,
                        desc: desc ? desc.innerText.trim() : '',
                        author: author ? author.innerText.trim() : ''
                    });
                }
            });
            return results;
        }""")
        
        browser.close()
        
        # 限制结果数量
        posts = posts[:MAX_RESULTS]
        print(f"✅ 找到 {len(posts)} 条帖子")
        return posts


def push_to_wechat(posts):
    """通过 Server酱 推送到微信"""
    if not posts:
        print("ℹ️  没有找到新帖子，不推送")
        return
    
    # 构造推送内容
    title = f"📢 小红书「{KEYWORD}」最新帖子 ({len(posts)}条)"
    content = f"# 小红书搜索结果\n\n关键词：**{KEYWORD}**\n\n"
    content += "---\n\n"
    
    for i, post in enumerate(posts, 1):
        content += f"## {i}. {post['title']}\n\n"
        if post['author']:
            content += f"👤 作者: {post['author']}\n\n"
        if post['desc']:
            desc = post['desc'][:200]
            content += f"📝 摘要: {desc}...\n\n"
        content += f"🔗 链接: {post['link']}\n\n"
        content += "---\n\n"
    
    content += f"\n> 推送时间: {time.strftime('%Y-%m-%d %H:%M:%S')}"
    
    # 调用 Server酱 API
    print("📤 推送到微信...")
    url = f"https://sctapi.ftqq.com/{SENDKEY}.send"
    data = {
        "title": title,
        "desp": content
    }
    
    try:
        resp = requests.post(url, data=data, timeout=15)
        result = resp.json()
        if result.get("code") == 0:
            print("✅ 推送成功!")
        else:
            print(f"❌ 推送失败: {result}")
    except Exception as e:
        print(f"❌ 推送异常: {e}")


def main():
    """主函数"""
    print("=" * 50)
    print("🚀 小红书帖子监控脚本启动")
    print("=" * 50)
    
    try:
        # 爬取帖子
        posts = scrape_xhs()
        
        # 保存结果
        with open(RESULT_FILE, "w", encoding="utf-8") as f:
            json.dump({"count": len(posts), "posts": posts}, f, ensure_ascii=False, indent=2)
        print(f"💾 结果已保存: {RESULT_FILE}")
        
        # 推送到微信
        push_to_wechat(posts)
        
        print("=" * 50)
        print("✅ 任务完成!")
        print("=" * 50)
        
    except Exception as e:
        print(f"❌ 任务失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

