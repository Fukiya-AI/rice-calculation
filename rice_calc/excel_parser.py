"""食数内訳ワゴン表（xlsb/xlsx）を解析するモジュール。

想定している表のレイアウト:
  - 1行目: 日付（1, 2, 3, ...）
  - 2行目: 曜日（火, 水, 木, ...）
  - 3行目以降: クラスごとの人数。「〇〇ワゴン」で終わる行はそのグループの合計行。
    - 合計行の直前が1行だけ（かつ「教員」行が無い）場合 → 1・2才クラス単独
      （教員は別枠で管理されていないため、そのままクラス人数として扱う）
    - 合計行の直前が「クラス行 + 教員」の2行 → 5才クラス
      （教員はそのクラス専用なのでそのまま加算する）
    - 合計行の直前が「クラス行 + クラス行 + 教員」の3行 → 3才・4才クラス
      （教員は2クラス共有のため、人数を半分ずつに分配する。割り切れない場合は
      先に出てくるクラス（例: ほし、ひばり）に多い方を割り振る）
  - 「事務所」行: 職員（事務所）人数
  - それ以降の空白行より下は無視する（総数など）
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import pandas as pd


@dataclass
class ClassCount:
    children: int
    teachers: int
    age_key: str  # "1_2" / "3" / "4" / "5"


@dataclass
class DayData:
    label: str
    classes: dict = field(default_factory=dict)  # class_name -> ClassCount
    staff: int = 0


@dataclass
class WagonTable:
    month_label: str
    days: dict  # label -> DayData


def _normalize(value) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip().replace("　", " ").strip()


def load_wagon_dataframe(file, filename: str) -> pd.DataFrame:
    ext = filename.lower().rsplit(".", 1)[-1]
    engine = "pyxlsb" if ext == "xlsb" else "openpyxl"
    return pd.read_excel(file, engine=engine, header=None)


def _find_header_row(df: pd.DataFrame) -> int:
    for i in range(min(5, len(df))):
        row = df.iloc[i, 1:]
        numeric_count = sum(
            isinstance(v, (int, float)) and not pd.isna(v) for v in row
        )
        if numeric_count >= 5:
            return i
    raise ValueError("日付ヘッダー行が見つかりませんでした。表の形式を確認してください。")


def _age_key_from_label(label: str) -> str:
    m = re.match(r"^\s*(\d)\s*歳", label)
    if not m:
        raise ValueError(f"クラス行から年齢を判定できません: 「{label}」")
    age = int(m.group(1))
    if age in (1, 2):
        return "1_2"
    if age in (3, 4, 5):
        return str(age)
    raise ValueError(f"想定していない年齢です: 「{label}」")


def _clean_class_name(label: str) -> str:
    m = re.match(r"^\s*(\d)\s*歳", label)
    age_num = m.group(1) if m else ""
    name = label.replace("歳", "").replace("才", "")
    name = re.sub(r"ワゴン\s*$", "", name).strip()
    name = re.sub(r"^\d+\s*", "", name).strip()
    if not name:
        name = f"{age_num}才"
    return name


def parse_wagon_table(df: pd.DataFrame) -> WagonTable:
    header_row = _find_header_row(df)
    weekday_row = header_row + 1
    data_start = header_row + 2

    month_label = _normalize(df.iat[header_row, 0])

    data_end = data_start
    while data_end < len(df) and _normalize(df.iat[data_end, 0]) != "":
        data_end += 1

    day_cols = []
    for col in range(1, df.shape[1]):
        day_val = df.iat[header_row, col]
        weekday_val = _normalize(df.iat[weekday_row, col]) if weekday_row < len(df) else ""
        if pd.isna(day_val) or weekday_val == "":
            continue
        day_cols.append(col)

    rows = [(r, _normalize(df.iat[r, 0])) for r in range(data_start, data_end)]

    segments: list[list[tuple[int, str]]] = []
    current: list[tuple[int, str]] = []
    staff_row = None
    for r, label in rows:
        if label == "":
            continue
        if label.endswith("事務所"):
            staff_row = r
            continue
        current.append((r, label))
        if label.endswith("ワゴン"):
            segments.append(current)
            current = []
    if current:
        raise ValueError(
            f"「ワゴン」で終わる合計行が見つからないグループがあります: {[l for _, l in current]}"
        )

    def build_classes_for_col(col: int) -> dict:
        classes: dict[str, ClassCount] = {}
        for seg in segments:
            if len(seg) == 1:
                # 1・2才クラスは「クラス行」と「合計行」が同一行のため、そのまま使う
                body = seg
            else:
                body = seg[:-1]  # 合計行は検算に使わないため読み捨てる
            teacher_rows = [(i, r, lbl) for i, (r, lbl) in enumerate(body) if lbl == "教員"]
            class_rows = [(i, r, lbl) for i, (r, lbl) in enumerate(body) if lbl != "教員"]

            if not class_rows:
                continue

            age_key = _age_key_from_label(class_rows[0][2])

            def get_int(r: int) -> int:
                v = df.iat[r, col]
                return int(v) if not pd.isna(v) else 0

            if len(class_rows) == 1 and not teacher_rows:
                _, r, lbl = class_rows[0]
                classes[_clean_class_name(lbl)] = ClassCount(
                    children=get_int(r), teachers=0, age_key=age_key
                )
            elif len(class_rows) == 1 and len(teacher_rows) == 1:
                _, r, lbl = class_rows[0]
                _, tr, _ = teacher_rows[0]
                classes[_clean_class_name(lbl)] = ClassCount(
                    children=get_int(r), teachers=get_int(tr), age_key=age_key
                )
            elif len(class_rows) == 2 and len(teacher_rows) == 1:
                (_, r1, lbl1), (_, r2, lbl2) = class_rows
                _, tr, _ = teacher_rows[0]
                t = get_int(tr)
                t1 = -(-t // 2)  # 先のクラスに端数を寄せる（切り上げ）
                t2 = t // 2
                classes[_clean_class_name(lbl1)] = ClassCount(
                    children=get_int(r1), teachers=t1, age_key=age_key
                )
                classes[_clean_class_name(lbl2)] = ClassCount(
                    children=get_int(r2), teachers=t2, age_key=age_key
                )
            else:
                raise ValueError(
                    f"想定外のグループ構成です: {[lbl for _, lbl in body]}"
                )
        return classes

    days: dict[str, DayData] = {}
    for col in day_cols:
        day_num = df.iat[header_row, col]
        weekday = _normalize(df.iat[weekday_row, col])
        label = f"{int(day_num)}日({weekday})"

        staff = 0
        if staff_row is not None:
            v = df.iat[staff_row, col]
            staff = int(v) if not pd.isna(v) else 0

        days[label] = DayData(label=label, classes=build_classes_for_col(col), staff=staff)

    return WagonTable(month_label=month_label, days=days)
