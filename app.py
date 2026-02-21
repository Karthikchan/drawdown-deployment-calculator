import streamlit as st
import pandas as pd
import numpy as np
import requests
import uuid

# -------------------------------------------------
# Page Setup
# -------------------------------------------------

st.set_page_config(page_title="Capital Deployment Engine", layout="wide")

# -------------------------------------------------
# Analytics
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
    payload = {
        "client_id": client_id,
        "events": [{"name": "page_view"}]
    }
    try:
        requests.post(url, json=payload, timeout=2)
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
st.write("Systematic allocation model with equity cap, crash replay and probabilistic projection.")

# -------------------------------------------------
# Sidebar Inputs
# -------------------------------------------------

st.sidebar.header("Portfolio Inputs")

total_portfolio = st.sidebar.number_input("Total Portfolio (₹)", 0.0, 1e12, 1000000.0)
current_equity = st.sidebar.number_input("Current Equity (₹)", 0.0, 1e12, 700000.0)
target_max_equity_pct = st.sidebar.slider("Max Equity Allocation (%)", 0, 100, 85)

drawdown_levels = st.sidebar.text_input("- Drawdown Levels (%)", "-5,-10,-15,-20,-30")
mode = st.sidebar.selectbox("Deployment Mode", ["Equal Allocation", "Progressively Aggressive"])

# Crash Replay
st.sidebar.markdown("---")
st.sidebar.header("Historical Crash Replay")

use_crash_replay = st.sidebar.checkbox("Replay Crash Path")
crash_type = st.sidebar.selectbox("Crash Type", ["2008-Style (Deep)", "2020-Style (Sharp)"])

# Monte Carlo
st.sidebar.markdown("---")
st.sidebar.header("Monte Carlo Projection")
use_monte_carlo = st.sidebar.checkbox("Run Monte Carlo")

if use_monte_carlo:
    simulations = st.sidebar.slider("Simulations", 500, 5000, 2000)
    exp_return = st.sidebar.slider("Expected Annual Return (%)", 5, 20, 12)
    volatility = st.sidebar.slider("Annual Volatility (%)", 5, 40, 18)
    years = st.sidebar.slider("Projection Years", 1, 15, 5)

# -------------------------------------------------
# Validation
# -------------------------------------------------

if total_portfolio == 0:
    st.stop()

try:
    raw = [x.strip() for x in drawdown_levels.split(",")]
    levels = sorted(list({abs(float(x)) for x in raw if x != ""}))
except:
    st.error("Invalid drawdown input")
    st.stop()

if len(levels) == 0:
    st.stop()

# -------------------------------------------------
# Capital Logic
# -------------------------------------------------

cash = total_portfolio - current_equity
max_equity = (target_max_equity_pct/100) * total_portfolio
max_deployable = max_equity - current_equity
deployable = min(cash, max(max_deployable, 0))

def generate_plan(mode):

    n = len(levels)

    weights = [1]*n if mode=="Equal Allocation" else list(range(1,n+1))
    total_weight = sum(weights)

    equity = current_equity
    deployed = 0
    rows=[]

    for i in range(n):

        planned = deployable * (weights[i]/total_weight)

        if deployed + planned > deployable:
            planned = deployable - deployed

        equity += planned
        deployed += planned

        rows.append({
            "Drawdown (%)": -levels[i],
            "Equity Value (₹)": equity
        })

    return pd.DataFrame(rows)

# -------------------------------------------------
# Deployment Output
# -------------------------------------------------

if deployable <= 0:
    st.warning("No deployable capital.")
else:

    df = generate_plan(mode)

    st.subheader("Deployment Path")
    st.dataframe(df, use_container_width=True)

    # Capital Allocation Curve
    st.line_chart(df.set_index("Drawdown (%)"))

# -------------------------------------------------
# Crash Replay Simulation
# -------------------------------------------------

if use_crash_replay and deployable > 0:

    st.subheader("Crash Replay Simulation")

    if crash_type.startswith("2008"):
        crash_depth = 55
        recovery_months = 36
    else:
        crash_depth = 35
        recovery_months = 12

    peak = df.iloc[0]["Equity Value (₹)"]
    crash_value = peak * (1 - crash_depth/100)

    monthly_recovery = (peak/crash_value)**(1/recovery_months) - 1

    values=[crash_value]
    for _ in range(recovery_months):
        values.append(values[-1]*(1+monthly_recovery))

    crash_df = pd.DataFrame({
        "Month": list(range(len(values))),
        "Portfolio Value": values
    }).set_index("Month")

    st.line_chart(crash_df)

    st.metric("Months to Recover Peak", recovery_months)

# -------------------------------------------------
# Monte Carlo
# -------------------------------------------------

if use_monte_carlo and deployable > 0:

    st.subheader("Monte Carlo Projection")

    start_value = df.iloc[-1]["Equity Value (₹)"]

    returns = np.random.normal(
        exp_return/100,
        volatility/100,
        (simulations, years)
    )

    growth = start_value * np.cumprod(1+returns, axis=1)
    final_vals = growth[:,-1]

    median = np.median(final_vals)
    p5 = np.percentile(final_vals,5)
    p95 = np.percentile(final_vals,95)

    col1,col2,col3 = st.columns(3)
    col1.metric("Median Final Value", f"₹{median:,.0f}")
    col2.metric("5th Percentile", f"₹{p5:,.0f}")
    col3.metric("95th Percentile", f"₹{p95:,.0f}")

    sharpe = (exp_return-5)/volatility if volatility!=0 else 0
    st.metric("Risk-Adjusted Score (Sharpe Proxy)", round(sharpe,2))

    st.line_chart(pd.DataFrame(growth.T))
