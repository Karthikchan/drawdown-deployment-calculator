import streamlit as st
import pandas as pd
import numpy as np
import requests
import uuid
from streamlit.errors import StreamlitSecretNotFoundError

# -------------------------------------------------
# Page Setup
# -------------------------------------------------

st.set_page_config(page_title="Drawdown Deployment Calculator", layout="wide")

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
    except Exception:
        pass


if GA_MEASUREMENT_ID and GA_API_SECRET and "ga_sent" not in st.session_state:
    send_ga_event()
    st.session_state.ga_sent = True

# -------------------------------------------------
# Styling
# -------------------------------------------------

st.markdown(
    """
    <style>
      .stApp { background: linear-gradient(180deg, #f8fafc 0%, #eef2ff 100%); }
      .block-container { padding-top: 1.4rem; }
      .nav-hint { color:#64748b; font-size:0.88rem; margin-top:-4px; margin-bottom:8px; }
      div[data-testid="column"] div[data-testid="stButton"] > button[kind="secondary"] {
        height: 140px !important;
        border-radius: 16px;
        border: 1px solid rgba(99, 102, 241, 0.28);
        background: linear-gradient(180deg, rgba(255,255,255,0.94), rgba(248,250,252,0.94));
        color: #0f172a;
        font-size: 1.06rem;
        font-weight: 700;
        box-shadow: 0 10px 22px rgba(15, 23, 42, 0.08);
        transition: all .2s ease;
        white-space: pre-wrap;
        line-height: 1.35;
        padding-top: 14px;
        padding-bottom: 14px;
      }
      div[data-testid="column"] div[data-testid="stButton"] > button[kind="secondary"]:hover {
        border-color: rgba(79, 70, 229, 0.55);
        transform: translateY(-1px);
      }
      .active-chip {
        display:inline-block; padding:6px 12px; border-radius:999px;
        background:#eef2ff; color:#3730a3; font-weight:600; font-size:0.84rem;
        border:1px solid rgba(79,70,229,.25); margin:8px 0 14px 0;
      }
    </style>
    """,
    unsafe_allow_html=True,
)

# -------------------------------------------------
# Title
# -------------------------------------------------

st.title("Drawdown Deployment Calculator")
st.write("An execution-first framework for disciplined drawdown investing.")

if "active_section" not in st.session_state:
    st.session_state.active_section = "Deployment Plan"

st.markdown('<div class="nav-hint">Tap a tile to jump directly to that section.</div>', unsafe_allow_html=True)

c1, c2, c3 = st.columns(3)
with c1:
    if st.button("① Entry Discipline\nBuild your deployment ladder", use_container_width=True):
        st.session_state.active_section = "Deployment Plan"
with c2:
    if st.button("② Equity Cap Risk Control\nTrack limits and deployable room", use_container_width=True):
        st.session_state.active_section = "Risk Diagnostics"
with c3:
    if st.button("③ Recovery Expectations\nReplay crash and recovery curves", use_container_width=True):
        st.session_state.active_section = "Crash Replay"

st.markdown(
    f'<div class="active-chip">Active Section: {st.session_state.active_section}</div>',
    unsafe_allow_html=True,
)

# -------------------------------------------------
# Sidebar Inputs
# -------------------------------------------------

st.sidebar.header("Portfolio Inputs")

total_portfolio = st.sidebar.number_input("Total Portfolio (₹)", 0.0, 1e12, 1000000.0)
current_equity = st.sidebar.number_input("Current Equity (₹)", 0.0, 1e12, 700000.0)
target_max_equity_pct = st.sidebar.slider("Max Equity Allocation (%)", 0, 100, 85)
drawdown_levels = st.sidebar.text_input("Drawdown Levels (%)", "-5,-10,-15,-20,-30")
deployment_mode = st.sidebar.selectbox(
    "Deployment Mode", ["Equal Allocation", "Progressively Aggressive"]
)

# -------------------------------------------------
# Validation
# -------------------------------------------------

if total_portfolio == 0:
    st.stop()

if current_equity > total_portfolio:
    st.error("Current equity cannot exceed total portfolio.")
    st.stop()

try:
    raw = [x.strip() for x in drawdown_levels.split(",")]
    levels = sorted(list({abs(float(x)) for x in raw if x != ""}))
except Exception:
    st.error("Invalid drawdown format. Example: -5,-10,-20")
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


def get_weights(mode, n):
    return [1] * n if mode == "Equal Allocation" else list(range(1, n + 1))


def generate_plan(mode):
    n = len(levels)
    weights = get_weights(mode, n)
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

        rows.append(
            {
                "Drawdown (%)": -levels[i],
                "Planned Tranche (₹)": round(planned, 2),
                "Equity Value (₹)": round(equity, 2),
                "Equity Allocation (%)": round((equity / total_portfolio) * 100, 2),
            }
        )

    return pd.DataFrame(rows)


