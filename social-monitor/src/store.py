"""快照存储：本地文件（默认）或腾讯云 COS（云函数冷启动后不丢）。

快照是一个 dict：{ 目标名: [条目ID列表], "__heartbeat": "YYYY-MM-DD" }

GitHub Actions 路线：store.path 设为相对路径 `data/snapshots.json`，
每次运行后由工作流把该文件提交回仓库，实现快照跨运行持久化（不依赖 artifact）。
"""
import json
import os
from typing import Dict, Any

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _abs(path: str) -> str:
    return path if os.path.isabs(path) else os.path.join(REPO_ROOT, path)


def load_snapshots(store_cfg: Dict[str, Any]) -> Dict[str, Any]:
    if store_cfg.get("type") == "cos":
        return _load_cos(store_cfg)
    path = _abs(store_cfg.get("path", "data/snapshots.json"))
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:  # noqa: BLE001
        return {}


def save_snapshots(store_cfg: Dict[str, Any], data: Dict[str, Any]) -> None:
    if store_cfg.get("type") == "cos":
        _save_cos(store_cfg, data)
        return
    path = _abs(store_cfg.get("path", "data/snapshots.json"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _load_cos(store_cfg: Dict[str, Any]) -> Dict[str, Any]:
    try:
        from qcloud_cos import CosConfig, CosS3Client
    except Exception:
        return {}
    client = CosS3Client(CosConfig(
        Region=store_cfg["cos_region"],
        SecretId=os.environ["COS_SECRET_ID"],
        SecretKey=os.environ["COS_SECRET_KEY"],
    ))
    try:
        resp = client.get_object(Bucket=store_cfg["cos_bucket"],
                                  Key=store_cfg.get("cos_key", "snapshots.json"))
        return json.loads(resp["Body"].get_raw_stream().read())
    except Exception:  # noqa: BLE001
        return {}


def _save_cos(store_cfg: Dict[str, Any], data: Dict[str, Any]) -> None:
    from qcloud_cos import CosConfig, CosS3Client
    client = CosS3Client(CosConfig(
        Region=store_cfg["cos_region"],
        SecretId=os.environ["COS_SECRET_ID"],
        SecretKey=os.environ["COS_SECRET_KEY"],
    ))
    client.put_object(
        Bucket=store_cfg["cos_bucket"],
        Key=store_cfg.get("cos_key", "snapshots.json"),
        Body=json.dumps(data, ensure_ascii=False),
    )
