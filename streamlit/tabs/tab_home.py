from pathlib import Path
import pandas as pd
import plotly.express as px
import streamlit as st


@st.cache_data
def load_sites():
    path = (
        Path(__file__).resolve().parent.parent.parent
        / "data"
        / "processed"
        / "sites_agg.parquet"
    )
    return pd.read_parquet(path)


def tab_home():
    st.title("Trafic cycliste à Paris")

    df_sites = load_sites()

    fig = px.scatter_map(
        df_sites,
        lat="lat",
        lon="lon",
        size="avg_hourly_count",
        hover_name="site",
        hover_data={
            "avg_hourly_count": ":.0f",
            "n_hours": True,
            "lat": False,
            "lon": False,
        },
        zoom=11,
        height=650,
    )

    st.plotly_chart(fig, use_container_width=True)

    st.write(f"Nombre de sites : **{len(df_sites)}**")
    st.caption("Taille des cercles : moyenne horaire des passages")
