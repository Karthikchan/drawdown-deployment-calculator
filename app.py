import streamlit as st
import pandas as pd

st.set_page_config(page_title="Drawdown Deployment Calculator", layout="wide")

st.title("Drawdown Deployment Calculator")
st.write("Structured capital deployment framework for disciplined equity investing.")

# ---------------------------
# Inputs
# ---------------------------

st.sidebar.header("Portfolio Inputs")

total_portfolio = st.sidebar.number_input(
    "Total Portfolio Value (₹)", min_value=0.0, value=1000000.0, step=10000.0
)

current_equity = st.sidebar.number_input(
    "Current Equity Value (₹)", min_value=0.0, value=700000.0, step=10000.0
)

target_max_equity_pct = st.sidebar.slider(
    "Target Maximum Equity Allocation (%)", 0, 100, 85
)

drawdown_levels = st.sidebar.text_input(
    "Drawdown Levels (%) - comma separated",
    "-5,-10,-15,-20,-30"
)

weighting_mode = st.sidebar.selectbox(
    "Deployment Mode",
    ["Equal Allocation", "Progressively Aggressive"]
)

# ---------------------------
# Processing
# ---------------------------

cash_available = total_portfolio - current_equity
max_equity_value_allowed = (target_max_equity_pct / 100) * total_portfolio
max_deployable = max_equity_value_allowed - current_equity

levels = [float(x.strip()) for x in drawdown_levels.split(",")]
num_stages = len(levels)

if cash_available <= 0:
    st.warning("No cash available for deployment.")
else:

    # Cap deployment to both cash available AND max equity limit
    deployable_cash = min(cash_available, max_deployable)

    if deployable_cash <= 0:
        st.warning("Already at or above target equity allocation.")
    else:

        if weighting_mode == "Equal Allocation":
            weights = [1] * num_stages
        else:
            weights = list(range(1, num_stages + 1))

        total_weight = sum(weights)

        deployment_plan = []
        remaining_cash = cash_available
        equity_value = current_equity
        deployed_so_far = 0

        for i in range(num_stages):

            planned_deploy = deployable_cash * (weights[i] / total_weight)

            # Prevent overshooting max equity
            if deployed_so_far + planned_deploy > deployable_cash:
                planned_deploy = deployable_cash - deployed_so_far

            if planned_deploy <= 0:
                deploy_amount = 0
            else:
                deploy_amount = planned_deploy

            equity_value += deploy_amount
            remaining_cash -= deploy_amount
            deployed_so_far += deploy_amount

            equity_pct = (equity_value / total_portfolio) * 100

            deployment_plan.append({
                "Drawdown Level (%)": levels[i],
                "Deploy Amount (₹)": round(deploy_amount, 2),
                "Equity After Deployment (₹)": round(equity_value, 2),
                "Remaining Cash (₹)": round(remaining_cash, 2),
                "Equity Allocation (%)": round(equity_pct, 2)
            })

        df = pd.DataFrame(deployment_plan)

        st.subheader("Deployment Plan")
        st.dataframe(df, use_container_width=True)

        st.subheader("Summary")

        st.write(f"Cash Available: ₹{cash_available:,.2f}")
        st.write(f"Max Deployable (Capped): ₹{deployable_cash:,.2f}")
        st.write(f"Final Equity Allocation if Fully Deployed: {df.iloc[-1]['Equity Allocation (%)']}%")

        st.success("Deployment capped at target maximum equity allocation.")

    # ---------------------------
    # Output
    # ---------------------------

    st.subheader("Deployment Plan")
    st.dataframe(df, use_container_width=True)

    st.subheader("Summary")

    st.write(f"Cash Available: ₹{cash_available:,.2f}")
    st.write(f"Final Equity Allocation if Fully Deployed: {df.iloc[-1]['Equity Allocation (%)']}%")

    if df.iloc[-1]["Equity Allocation (%)"] > target_max_equity_pct:
        st.error("Warning: Final allocation exceeds target maximum equity allocation.")
    else:
        st.success("Final allocation remains within target band.")
