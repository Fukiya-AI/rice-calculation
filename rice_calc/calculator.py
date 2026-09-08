"""配缶量・生米・水・味噌汁の水の計算ロジック。"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from rice_calc.excel_parser import ClassCount

RICE_CONVERSION_FACTOR = 2.2  # 炊き上がりkg ÷ 2.2 = 生米kg
NOODLE_BALL_G = 200  # めん1玉あたりのグラム数

# 生米・水の換算対象になる献立（実際の「ごはん」を炊く必要があるもの）
RICE_MEAL_TYPES = ("ごはん", "丼ごはん")
# 玉数（個数）で結果を出す献立
NOODLE_MEAL_TYPES = ("めん",)
ALL_MEAL_TYPES = ("ごはん", "丼ごはん", "丼具", "めん")


def round_half_up(value: float, ndigits: int = 0) -> float:
    quantum = Decimal("1").scaleb(-ndigits)
    d = Decimal(str(value)).quantize(quantum, rounding=ROUND_HALF_UP)
    return float(d)


def calc_meal(
    classes: dict[str, ClassCount],
    staff_count: int,
    rate_table: dict[str, float],
    extra_kg: float = 0.0,
    unit_g: float = 1000.0,
    ndigits: int = 1,
) -> tuple[dict[str, float], float]:
    """rate_table: {"1_2": g, "3": g, "4": g, "5": g, "職員": g}

    unit_g/ndigits で出力単位を切り替える（kg: 1000g/小数1桁、玉: 200g/整数、など）。
    """
    results: dict[str, float] = {}
    total = 0.0

    for class_name, info in classes.items():
        g = info.children * rate_table[info.age_key] + info.teachers * rate_table["職員"]
        value = round_half_up(g / unit_g, ndigits)
        results[class_name] = value
        total += value

    staff_value = round_half_up(staff_count * rate_table["職員"] / unit_g, ndigits)
    results["職員"] = staff_value
    total += staff_value

    if extra_kg:
        extra_value = round_half_up(extra_kg, ndigits)
        results["その他"] = extra_value
        total += extra_value

    return results, round_half_up(total, ndigits)


def calc_raw_rice_kg(total_cooked_kg: float) -> float:
    return round_half_up(total_cooked_kg / RICE_CONVERSION_FACTOR, 1)


def calc_water_l(raw_rice_kg: float, multiplier: float) -> float:
    return round_half_up(raw_rice_kg * multiplier, 1)


def calc_soup_water_l(rice_totals_kg: list[float]) -> float:
    return round_half_up(sum(rice_totals_kg), 0)
