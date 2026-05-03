import datetime as dt
import joblib
from pathlib import Path
import pandas as pd
import re
import streamlit as st


@st.cache_data
def load_counters():
    path = (
        Path(__file__).resolve().parent.parent.parent
        / "data"
        / "processed"
        / "counters.parquet"
    )
    df_counters = pd.read_parquet(path)

    counters = df_counters["Nom du compteur"]

    return counters


@st.cache_data
def load_typicals():
    base = Path(__file__).resolve().parent.parent.parent / "data" / "processed"
    df1 = pd.read_parquet(base / "typical_counter_weekday_hour.parquet")
    df2 = pd.read_parquet(base / "typical_counter_hour.parquet")

    return df1, df2


df_counter_weekday_hour, df_counter_hour = load_typicals()


def typical_count(counter, weekday, hour):
    row = df_counter_weekday_hour[
        (df_counter_weekday_hour["Nom du compteur"] == counter)
        & (df_counter_weekday_hour["Jour de la semaine"] == weekday)
        & (df_counter_weekday_hour["Heure"] == hour)
    ]
    if not row.empty:
        return float(row.iloc[0]["typical_count"])

    row2 = df_counter_hour[
        (df_counter_hour["Nom du compteur"] == counter)
        & (df_counter_hour["Heure"] == hour)
    ]
    if not row2.empty:
        return float(row2.iloc[0]["typical_count_hour"])

    return float(df_counter_hour["typical_count_hour"].mean())


@st.cache_resource
def load_models():
    base = Path(__file__).resolve().parent.parent.parent / "models"
    return {
        "1 - Linear Regression": joblib.load(base / "model_lr.joblib"),
        "2 - Random Forest": joblib.load(base / "model_rf.joblib"),
        "3 - LightGBM": joblib.load(base / "model_lgbm.joblib"),
        "4 - XGBoost": joblib.load(base / "model_xgb.joblib"),
    }


def tab_demo():
    st.title("Démo")

    counters = load_counters()

    counter = st.selectbox("Compteur", counters)

    pattern = r"(Bike IN|Bike OUT|E-O|O-E|N-S|S-N|NE-SO|SO-NE|NO-SE|SE-NO)"
    match = re.search(pattern, counter)
    if match:
        direction = match.group(1)
    else:
        direction = "N/A"

    col1, col2 = st.columns(2)

    with col1:
        datetime_choice = st.datetime_input(
            label="Date et heure",
            value=dt.datetime(2024, 5, 1, 15, 0),
            min_value=dt.datetime(2024, 5, 1, 15, 0),
            step=dt.timedelta(hours=1),
        )

        year = datetime_choice.year
        month = datetime_choice.month
        day_of_month = datetime_choice.day
        hour = datetime_choice.hour
        weekday = datetime_choice.weekday()
        weekend = int(weekday >= 5)

    with col2:
        holiday = st.segmented_control(
            label="Jour de vacances",
            options=["non", "oui"],
            selection_mode="single",
            default="non",
        )
        if holiday == "non":
            holiday = 0
        else:
            holiday = 1

    lag_1h_auto = typical_count(counter, weekday, (hour - 1) % 24)
    lag_24h_auto = typical_count(counter, (weekday - 1) % 7, hour)
    lag_168h_auto = typical_count(counter, weekday, hour)

    roll_mean_3h_auto = (
        typical_count(counter, weekday, (hour - 1) % 24)
        + typical_count(counter, weekday, (hour - 2) % 24)
        + typical_count(counter, weekday, (hour - 3) % 24)
    ) / 3

    auto_lags = st.toggle("Estimer automatiquement les variables de retard", value=True)

    if auto_lags:
        lag_1h = lag_1h_auto
        lag_24h = lag_24h_auto
        lag_168h = lag_168h_auto
        roll_mean_3h = roll_mean_3h_auto
    else:
        with st.expander(
            "Modifier manuellement les variables de retards", expanded=True
        ):
            lag_1h = st.number_input(
                "lag 1h", value=float(lag_1h_auto), step=1.0, format="%.0f"
            )
            lag_24h = st.number_input(
                "lag 24h", value=float(lag_24h_auto), step=1.0, format="%.0f"
            )
            lag_168h = st.number_input(
                "lag 168h", value=float(lag_168h_auto), step=1.0, format="%.0f"
            )
            roll_mean_3h = st.number_input(
                "Moyenne glissante sur 3 heures",
                value=float(roll_mean_3h_auto),
                step=0.1,
                format="%.1f",
            )

    col1, col2 = st.columns(2)

    with col1:
        temperature = st.slider("Température (°C)", -10.0, 45.0, 0.0, 0.1)

    with col2:
        precipitation = st.slider(
            "Précipitations - pluie et neige (mm)", 0.0, 100.0, 0.0, 0.1
        )

    model_features = [
        "Année",
        "Mois",
        "Jour du mois",
        "Heure",
        "Jour de la semaine",
        "Week-end",
        "Vacances",
        "lag_1h",
        "lag_24h",
        "lag_168h",
        "roll_mean_3h",
        "Température (°C)",
        "Précipitations (mm)",
        "Nom du compteur",
        "Direction",
    ]

    X_test = pd.DataFrame(
        [
            {
                "Année": year,  # 2025
                "Mois": month,  # 2
                "Jour du mois": day_of_month,  # 12
                "Heure": hour,  # 18
                "Jour de la semaine": weekday,  # 2
                "Week-end": weekend,  # 0
                "Vacances": holiday,  # 0
                "lag_1h": lag_1h,  # 104.0
                "lag_24h": lag_24h,  # 208.0
                "lag_168h": lag_168h,  # 180.0
                "roll_mean_3h": roll_mean_3h,
                "Température (°C)": temperature,  # 5.2
                "Précipitations (mm)": precipitation,  # 0.0
                "Nom du compteur": counter,  # "77 boulevard Masséna SO-NE"
                "Direction": direction,  # "SO-NE"
            }
        ]
    )[model_features]

    models = load_models()

    preds = []
    for name, model in models.items():
        yhat = round(model.predict(X_test)[0], 0)
        preds.append({"Modèle": name, "Prédiction": yhat})

    order = [
        "1 - Linear Regression",
        "2 - Random Forest",
        "3 - LightGBM",
        "4 - XGBoost",
    ]
    df_preds = pd.DataFrame(preds).set_index("Modèle").loc[order]

    st.bar_chart(
        data=df_preds["Prédiction"],
        horizontal=True,
        x_label="Prédiction du comptage horaire",
        # width = 'content'
    )

    st.dataframe(df_preds)
