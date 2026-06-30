from __future__ import annotations

import random
from .models import LootItem


def draw_loot(items: list[LootItem]) -> LootItem | None:
    if not items:
        return None
    population = [item for item in items]
    weights = [max(1, item.weight) for item in population]
    return random.choices(population, weights=weights, k=1)[0]
