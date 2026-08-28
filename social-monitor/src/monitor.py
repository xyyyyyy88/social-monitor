"""主程序：一次调用 = 检查一轮（适合被每小时定时器触发）。

云函数入口（腾讯云 SCF）：见 deploy/tencent_scf.md，把 main(event, context) 指向 run_once。
轻量服务器：用 crontab 每小时执行 `python src/monitor.py`。
"""
import json
import os
import re
import time
from typing import Dict, Any, List

from dingtalk import push_markdown
from store import load_snapshots, save_snapshots
from diff import diff_snapshots
from extractors import extract

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json")


def _resolve_env(cfg: Any) -> Any:
    """把配置里的 ${VAR} 替换为环境变量值。"""
    s = json.dumps(cfg)
    for key in set(re.findall(r"\$\{(\w+)\}", s)):
        s = s.replace(f"${{{key}}}", os.environ.get(key, ""))
    return json.loads(s)


def _build_markdown(all_new: List[Dict]) -> str:
    lines = ["#### 监测到 {n} 条新内容\n".format(n=len(all_new))]
    for it in all_new:
        plat = it.get("_platform", "")
        name = it.get("_name", "")
        text = it.get("text", "") or "(无文字预览)"
        url = it.get("url", "")
        t = it.get("time", "")
        lines.append(f"- **[{name}]({url})** · {plat} · {t}\n  > {text}")
    if not all_new:
        lines.append("_本轮无新增_")
    return "\n".join(lines)


def run_once(cfg: Dict[str, Any]) -> Dict:
    cfg = _resolve_env(cfg)
    cookies = os.environ.get(cfg.get("cookies_env", ""), "")
    snaps = load_snapshots(cfg["store"])
    all_new: List[Dict] = []

    for t in cfg["targets"]:
        try:
            items = extract(t["platform"], t["url"], cookies, cfg.get("selectors"))
        except Exception as exc:  # noqa: BLE001
            items = [{"id": "ERR", "url": t["url"], "text": f"抓取异常:{exc}", "time": ""}]

        prev = snaps.get(t["name"], [])
        new, _removed = diff_snapshots(prev, items)
        # 保存本轮全部 ID 作为下次基准
        snaps[t["name"]] = [it["id"] for it in items]
        for it in new:
            it["_platform"] = t["platform"]
            it["_name"] = t["name"]
            all_new.append(it)

    save_snapshots(cfg["store"], snaps)

    # 推送新增
    if all_new:
        md = _build_markdown(all_new)
        push_markdown(cfg["dingtalk"]["webhook"], cfg["dingtalk"]["secret"],
                      "监测到新内容", md)

    # 每日存活播报（避免静默失败发现不了）
    if cfg.get("heartbeat"):
        today = time.strftime("%Y-%m-%d")
        if snaps.get("__heartbeat") != today:
            snaps["__heartbeat"] = today
            save_snapshots(cfg["store"], snaps)
            hb = (f"### 监测任务存活播报\n> 日期 {today} · 目标 {len(cfg['targets'])} 个"
                  f" · 本轮新增 {len(all_new)} 条")
            push_markdown(cfg["dingtalk"]["webhook"], cfg["dingtalk"]["secret"],
                          "存活播报", hb)

    return {"new_count": len(all_new)}


def main(event=None, context=None):  # 兼容云函数入口
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    return run_once(cfg)


if __name__ == "__main__":
    result = main()
    print("done:", result)
