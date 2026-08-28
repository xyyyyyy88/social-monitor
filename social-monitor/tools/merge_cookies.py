#!/usr/bin/env python3
"""合并多个平台导出的 Cookie-Editor JSON 数组，输出可直接塞进 Secret: DTC_COOKIES 的单一数组。

用法：
  python tools/merge_cookies.py douyin.json kuaishou.json xiaohongshu.json
  # 不传参则尝试读取当前目录下的 douyin.json / kuaishou.json / xiaohongshu.json

输出：
  - 终端打印【单行紧凑 JSON】，直接复制粘贴到 GitHub Secret: DTC_COOKIES
  - 同时写 merged_cookies.json（带缩进，便于查看）

按 (name, domain) 去重，避免同一 cookie 被重复写入。
"""
import json
import os
import sys

DEFAULT_FILES = ["douyin.json", "kuaishou.json", "xiaohongshu.json"]


def load(fp: str):
    with open(fp, encoding="utf-8") as f:
        return json.load(f)


def main() -> None:
    files = [a for a in sys.argv[1:] if a] or [f for f in DEFAULT_FILES if os.path.exists(f)]
    if not files:
        print("未找到 cookie 文件。请把各平台导出的 JSON 传给脚本，例如：")
        print("  python tools/merge_cookies.py douyin.json kuaishou.json xiaohongshu.json")
        sys.exit(1)

    merged, seen = [], set()
    for fp in files:
        try:
            arr = load(fp)
        except Exception as exc:  # noqa: BLE001
            print(f"跳过 {fp}（解析失败）：{exc}")
            continue
        if not isinstance(arr, list):
            print(f"跳过 {fp}（不是 JSON 数组）")
            continue
        for c in arr:
            if not isinstance(c, dict):
                continue
            key = (c.get("name"), c.get("domain"))
            if key in seen:
                continue
            seen.add(key)
            merged.append(c)

    compact = json.dumps(merged, ensure_ascii=False, separators=(",", ":"))
    with open("merged_cookies.json", "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    print(f"共合并 {len(merged)} 条 cookie（来自 {len(files)} 个文件）")
    print("---- 复制下面这行到 GitHub Secret: DTC_COOKIES ----")
    print(compact)
    print("---------------------------------------------------")
    print("（同时已写 merged_cookies.json 供查看）")


if __name__ == "__main__":
    main()
