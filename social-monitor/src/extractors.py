"""四平台内容提取。

所有平台统一使用 Playwright 无头 Chromium 渲染页面并提取，
选择器可经 config.json 的 selectors 覆盖（这几个站 DOM 常变，需按实际调）。

所有提取函数返回统一结构：[{"id","url","text","time"}, ...]
id 取内容唯一标识（用内容链接），用于差集比对。
"""
import json
import re
from typing import List, Dict, Any, Optional

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


def _load_cookies(cookies: Any) -> List[Dict]:
    if isinstance(cookies, str):
        try:
            return json.loads(cookies)
        except Exception:  # noqa: BLE001
            return []
    return cookies or []


def _normalize_cookies_for_playwright(cookies: List[Dict]) -> List[Dict]:
    """把 Cookie-Editor 导出的 cookie 转为 Playwright add_cookies 可接受的格式。

    关键映射：
    - sameSite: "no_restriction" -> "None", null -> "Lax"
    - expirationDate -> expires
    - 去掉 hostOnly/session/storeId 等 Playwright 不认的字段
    - 过滤掉 name 为空的 cookie
    """
    _SAME_SITE_MAP = {"no_restriction": "None"}
    result = []
    for c in cookies:
        if not c.get("name"):
            continue
        nc = {}
        for k, v in c.items():
            if k in ("hostOnly", "session", "storeId"):
                continue
            if k == "sameSite":
                if v is None:
                    v = "Lax"
                elif isinstance(v, str):
                    v = _SAME_SITE_MAP.get(v, v)
            elif k == "expirationDate":
                k = "expires"
                v = int(v) if v else None
            nc[k] = v
        result.append(nc)
    return result


# --------------------- 全平台（Playwright 渲染） ---------------------
def _playwright_extract(url: str, cookies: Any, item_sel: str) -> List[Dict]:
    from playwright.sync_api import sync_playwright  # 懒加载，避免无谓依赖

    ck = _load_cookies(cookies)
    ck = _normalize_cookies_for_playwright(ck)
    # 补全 domain/path：Cookie-Editor 导出的已含 domain；手动导出的只有 name/value，
    # 需补上 domain 否则 Playwright add_cookies 会报错。
    try:
        from urllib.parse import urlparse
        host = urlparse(url).netloc
        for c in ck:
            if isinstance(c, dict):
                c.setdefault("domain", host)
                c.setdefault("path", "/")
    except Exception:  # noqa: BLE001
        pass
    items: List[Dict] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"]
        )
        context = browser.new_context(user_agent=UA)
        if ck:
            context.add_cookies(ck)
        page = context.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=45000)
            try:
                page.wait_for_selector(item_sel, timeout=20000)
            except Exception:  # noqa: BLE001
                pass
            # 滚动几次触发懒加载
            for _ in range(4):
                page.mouse.wheel(0, 1500)
                page.wait_for_timeout(900)
            items = page.eval_on_selector_all(
                item_sel,
                """(els) => els.slice(0, 20).map(el => {
                    const a = el.querySelector('a');
                    const href = a ? a.href : '';
                    const txt = (el.innerText || '').replace(/\\s+/g, ' ').trim().slice(0, 120);
                    return { id: href || (el.outerHTML||'').slice(0, 80), url: href, text: txt, time: '' };
                })""",
            )
        except Exception as exc:  # noqa: BLE001
            items = [{"id": "ERR", "url": url, "text": f"抓取异常:{exc}", "time": ""}]
        finally:
            browser.close()

    # 去重
    seen, res = set(), []
    for it in items:
        key = it.get("id")
        if not key or key in seen:
            continue
        seen.add(key)
        res.append(it)
    return res


# ----------------------------- 调度入口 -----------------------------
def extract(platform: str, url: str, cookies: Any = None,
            selectors: Optional[Dict] = None) -> List[Dict]:
    selectors = selectors or {}
    sel_map = {
        "weibo": "div.card-wrap, div.WB_feed_type",
        "douyin": "li[data-e2e=\"user-post-item\"], div[data-e2e=\"user-post-item\"]",
        "xiaohongshu": "section.note-item",
        "kuaishou": "div[data-e2e=\"feed-item\"], div.video-card",
    }
    item_sel = selectors.get(platform, sel_map.get(platform, ""))
    return _playwright_extract(url, cookies, item_sel)
