import streamlit as st
import pandas as pd
import numpy as np
import requests
import uuid

# -------------------------------------------------
# Page Setup
# -------------------------------------------------

st.set_page_config(
    page_title="Capital Deployment Engine",
    layout="wide"
)

# -------------------------------------------------
# Analytics (Lightweight)
# -------------------------------------------------

GA_MEASUREMENT_ID = st.secrets.get("GA_MEASUREMENT_ID")
GA_API_SECRET = st.secrets.get("GA_API_SECRET")

def send_ga_event():
    client_id = str(uuid.uuid4())
    url = (
        f"https://www.google-analytics.com/mp/collect"
        f"?measurement_id={GA_MEASUREMENT_ID}"
        f"&api_secret={GA_API_SECRET}"
    )
    payload = {"client_id": client_id, "events": [{"name": "page_view"}]}
    try:
        requests.post(url, json=payload, timeout=1)
    except:
        pass

if GA_MEASUREMENT_ID and GA_API_SECRET:
    if "ga_sent" not in st.session_state:
        send_ga_event()
        st.session_state.ga_sent = True

# -------------------------------------------------
# Title
# -------------------------------------------------

st.title("Capital Deployment Engine")
st.write("Structured allocation, crash replay and probabilistic modeling.")

# -------------------------------------------------
# Sidebar Inputs (Global)
# -------------------------------------------------

st.sidebar.header("Portfolio Inputs")

total_portfolio = st.sidebar.number_input(
    "Total Portfolio (₹)", 0.0, 1e12, 1000000.0
)

current_equity = st.sidebar.number_input(
    "Current Equity (₹)", 0.0, 1e12, 700000.0
)

target_max_equity_pct = st.sidebar.slider(
    "Max Equity Allocation (%)", 0, 100, 85
)

drawdown_levels = st.sidebar.text_input(
    "Drawdown Levels (%)", "-5,-10,-15,-20,-30"
)

deployment_mode = st.sidebar.selectbox(
    "Deployment Mode",
    ["Equal Allocation", "Progressively Aggressive"]
)

# -------------------------------------------------
# Validation
# -------------------------------------------------

if total_portfolio == 0:
    st.stop()

try:
    raw = [x.strip() for x in drawdown_levels.split(",")]
    levels = sorted(list({abs(float(x)) for x in raw if x != ""}))
except:
    st.error("Invalid drawdown format.")
    st.stop()

if len(levels) == 0:
    st.stop()

# -------------------------------------------------
# Capital Logic
# -------------------------------------------------

cash = total_portfolio - current_equity
max_equity = (target_max_equity_pct / 100) * total_portfolio
max_deployable = max_equity - current_equity
deployable = min(cash, max(max_deployable, 0))

def generate_plan(mode):
    n = len(levels)
    weights = [1]*n if mode == "Equal Allocation" else list(range(1,n+1))
    total_weight = sum(weights)

    equity = current_equity
    deployed = 0
    rows = []

    for i in range(n):
        planned = deployable * (weights[i] / total_weight)

        if deployed + planned > deployable:
            planned = deployable - deployed

        equity += planned
        deployed += planned

        rows.append({
            "Drawdown (%)": -levels[i],
            "Equity Value (₹)": equity,
            "Equity Allocation (%)": (equity/total_portfolio)*100
        })

    return pd.DataFrame(rows)

df = generate_plan(deployment_mode) if deployable > 0 else None

# -------------------------------------------------
# Tabs
# -------------------------------------------------

tab1, tab2, tab3, tab4 = st.tabs([
    "Deployment Engine",
    "Crash Replay",
    "Monte Carlo",
    "Risk Diagnostics"
])

# -------------------------------------------------
# TAB 1
# -------------------------------------------------

with tab1:

    if deployable <= 0:
        st.warning("No deployable capital.")
    else:
        st.subheader("Deployment Plan")
        st.dataframe(df, use_container_width=True)

        st.subheader("Allocation Curve")
        st.line_chart(df.set_index("Drawdown (%)")[["Equity Allocation (%)"]])

# -------------------------------------------------
# TAB 2
# -------------------------------------------------

with tab2:

    crash_type = st.selectbox("Crash Type", [
        "2008-Style (Deep, Slow Recovery)",
        "2020-Style (Sharp, Fast Recovery)"
    ])

    if deployable > 0:

        if crash_type.startswith("2008"):
            crash_depth = 55
            recovery_months = 36
        else:
            crash_depth = 35
            recovery_months = 12

        peak = df.iloc[-1]["Equity Value (₹)"]
        crash_value = peak * (1 - crash_depth/100)

        monthly_recovery = (peak/crash_value)**(1/recovery_months) - 1

        values=[crash_value]
        for _ in range(recovery_months):
            values.append(values[-1]*(1+monthly_recovery))

        crash_df = pd.DataFrame({
            "Portfolio Value": values
        })

        st.line_chart(crash_df)
        st.metric("Months to Recover Peak", recovery_months)

# -------------------------------------------------
# TAB 3 – Optimized Monte Carlo
# -------------------------------------------------

@st.cache_data(show_spinner=False)
def run_monte_carlo(start_value, simulations, years, exp_return, volatility):
    returns = np.random.normal(
        exp_return/100,
        volatility/100,
        (simulations, years)
    )
    growth = start_value * np.cumprod(1+returns, axis=1)
    return growth

with tab3:

    run_mc = st.checkbox("Enable Monte Carlo")

    if run_mc and deployable > 0:

        simulations = st.slider("Simulations", 500, 5000, 1000)
        exp_return = st.slider("Expected Return (%)", 5, 20, 12)
        volatility = st.slider("Volatility (%)", 5, 40, 18)
        years = st.slider("Projection Years", 1, 15, 5)

        if st.button("Run Simulation"):

            start_value = df.iloc[-1]["Equity Value (₹)"]

            growth = run_monte_carlo(
                start_value,
                simulations,
                years,
                exp_return,
                volatility
            )

            final_vals = growth[:,-1]

            col1, col2, col3 = st.columns(3)
            col1.metric("Median Final", f"₹{np.median(final_vals):,.0f}")
            col2.metric("5th Percentile", f"₹{np.percentile(final_vals,5):,.0f}")
            col3.metric("95th Percentile", f"₹{np.percentile(final_vals,95):,.0f}")

            # Plot only percentile paths
            median_path = np.median(growth, axis=0)
            p5_path = np.percentile(growth, 5, axis=0)
            p95_path = np.percentile(growth, 95, axis=0)

            mc_plot = pd.DataFrame({
                "Median": median_path,
                "5th %ile": p5_path,
                "95th %ile": p95_path
            })

            st.line_chart(mc_plot)

# -------------------------------------------------
# TAB 4
# -------------------------------------------------

with tab4:

    current_pct = (current_equity/total_portfolio)*100

    st.metric("Current Equity Allocation (%)", round(current_pct,2))
    st.metric("Maximum Allocation Cap (%)", target_max_equity_pct)
    st.metric("Deployable Capital (₹)", f"{deployable:,.0f}")

    if current_pct > target_max_equity_pct:
        st.error("Above target allocation cap.")
    else:
        st.success("Within allocation limits.")