def crash_equity_and_cash_at_bottom(mode, crash_drop, *legacy_args, **kwargs):
    """Compute portfolio equity/cash at crash bottom.

    Supports both signatures:
    - crash_equity_and_cash_at_bottom(mode, crash_drop)
    - crash_equity_and_cash_at_bottom(mode, crash_drop, initial_equity, deployable_capital, available_cash)
    """
    initial_equity = kwargs.get("initial_equity")
    deployable_capital = kwargs.get("deployable_capital")
    available_cash = kwargs.get("available_cash")

    # Backward compatibility for legacy positional callers.
    if len(legacy_args) > 0:
        initial_equity = legacy_args[0]
    if len(legacy_args) > 1:
        deployable_capital = legacy_args[1]
    if len(legacy_args) > 2:
        available_cash = legacy_args[2]

    initial_equity = current_equity if initial_equity is None else initial_equity
    deployable_capital = deployable if deployable_capital is None else deployable_capital
    available_cash = cash if available_cash is None else available_cash

    n = len(levels)
    weights = get_weights(mode, n)
    total_weight = sum(weights)

    crash_equity_value = initial_equity * (1 - crash_drop)
    cash_balance = available_cash

    for i in range(n):
        trigger_drop = levels[i] / 100

        if trigger_drop > crash_drop:
            continue

        planned = deployable_capital * (weights[i] / total_weight)
        planned = min(planned, cash_balance)

        if planned <= 0:
            continue

        tranche_to_bottom_factor = (1 - crash_drop) / (1 - trigger_drop)
        crash_equity_value += planned * tranche_to_bottom_factor
        cash_balance -= planned

    return crash_equity_value, cash_balance


df = generate_plan(deployment_mode) if deployable > 0 else None

# -------------------------------------------------
# Sections
# -------------------------------------------------

active_section = st.session_state.active_section

if active_section == "Deployment Plan":
    if deployable <= 0:
        st.warning("No deployable capital under current equity cap.")
    else:
        st.subheader("Deployment Plan")
        st.dataframe(df, width="stretch")
        st.subheader("Equity Allocation Curve")
        st.line_chart(df.set_index("Drawdown (%)")[["Equity Allocation (%)"]])

elif active_section == "Crash Replay":
    st.subheader("Crash Replay Comparison")

    crash_type = st.selectbox("Crash Scenario", ["2008-Style Crash", "2020-Style Crash"])

    if deployable > 0:
        if crash_type.startswith("2008"):
            pf_drop, n50_drop, n500_drop = 0.55, 0.50, 0.55
        else:
            pf_drop, n50_drop, n500_drop = 0.35, 0.38, 0.42

        pf_annual, n50_annual, n500_annual = 0.12, 0.13, 0.14
        pf_monthly = (1 + pf_annual) ** (1 / 12) - 1
        n50_monthly = (1 + n50_annual) ** (1 / 12) - 1
        n500_monthly = (1 + n500_annual) ** (1 / 12) - 1

        pre_crash_total = total_portfolio
        pf_equity, cash_before = crash_equity_and_cash_at_bottom(deployment_mode, pf_drop)
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
            pf_equity *= (1 + pf_monthly)
            pf_total = pf_equity + cash_before
            pf_path.append(pf_total)
            if pf_months == 0 and pf_total >= pre_crash_total:
                pf_months = month

            n50_value *= (1 + n50_monthly)
            n50_path.append(n50_value)
            if n50_months == 0 and n50_value >= pre_crash_total:
                n50_months = month

            n500_value *= (1 + n500_monthly)
            n500_path.append(n500_value)
            if n500_months == 0 and n500_value >= pre_crash_total:
                n500_months = month

        crash_df = pd.DataFrame({"Portfolio": pf_path, "NIFTY 50": n50_path, "NIFTY 500": n500_path})
        st.line_chart(crash_df)

        c1, c2, c3 = st.columns(3)
        c1.metric("Portfolio Recovery (Months)", pf_months)
        c2.metric("NIFTY 50 Recovery (Months)", n50_months)
        c3.metric("NIFTY 500 Recovery (Months)", n500_months)
    else:
        st.info("Crash Replay requires deployable capital under the selected equity cap.")

else:
    current_pct = (current_equity / total_portfolio) * 100

    a, b, c = st.columns(3)
    a.metric("Current Equity Allocation (%)", round(current_pct, 2))
    b.metric("Maximum Allocation Cap (%)", target_max_equity_pct)
    c.metric("Deployable Capital (₹)", f"{deployable:,.0f}")

    if current_pct > target_max_equity_pct:
        st.error("Current equity exceeds allocation cap.")
    else:
        st.success("Within allocation limits.")
