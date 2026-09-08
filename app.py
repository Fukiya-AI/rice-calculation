import io

import pandas as pd
import streamlit as st

from rice_calc import calculator as calc
from rice_calc import excel_export
from rice_calc import excel_parser as parser
from rice_calc import settings_store as store

st.set_page_config(page_title="ごはん配缶量計算", layout="wide")


def page_calc():
    st.header("ごはん配缶量計算")

    uploaded = st.file_uploader(
        "食数内訳ワゴン表をアップロード（.xlsb / .xlsx）", type=["xlsb", "xlsx"]
    )
    if uploaded is None:
        st.info("エクセルファイルをアップロードしてください。")
        return

    try:
        df = parser.load_wagon_dataframe(io.BytesIO(uploaded.getvalue()), uploaded.name)
        table = parser.parse_wagon_table(df)
    except Exception as e:
        st.error(f"エクセルの読み込みに失敗しました: {e}")
        return

    st.caption(f"読み込んだ月: {table.month_label}")

    day_labels = list(table.days.keys())
    day_label = st.selectbox("計算する日付", day_labels)
    day = table.days[day_label]

    settings = store.load_settings()

    st.subheader("その日の人数（教員は分配済み・必要なら修正できます）")
    rows = []
    for class_name, c in day.classes.items():
        rows.append(
            {
                "クラス": class_name,
                "年齢区分": store.AGE_LABELS[c.age_key],
                "園児数": c.children,
                "教員数": c.teachers,
            }
        )
    rows.append({"クラス": "職員（事務所）", "年齢区分": "職員", "園児数": 0, "教員数": day.staff})
    count_df = pd.DataFrame(rows)
    edited_df = st.data_editor(count_df, hide_index=True, use_container_width=True, key="counts")

    meal_types = st.multiselect(
        "計算する献立を選択",
        list(store.MEAL_TYPES),
        default=["ごはん"],
        help="その日に必要な献立をすべて選んでください（例: 丼の日は「丼ごはん」と「丼具」の両方）",
    )

    col1, col2 = st.columns(2)
    with col1:
        extra_kg = st.number_input("その他（手入力・kg）", min_value=0.0, value=0.0, step=0.1)
    with col2:
        water_multiplier = st.number_input(
            "水の倍率（生米kg × 倍率 = 水L）",
            min_value=0.0,
            value=float(settings["water_multiplier_default"]),
            step=0.1,
        )

    if st.button("計算する", type="primary"):
        classes = {}
        for _, r in edited_df.iterrows():
            if r["クラス"] == "職員（事務所）":
                continue
            age_key = next(k for k, v in store.AGE_LABELS.items() if v == r["年齢区分"])
            classes[r["クラス"]] = parser.ClassCount(
                children=int(r["園児数"]), teachers=int(r["教員数"]), age_key=age_key
            )
        staff_row = edited_df[edited_df["クラス"] == "職員（事務所）"].iloc[0]
        staff_count = int(staff_row["教員数"])

        meal_results = []
        rice_like_totals = []

        for meal in meal_types:
            rate_table = settings["rates"][meal]
            is_rice = meal in calc.RICE_MEAL_TYPES
            results, total_kg = calc.calc_meal(
                classes, staff_count, rate_table, extra_kg=extra_kg if is_rice else 0.0
            )
            raw_rice = water = None
            if is_rice:
                raw_rice = calc.calc_raw_rice_kg(total_kg)
                water = calc.calc_water_l(raw_rice, water_multiplier)
                rice_like_totals.append(total_kg)
            meal_results.append(
                {
                    "meal": meal,
                    "results": results,
                    "total": total_kg,
                    "raw_rice": raw_rice,
                    "water": water,
                }
            )

        soup_water = calc.calc_soup_water_l(rice_like_totals) if rice_like_totals else None

        st.session_state["calc_output"] = {
            "day_label": day_label,
            "meal_results": meal_results,
            "soup_water": soup_water,
        }

    output = st.session_state.get("calc_output")
    if output:
        for meal in output["meal_results"]:
            st.subheader(meal["meal"])
            result_df = pd.DataFrame(
                [{"クラス": k, "配缶量(kg)": v} for k, v in meal["results"].items()]
            )
            st.dataframe(result_df, hide_index=True, use_container_width=True)
            st.write(f"**合計: {meal['total']} kg**")
            if meal["raw_rice"] is not None:
                st.write(f"生米: **{meal['raw_rice']} kg** ／ 水: **{meal['water']} L**")

        if output["soup_water"] is not None:
            st.subheader("味噌汁の水")
            st.write(f"**{output['soup_water']} L**")

        xlsx_bytes = excel_export.build_print_workbook(
            output["day_label"], output["meal_results"], output["soup_water"]
        )
        st.download_button(
            "A4印刷用Excelをダウンロード（大きな文字）",
            data=xlsx_bytes,
            file_name=f"配缶量_{output['day_label']}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )


def page_settings():
    st.header("設定（年齢別一人当たり量など）")
    settings = store.load_settings()

    st.caption("各献立・年齢区分ごとの1人あたりの量（g）を設定してください。")
    for meal in store.MEAL_TYPES:
        st.subheader(meal)
        cols = st.columns(len(store.AGE_KEYS))
        for col, age_key in zip(cols, store.AGE_KEYS):
            with col:
                settings["rates"][meal][age_key] = st.number_input(
                    store.AGE_LABELS[age_key],
                    min_value=0,
                    value=int(settings["rates"][meal][age_key]),
                    step=5,
                    key=f"{meal}_{age_key}",
                )

    st.subheader("水の倍率のデフォルト値")
    settings["water_multiplier_default"] = st.number_input(
        "生米kg × この倍率 = 水L（計算画面で毎回変更可）",
        min_value=0.0,
        value=float(settings["water_multiplier_default"]),
        step=0.1,
    )

    if st.button("設定を保存", type="primary"):
        store.save_settings(settings)
        st.success("設定を保存しました。")


def main():
    st.sidebar.title("メニュー")
    page = st.sidebar.radio("ページを選択", ["計算", "設定"])
    if page == "計算":
        page_calc()
    else:
        page_settings()


if __name__ == "__main__":
    main()
