"""快照差集：对比上一次记录的 ID 列表与本次抓取到的条目。"""
from typing import List, Dict, Tuple


def diff_snapshots(prev_ids: List[str], curr_items: List[Dict]) -> Tuple[List[Dict], List[str]]:
    """返回 (新增条目, 消失的ID)。"""
    prev = set(prev_ids or [])
    new = [it for it in curr_items if it.get("id") not in prev]
    curr = {it.get("id") for it in curr_items}
    removed = [pid for pid in prev_ids if pid not in curr]
    return new, removed


if __name__ == "__main__":
    prev = ["a", "b"]
    curr = [
        {"id": "a", "text": "old"},
        {"id": "b", "text": "old"},
        {"id": "c", "text": "new"},
    ]
    new, removed = diff_snapshots(prev, curr)
    assert [it["id"] for it in new] == ["c"], new
    assert removed == [], removed
    print("diff OK, new:", [it["id"] for it in new])
