import streamlit as st
import pandas as pd
import requests
import uuid
import matplotlib.pyplot as plt

# -------------------------------------------------
# Page Configuration
# -------------------------------------------------

st.set_page_config(
    page_title="Drawdown Deployment Calculator",
    layout="wide"
)

# -------------------------------------------------
# Server-Side Google Analytics Tracking
# -------------------------------------------------

GA_MEASUREMENT_ID = st.secrets.get("GA_MEASUREMENT_ID")
GA_API_SECRET = st.secrets.get("GA_API_SECRET")

def send_ga_event():
    client_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())

    url = (
        f"https://www.google-analytics.com/mp/collect"
        f"?measurement_id={GA_MEASUREMENT_ID}"
        f"&api_secret={GA_API_SECRET}"
    )

    payload = {
        "client_id": client_id,
        "events": [
            {"name": "session_start", "params": {"session_id": session_id}},
            {
                "name": "page_view",
                "params": {"session_id": session_id, "engagement_time_msec": 100}
            }
        ]
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

st.title("Drawdown Deployment Calculator")
st.write("Rule-based capital deployment engine with equity cap discipline.")

# -------------------------------------------------
# Sidebar Inputs
# -------------------------------------------------

st.sidebar.header("Portfolio Inputs")

total_portfolio = st.sidebar.number_input(
    "Total Portfolio Value (₹)",
    min_value=0.0,
    value=1000000.0,
    step=10000.0
)

current_equity = st.sidebar.number_input(
    "Current Equity Value (₹)",
    min_value=0.0,
    value=700000.0,
    step=10000.0
)

target_max_equity_pct = st.sidebar.slider(
    "Target Maximum Equity Allocation (%)",
    min_value=0,
    max_value=100,
    value=85
)

drawdown_levels = st.sidebar.text_input(
    "Drawdown Levels (%) - comma separated",
    "-5,-10,-15,-20,-30"
)

weighting_mode = st.sidebar.selectbox(
    "Deployment Mode",
    ["Equal Allocation", "Progressively Aggressive"]
)

compare_mode = st.sidebar.checkbox("Compare Both Modes")

# -------------------------------------------------
# Risk Diagnostics
# -------------------------------------------------

st.sidebar.markdown("---")
st.sidebar.header("Risk Diagnostics")

if total_portfolio == 0:
    st.error("Total portfolio cannot be zero.")
    st.stop()

current_equity_pct = (current_equity / total_portfolio) * 100
st.sidebar.write(f"Current Equity Allocation: {current_equity_pct:.2f}%")

if current_equity_pct > target_max_equity_pct:
    st.sidebar.error("Already above target max allocation.")

# -------------------------------------------------
# Parse Drawdowns Safely
# -------------------------------------------------

try:
    raw_levels = [x.strip() for x in drawdown_levels.split(",")]
    levels = sorted(
        list({abs(float(x)) for x in raw_levels if x != ""})
    )
except:
    st.error("Invalid drawdown format. Use comma-separated values like -5,-10,-15")
    st.stop()

if len(levels) == 0:
    st.warning("Please enter valid drawdown levels.")
    st.stop()

# -------------------------------------------------
# Core Capital Calculations
# -------------------------------------------------

cash_available = total_portfolio - current_equity
max_equity_value_allowed = (target_max_equity_pct / 100) * total_portfolio
max_deployable = max_equity_value_allowed - current_equity
deployable_cash = min(cash_available, max(max_deployable, 0))


# -------------------------------------------------
# Deployment Function
# -------------------------------------------------

def generate_plan(mode):
    num_stages = len(levels)

    if mode == "Equal Allocation":
        weights = [1] * num_stages
    else:
        weights = list(range(1, num_stages + 1))

    total_weight = sum(weights)

    equity_value = current_equity
    remaining_cash = cash_available
    deployed_so_far = 0

    rows = []

    for i in range(num_stages):
        planned = deployable_cash * (weights[i] / total_weight)

        if deployed_so_far + planned > deployable_cash:
            planned = deployable_cash - deployed_so_far

        deploy_amount = max(planned, 0)

        equity_value += deploy_amount
        remaining_cash -= deploy_amount
        deployed_so_far += deploy_amount

        equity_pct = (equity_value / total_portfolio) * 100

        rows.append({
            "Drawdown Level (%)": -levels[i],
            "Deploy Amount (₹)": round(deploy_amount, 2),
            "Equity After Deployment (₹)": round(equity_value, 2),
            "Remaining Cash (₹)": round(remaining_cash, 2),
            "Equity Allocation (%)": round(equity_pct, 2)
        })

    return pd.DataFrame(rows)


# -------------------------------------------------
# Execution
# -------------------------------------------------

if cash_available <= 0:
    st.warning("No cash available for deployment.")
elif deployable_cash <= 0:
    st.warning("Deployment capped. Already at target allocation.")
else:

    st.subheader("Deployment Plan")

    if compare_mode:

        df_equal = generate_plan("Equal Allocation")
        df_aggressive = generate_plan("Progressively Aggressive")

        col1, col2 = st.columns(2)

        with col1:
            st.write("Equal Allocation")
            st.dataframe(df_equal, use_container_width=True)

        with col2:
            st.write("Progressively Aggressive")
            st.dataframe(df_aggressive, use_container_width=True)

        # Plot Comparison
        st.subheader("Equity Allocation Comparison")

        fig, ax = plt.subplots()

        ax.plot(
            df_equal["Drawdown Level (%)"],
            df_equal["Equity Allocation (%)"],
            marker='o',
            label="Equal"
        )

        ax.plot(
            df_aggressive["Drawdown Level (%)"],
            df_aggressive["Equity Allocation (%)"],
            marker='o',
            label="Aggressive"
        )

        ax.set_xlabel("Market Drawdown (%)")
        ax.set_ylabel("Equity Allocation (%)")
        ax.grid(True)
        ax.legend()

        st.pyplot(fig)

    else:

        df = generate_plan(weighting_mode)

        st.dataframe(df, use_container_width=True)

        # Allocation Curve
        st.subheader("Equity Allocation Path")

        fig, ax = plt.subplots()

        ax.plot(
            df["Drawdown Level (%)"],
            df["Equity Allocation (%)"],
            marker='o'
        )

        ax.set_xlabel("Market Drawdown (%)")
        ax.set_ylabel("Equity Allocation (%)")
        ax.grid(True)

        st.pyplot(fig)

        # Professional Summary Metrics
        st.subheader("Capital Summary")

        col1, col2 = st.columns(2)

        with col1:
            st.metric("Cash Available", f"₹{cash_available:,.0f}")
            st.metric("Max Deployable", f"₹{deployable_cash:,.0f}")

        with col2:
            final_pct = df.iloc[-1]["Equity Allocation (%)"]
            st.metric("Final Equity Allocation", f"{final_pct}%")

        if deployable_cash < cash_available:
            st.info("Deployment capped at target maximum equity allocation.")

        st.success("Rule-based deployment plan generated successfully.")
