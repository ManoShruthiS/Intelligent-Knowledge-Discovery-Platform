from __future__ import annotations
from typing import List, Sequence

def reorder_for_lost_in_middle(chunks: Sequence[dict]) -> List[dict]:
    if not chunks:
        return []
    if len(chunks) < 3:
        return list(chunks)
    out: List[dict] = []
    pool = list(chunks)
    head: List[dict] = []
    tail: List[dict] = []
    take_head = True
    while pool:
        item = pool.pop(0)
        if take_head:
            head.append(item)
        else:
            tail.append(item)
        take_head = not take_head
    return head + list(reversed(tail))
