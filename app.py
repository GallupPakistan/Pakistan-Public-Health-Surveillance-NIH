import streamlit as st

st.set_page_config(
    page_title="Pakistan Public Health Surveillance",
    page_icon=":material/monitor_heart:",
    layout="wide",
)

try:
    overview = st.Page("views/overview.py", title="Overview", icon="🏠", default=True)
    geography = st.Page("views/geography.py", title="Geography", icon="📍")
    trends = st.Page("views/trends.py", title="Trends", icon="📈")
    outbreaks = st.Page("views/outbreaks.py", title="Outbreaks", icon="⚠️")
    forecast = st.Page("views/forecast.py", title="Forecast", icon="🔮")
    executive = st.Page("views/executive.py", title="Executive Analytics", icon="🎯")
    reporting = st.Page("views/reporting.py", title="Reporting", icon="📋")
    settings = st.Page("views/settings.py", title="Settings", icon="⚙️")
except AttributeError:
    st.error(
        "This app needs Streamlit 1.36+ for `st.navigation` / `st.Page`. "
        "Run `pip install -r requirements.txt` to install the pinned version, "
        "then restart the app."
    )
    st.stop()

pg = st.navigation(
    [overview, geography, trends, outbreaks, forecast, executive, reporting, settings]
)
pg.run()
