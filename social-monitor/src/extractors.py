"""四平台内容提取。

- 微博：走 m.weibo.cn 公开 JSON 接口（最稳，不依赖渲染）。
- 抖音 / 快手 / 小红书：用 Playwright 无头 Chromium 渲染页面并提取，
  选择器可经 config.json 的 selectors 覆盖（这几个站 DOM 常变，需按实际调）。

所有提取函数返回统一结构：[{"id","url","text","time"}, ...]
id 取内容唯一标识（微博用 mblog id；其余用内容链接），用于差集比对。
"""
import json
import re
import urllib.request
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


def _cookie_header(cookies: List[Dict]) -> str:
    return "; ".join(f"{c.get('name')}={c.get('value')}" for c in cookies)


# ----------------------------- 微博 -----------------------------
def extract_weibo(url: str, cookies: Any = None) -> List[Dict]:
    m = re.search(r"/u/(\d+)", url) or re.search(r"uid=(\d+)", url)
    uid = m.group(1) if m else None
    if not uid:
        return [{"id": "ERR", "url": url, "text": "微博UID解析失败", "time": ""}]
    containerid = f"107603{uid}"
    api = (f"https://m.weibo.cn/api/container/getIndex?type=uid&value={uid}"
           f"&containerid={containerid}&page=1")
    req = urllib.request.Request(api, headers={
        "User-Agent": UA,
        "Referer": f"https://m.weibo.cn/u/{uid}",
        "Accept": "application/json",
        "X-Requested-With": "XMLHttpRequest",
    })
    ck = _load_cookies(cookies)
    if ck:
        req.add_header("Cookie", _cookie_header(ck))
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        return [{"id": "ERR", "url": url, "text": f"微博抓取失败:{exc}", "time": ""}]
    items: List[Dict] = []
    for card in data.get("data", {}).get("cards", []):
        mb = card.get("mblog")
        if not mb:
            continue
        bid = str(mb.get("id"))
        text = re.sub(r"<[^>]+>", "", mb.get("text", "")).strip()
        items.append({
            "id": bid,
            "url": f"https://m.weibo.cn/detail/{bid}",
            "text": text[:120],
            "time": mb.get("created_at", ""),
        })
    return items


# --------------------- 抖音 / 快手 / 小红书（Playwright） ---------------------
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
    if platform == "weibo":
        return extract_weibo(url, cookies)
    if platform == "douyin":
        return _playwright_extract(url, cookies, selectors.get("douyin", ""))
    if platform == "xiaohongshu":
        return _playwright_extract(url, cookies, selectors.get("xiaohongshu", ""))
    if platform == "kuaishou":
        return _playwright_extract(url, cookies, selectors.get("kuaishou", ""))
    return [{"id": "ERR", "url": url, "text": f"未知平台:{platform}", "time": ""}]
