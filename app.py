import streamlit as st
import pandas as pd
import time
import os
from automation import LeadAutomation

st.set_page_config(page_title="LeadGen Pro Enterprise", layout="wide")

st.markdown("""
<style>
.stApp { background-color: #0b0d11; color: #ffffff; }
div[data-testid="stMetric"] {
    background-color: #161b22;
    border: 1px solid #30363d;
    padding: 15px;
    border-radius: 10px;
}
div[data-testid="stMetricValue"] {
    color: #58a6ff;
    font-size: 1.8rem !important;
}
.stProgress > div > div > div > div {
    background-image: linear-gradient(to right, #1f6feb , #58a6ff);
}
section[data-testid="stSidebar"] {
    background-color: #0d1117;
}
</style>
""", unsafe_allow_html=True)

# ---------------- SESSION STATE ----------------
if "running" not in st.session_state: st.session_state.running = False
if "logs" not in st.session_state: st.session_state.logs = []
if "stats" not in st.session_state: st.session_state.stats = {"success": 0, "fail": 0, "total": 0}
if "csv_signature" not in st.session_state: st.session_state.csv_signature = None
if "checkpoint_loaded" not in st.session_state: st.session_state.checkpoint_loaded = False
if "_lock" not in st.session_state: st.session_state._lock = False  # 🔒 rerun lock

# ---------------- LOG ----------------
def add_log(msg, type="info"):
    icon = "✅" if type == "success" else "❌" if type == "error" else "⚠️"
    st.session_state.logs.insert(0, f"{icon} {msg}")
    st.session_state.logs = st.session_state.logs[:200]

# ---------------- UI ----------------
st.title("🚀 LeadGen | Automation")

with st.sidebar:
    is_headless = st.checkbox("Run in Background (Headless)", value=True)
    if st.button("🗑️ Reset All Progress"):
        if os.path.exists("checkpoint.json"):
            os.remove("checkpoint.json")
        st.session_state.stats = {"success": 0, "fail": 0, "total": 0}
        st.session_state.logs = []
        st.session_state.running = False
        st.session_state.checkpoint_loaded = False
        st.session_state._lock = False
        st.rerun()

with st.container(border=True):
    col1, col2 = st.columns([2, 1])
    target_url = col1.text_input("Website URL", value="https://admission.gibsbschool.com/")
    uploaded_file = col2.file_uploader("Upload Lead CSV", type="csv")

# ---------------- CSV CHANGE ----------------
if uploaded_file:
    sig = f"{uploaded_file.name}_{uploaded_file.size}"
    if st.session_state.csv_signature != sig:
        st.session_state.csv_signature = sig
        st.session_state.stats = {"success": 0, "fail": 0, "total": 0}
        st.session_state.logs = []
        st.session_state.checkpoint_loaded = False
        if os.path.exists("checkpoint.json"):
            os.remove("checkpoint.json")

# ---------------- KPI PLACEHOLDERS ----------------
k1, k2, k3, k4 = st.columns(4)

total_kpi = k1.empty()
success_kpi = k2.empty()
fail_kpi = k3.empty()
remaining_kpi = k4.empty()

def render_kpis():
    total_kpi.metric("Target Total", st.session_state.stats["total"])
    success_kpi.metric("Delivered ✅", st.session_state.stats["success"])
    fail_kpi.metric("Failed ❌", st.session_state.stats["fail"])
    remaining_kpi.metric(
        "Remaining ⏳",
        max(
            0,
            st.session_state.stats["total"]
            - (st.session_state.stats["success"] + st.session_state.stats["fail"])
        )
    )

render_kpis()

# ---------------- CONTROLS ----------------
progress_bar = st.progress(0)
status_ui = st.empty()

c1, c2 = st.columns(2)
start_btn = c1.button("▶ START / RESUME", use_container_width=True, disabled=st.session_state.running)
stop_btn = c2.button("🛑 STOP AUTOMATION", use_container_width=True, disabled=not st.session_state.running)

if stop_btn:
    st.session_state.running = False
    add_log("Automation stopped by user.", "warning")
    st.rerun()

# ---------------- LOG VIEW ----------------
st.markdown("### 📜 Live Activity Feed")
log_box = st.empty()

def render_logs():
    with log_box.container(height=300, border=True):
        for log in st.session_state.logs[:25]:
            st.write(log)

render_logs()

# ---------------- START ----------------
if start_btn and uploaded_file:
    df_preview = pd.read_csv(uploaded_file)
    if "email" in df_preview.columns:
        st.session_state.stats["total"] = len(df_preview)
        render_kpis()

if start_btn and uploaded_file and not st.session_state.running:
    st.session_state.running = True
    st.session_state._lock = True  # 🔒 lock reruns
    add_log("Automation started.", "success")
    st.rerun()

# ---------------- AUTOMATION ----------------
if st.session_state.running and uploaded_file:
    df = pd.read_csv(uploaded_file)
    if "email" not in df.columns:
        st.error("CSV error: 'email' column not found.")
        st.session_state.running = False
    else:
        bot = LeadAutomation(target_url, add_log, headless=is_headless)
        cp = bot.load_checkpoint()

        if not st.session_state.checkpoint_loaded:
            st.session_state.stats["success"] = cp["success_count"]
            st.session_state.stats["fail"] = cp["fail_count"]
            st.session_state.checkpoint_loaded = True
            render_kpis()

        bot.init_driver()

        try:
            for i in range(cp["last_index"], len(df)):
                if not st.session_state.running:
                    break

                email = df.iloc[i]["email"]
                status_ui.markdown(f"**🔄 Now Processing:** `{email}`")

                if bot.process_email(email):
                    st.session_state.stats["success"] += 1
                    add_log(f"Success: {email}", "success")
                else:
                    st.session_state.stats["fail"] += 1
                    add_log(f"Failed after 10 retries: {email}", "error")

                render_kpis()
                progress_bar.progress(
                    min(
                        1.0,
                        (st.session_state.stats["success"] + st.session_state.stats["fail"])
                        / st.session_state.stats["total"]
                    )
                )

                bot.save_checkpoint(
                    i + 1,
                    st.session_state.stats["success"],
                    st.session_state.stats["fail"]
                )

                render_logs()
                time.sleep(0.05)

        finally:
            bot.quit()
            st.session_state.running = False
            st.session_state._lock = False
            add_log("Automation paused or finished.", "warning")
            render_logs()
            render_kpis()

# ---------------- HARD STOP FOR STREAMLIT CLOUD ----------------
if st.session_state.get("_lock"):
    st.stop()