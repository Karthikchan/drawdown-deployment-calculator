import streamlit as st
import streamlit.components.v1 as components
import pandas as pd

# -------------------------------------------------
# Page Configuration
# -------------------------------------------------

st.set_page_config(
    page_title="Drawdown Deployment Calculator",
    layout="wide"
)

# -------------------------------------------------
# Google Analytics (GA4)
# Replace with your Measurement ID
# -------------------------------------------------

GA_MEASUREMENT_ID = "G-2NC6JTLL3R"

components.html(f"""
<!-- Google tag (gtag.js) -->
<script async src="https://www.googletagmanager.com/gtag/js?id={GA_MEASUREMENT_ID}"></script>
<script>
window.dataLayer = window.dataLayer || [];
function gtag(){{dataLayer.push(arguments);}}
gtag('js', new Date());
gtag('config', '{GA_MEASUREMENT_ID}');
</script>
""", height=0)

# -------------------------------------------------
# App Title
# -------------------------------------------------

st.title("Drawdown Deployment Calculator")
st.write("Structured capital deployment framework for disciplined equity investing.")

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

# -------------------------------------------------
# Core Calculations
# -------------------------------------------------

# Cash available for deployment
cash_available = total_portfolio - current_equity

# Maximum equity allowed based on user cap
max_equity_value_allowed = (target_max_equity_pct / 100) * total_portfolio

# Maximum deployable capital without breaching cap
max_deployable = max_equity_value_allowed - current_equity

# Parse drawdown levels
levels = [float(x.strip()) for x in drawdown_levels.split(",") if x.strip() != ""]
num_stages = len(levels)

# -------------------------------------------------
# Validation
# -------------------------------------------------

if cash_available <= 0:
    st.warning("No cash available for deployment.")

elif num_stages == 0:
    st.warning("Please enter valid drawdown levels.")

else:
    # Ensure deployment does not exceed cap
    deployable_cash = min(cash_available, max_deployable)

    if deployable_cash <= 0:
        st.warning("Already at or above target equity allocation.")

    else:
        # Determine weighting logic
        if weighting_mode == "Equal Allocation":
            weights = [1] * num_stages
        else:
            # More weight to deeper drawdowns
            weights = list(range(1, num_stages + 1))

        total_weight = sum(weights)

        deployment_plan = []
        remaining_cash = cash_available
        equity_value = current_equity
        deployed_so_far = 0

        # -------------------------------------------------
        # Deployment Loop
        # -------------------------------------------------

        for i in range(num_stages):

            # Planned allocation based on weight
            planned_deploy = deployable_cash * (weights[i] / total_weight)

            # Prevent overshooting max deployable amount
            if deployed_so_far + planned_deploy > deployable_cash:
                planned_deploy = deployable_cash - deployed_so_far

            deploy_amount = max(planned_deploy, 0)

            # Update portfolio state
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

        # -------------------------------------------------
        # Output Section
        # -------------------------------------------------

        st.subheader("Deployment Plan")
        st.dataframe(df, use_container_width=True)

        st.subheader("Summary")

        st.write(f"Cash Available: ₹{cash_available:,.2f}")
        st.write(f"Max Deployable (Capped): ₹{deployable_cash:,.2f}")
        st.write(
            f"Final Equity Allocation if Fully Deployed: "
            f"{df.iloc[-1]['Equity Allocation (%)']}%"
        )

        st.success("Deployment capped at target maximum equity allocation.")
