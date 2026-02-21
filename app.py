import streamlit as st
import pandas as pd
import numpy as np
import requests
import uuid
from streamlit.errors import StreamlitSecretNotFoundError

# -------------------------------------------------
# Page Setup
# -------------------------------------------------

st.set_page_config(
    page_title="Drawdown Deployment Calculator",
    layout="wide"
)

# -------------------------------------------------
# Lightweight Analytics
# -------------------------------------------------

try:
    GA_MEASUREMENT_ID = st.secrets.get("GA_MEASUREMENT_ID")
    GA_API_SECRET = st.secrets.get("GA_API_SECRET")
except StreamlitSecretNotFoundError:
    GA_MEASUREMENT_ID = None
    GA_API_SECRET = None

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

st.title("Drawdown Deployment Calculator")
st.write("Structured capital deployment with equity cap discipline.")
st.caption("Best viewed on desktop.")

# -------------------------------------------------
# Sidebar Inputs
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

monthly_contribution = st.sidebar.number_input(
    "Monthly Contribution (₹)", 0.0, 1e9, 0.0, step=1000.0
)

monthly_withdrawal = st.sidebar.number_input(
    "Monthly Withdrawal (₹)", 0.0, 1e9, 0.0, step=1000.0
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
            "Equity Value (₹)": round(equity, 2),
            "Equity Allocation (%)": round((equity/total_portfolio)*100, 2)
        })

    return pd.DataFrame(rows)

def crash_equity_and_cash_at_bottom(
    mode,
    crash_drop,
    initial_equity,
    deployable_capital,
    available_cash
):
    n = len(levels)
    weights = [1] * n if mode == "Equal Allocation" else list(range(1, n + 1))
    total_weight = sum(weights)

    crash_equity_value = initial_equity * (1 - crash_drop)
    cash_balance = available_cash

    for i in range(n):
        trigger_drop = levels[i] / 100

        # Deploy only if the crash actually reaches this drawdown level.
        if trigger_drop > crash_drop:
            continue

        planned = deployable_capital * (weights[i] / total_weight)
        planned = min(planned, cash_balance)

        if planned <= 0:
            continue

        # Tranche bought at trigger_drop and marked to crash bottom.
        tranche_to_bottom_factor = (1 - crash_drop) / (1 - trigger_drop)
        crash_equity_value += planned * tranche_to_bottom_factor
        cash_balance -= planned

    return crash_equity_value, cash_balance

df = generate_plan(deployment_mode) if deployable > 0 else None

# -------------------------------------------------
# Tabs
# -------------------------------------------------

tab1, tab2, tab3, tab4 = st.tabs([
    "Deployment Plan",
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

        st.subheader("Equity Allocation Curve")
        st.line_chart(df.set_index("Drawdown (%)")[["Equity Allocation (%)"]])

# -------------------------------------------------
# TAB 2 — Crash Replay with NIFTY Comparison
# -------------------------------------------------

# -------------------------------------------------
# TAB 2 — Dynamic Crash Replay with Index Comparison
# -------------------------------------------------

with tab2:

    st.subheader("Crash Replay Comparison")

    crash_type = st.selectbox(
        "Crash Scenario",
        ["2008-Style Crash", "2020-Style Crash", "Custom"]
    )

    if deployable > 0:

        # Crash depths and return assumptions
        if crash_type.startswith("2008"):
            pf_drop = 0.55
            n50_drop = 0.50
            n500_drop = 0.55
            pf_annual = 0.12
            n50_annual = 0.13
            n500_annual = 0.14
        elif crash_type.startswith("2020"):
            pf_drop = 0.35
            n50_drop = 0.38
            n500_drop = 0.42
            pf_annual = 0.12
            n50_annual = 0.13
            n500_annual = 0.14
        else:
            st.caption("Tune a custom crash and recovery profile.")
            pf_drop = st.slider("Portfolio Crash Depth (%)", 5, 70, 40) / 100
            n50_drop = st.slider("NIFTY 50 Crash Depth (%)", 5, 70, 38) / 100
            n500_drop = st.slider("NIFTY 500 Crash Depth (%)", 5, 70, 42) / 100
            pf_annual = st.slider("Portfolio Annual Recovery Return (%)", 1, 25, 12) / 100
            n50_annual = st.slider("NIFTY 50 Annual Recovery Return (%)", 1, 25, 13) / 100
            n500_annual = st.slider("NIFTY 500 Annual Recovery Return (%)", 1, 25, 14) / 100

        pf_monthly = (1 + pf_annual) ** (1/12) - 1
        n50_monthly = (1 + n50_annual) ** (1/12) - 1
        n500_monthly = (1 + n500_annual) ** (1/12) - 1
        net_monthly_flow = monthly_contribution - monthly_withdrawal

        pre_crash_total = total_portfolio

        # Portfolio value at crash bottom after staged deployments.
        pf_equity, cash_before = crash_equity_and_cash_at_bottom(
            deployment_mode,
            pf_drop,
            current_equity,
            deployable,
            cash
        )
        pf_total = pf_equity + cash_before

        n50_value = pre_crash_total * (1 - n50_drop)
        n500_value = pre_crash_total * (1 - n500_drop)

        pf_path = [pf_total]
        n50_path = [n50_value]
        n500_path = [n500_value]

        pf_months = 0
        n50_months = 0
        n500_months = 0

        for month in range(1, 181):

            # Portfolio recovery (equity grows, then net cashflow is invested/withdrawn)
            pf_equity *= (1 + pf_monthly)
            pf_equity = max(pf_equity + net_monthly_flow, 0)
            pf_total = pf_equity + cash_before
            pf_path.append(pf_total)

            if pf_months == 0 and pf_total >= pre_crash_total:
                pf_months = month

            # NIFTY 50 recovery (benchmark remains contribution-neutral)
            n50_value *= (1 + n50_monthly)
            n50_path.append(n50_value)

            if n50_months == 0 and n50_value >= pre_crash_total:
                n50_months = month

            # NIFTY 500 recovery (benchmark remains contribution-neutral)
            n500_value *= (1 + n500_monthly)
            n500_path.append(n500_value)

            if n500_months == 0 and n500_value >= pre_crash_total:
                n500_months = month

        crash_df = pd.DataFrame({
            "Portfolio": pf_path,
            "NIFTY 50": n50_path,
            "NIFTY 500": n500_path
        })

        st.line_chart(crash_df)

        col1, col2, col3 = st.columns(3)
        col1.metric("Portfolio Recovery (Months)", pf_months)
        col2.metric("NIFTY 50 Recovery (Months)", n50_months)
        col3.metric("NIFTY 500 Recovery (Months)", n500_months)

        flow_label = f"₹{net_monthly_flow:,.0f}"
        st.caption(f"Monthly net cashflow applied to Portfolio path only: {flow_label}")
# -------------------------------------------------
# TAB 3 — Monte Carlo (Optimized)
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

    run_mc = st.checkbox("Enable Monte Carlo Simulation")

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

            final_vals = growth[:, -1]

            col1, col2, col3 = st.columns(3)
            col1.metric("Median Final Value", f"₹{np.median(final_vals):,.0f}")
            col2.metric("5th Percentile", f"₹{np.percentile(final_vals,5):,.0f}")
            col3.metric("95th Percentile", f"₹{np.percentile(final_vals,95):,.0f}")

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
        st.error("Current equity exceeds allocation cap.")
    else:
        st.success("Within allocation limits.")
