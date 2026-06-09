from __future__ import annotations

from io import BytesIO

import pandas as pd
import streamlit as st

from engine import (
    AGENT_VIEW_COLUMNS,
    DEFAULT_RULEBOOK_FILE,
    REQUIRED_INPUT_COLUMNS,
    analyze_cases,
    read_cases,
    read_rulebook,
)


st.set_page_config(
    page_title="AI Case Engine MVP",
    layout="wide",
    initial_sidebar_state="expanded",
)


def main() -> None:
    apply_theme()
    st.title("AI Case Engine MVP")
    st.caption("Streamlit-App auf Basis der lokalen run_engine_mvp_v7.py Logik.")

    cases = render_sidebar()
    results = st.session_state.get("results")
    agent_view = st.session_state.get("agent_view")

    if results is None or agent_view is None:
        render_start_state()
        return

    render_dashboard(agent_view)
    filtered = render_agent_view(agent_view)
    render_case_detail(filtered)
    render_export(results, agent_view)


def render_sidebar() -> pd.DataFrame | None:
    with st.sidebar:
        st.header("Analyse")
        case_mode = st.radio("Case Input", ["Excel Upload", "Manuelle Eingabe"])
        cases = load_uploaded_or_manual_cases(case_mode)

        st.divider()
        st.subheader("Rulebook")
        rulebook_upload = st.file_uploader("Rulebook Excel", type=["xlsx"], key="rulebook")
        rulebook_source = rulebook_upload if rulebook_upload else DEFAULT_RULEBOOK_FILE

        if st.button("Analyse starten", type="primary", use_container_width=True):
            run_analysis(cases, rulebook_source)

        if not rulebook_upload:
            st.caption(f"Default: {DEFAULT_RULEBOOK_FILE.name}")

        return cases


def load_uploaded_or_manual_cases(case_mode: str) -> pd.DataFrame | None:
    if case_mode == "Excel Upload":
        upload = st.file_uploader("Case Input Excel/CSV", type=["xlsx", "xls", "csv"], key="cases")
        if upload is None:
            st.info("Bitte Case-Input-Datei hochladen.")
            return None
        try:
            return read_cases(upload)
        except Exception as exc:
            st.error(str(exc))
            return None

    with st.form("manual_case"):
        values = {
            "case_id": st.text_input("case_id", "C-DEMO-001"),
            "customer_name": st.text_input("customer_name", "Muster GmbH"),
            "vehicle_model": st.text_input("vehicle_model", "Crafter"),
            "vin": st.text_input("vin", "WVDEMO123456789"),
            "case_subject": st.text_input("case_subject", "Fahrzeug nicht einsatzbereit"),
            "case_text": st.text_area(
                "case_text",
                "Unser Fahrzeug ist nicht fahrbereit. Wir verlieren Kundentermine und brauchen dringend eine Lösung.",
                height=150,
            ),
            "previous_cases": st.text_input("previous_cases", "2"),
            "language": st.text_input("language", "DE"),
        }
        submitted = st.form_submit_button("Case übernehmen", use_container_width=True)

    if submitted or "manual_case" not in st.session_state:
        st.session_state["manual_case_df"] = pd.DataFrame([values], columns=REQUIRED_INPUT_COLUMNS)

    return st.session_state["manual_case"]


def run_analysis(cases: pd.DataFrame | None, rulebook_source) -> None:
    if cases is None:
        st.warning("Bitte Case Input bereitstellen.")
        return

    try:
        rules = read_rulebook(rulebook_source)
        results, agent_view = analyze_cases(cases, rules)
    except Exception as exc:
        st.error(str(exc))
        return

    st.session_state["results"] = results
    st.session_state["agent_view"] = agent_view
    st.success("Analyse abgeschlossen.")


def render_start_state() -> None:
    st.markdown(
        """
        <div class="empty-state">
            <h3>Bereit für die MVP-Analyse</h3>
            <p>Links Case Input wählen, echtes Rulebook laden oder Default verwenden, dann Analyse starten.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_dashboard(agent_view: pd.DataFrame) -> None:
    st.subheader("Dashboard")
    kpis = {
        "Cases gesamt": len(agent_view),
        "P1 Cases": int((agent_view["case_priority_class"] == "P1").sum()),
        "P2 Cases": int((agent_view["case_priority_class"] == "P2").sum()),
        "Red Risk": int((agent_view["escalation_risk_level"] == "red").sum()),
        "Orange Risk": int((agent_view["escalation_risk_level"] == "orange").sum()),
        "Very High Urgency": int((agent_view["urgency_level"] == "very_high").sum()),
        "High Business Value": int(
            agent_view["business_value_level"].isin(["high", "very_high"]).sum()
        ),
    }

    cols = st.columns(len(kpis))
    for col, (label, value) in zip(cols, kpis.items()):
        col.markdown(
            f"""
            <div class="kpi-card">
                <span>{label}</span>
                <strong>{value}</strong>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_agent_view(agent_view: pd.DataFrame) -> pd.DataFrame:
    st.subheader("Agent View")
    c1, c2, c3 = st.columns(3)
    priorities = c1.multiselect(
        "Priority",
        sorted(agent_view["case_priority_class"].dropna().unique()),
    )
    risks = c2.multiselect(
        "Risk",
        sorted(agent_view["escalation_risk_level"].dropna().unique()),
    )
    urgency = c3.multiselect(
        "Urgency",
        sorted(agent_view["urgency_level"].dropna().unique()),
    )

    filtered = agent_view.copy()
    if priorities:
        filtered = filtered[filtered["case_priority_class"].isin(priorities)]
    if risks:
        filtered = filtered[filtered["escalation_risk_level"].isin(risks)]
    if urgency:
        filtered = filtered[filtered["urgency_level"].isin(urgency)]

    visible_cols = [col for col in AGENT_VIEW_COLUMNS if col in filtered.columns]
    st.dataframe(
        filtered[visible_cols].style.apply(style_agent_row, axis=1),
        use_container_width=True,
        hide_index=True,
        height=420,
    )
    return filtered


def render_case_detail(agent_view: pd.DataFrame) -> None:
    st.subheader("Case Detail")
    if agent_view.empty:
        st.info("Keine Cases in der aktuellen Filterauswahl.")
        return

    selected = st.selectbox("Case auswählen", agent_view["case_id"].astype(str).tolist())
    row = agent_view[agent_view["case_id"].astype(str) == selected].iloc[0]

    left, right = st.columns(2)
    with left:
        detail_card("Decision Reason", row.get("decision_reason", ""))
        detail_card("Forbidden Claims", row.get("forbidden_claims", ""))
    with right:
        detail_card("Recommended Customer Reply", row.get("recommended_customer_reply", ""))
        detail_card("Deescalation Phrases", row.get("deescalation_phrases", ""))


def render_export(results: pd.DataFrame, agent_view: pd.DataFrame) -> None:
    st.subheader("Export")
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        results.to_excel(writer, sheet_name="Output_Simulation_MVP", index=False)
        agent_view.to_excel(writer, sheet_name="Agent_View_MVP", index=False)

    st.download_button(
        "Ergebnis als Excel herunterladen",
        data=buffer.getvalue(),
        file_name="case_output_mvp_streamlit.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )


def detail_card(title: str, value) -> None:
    st.markdown(
        f"""
        <div class="detail-card">
            <span>{title}</span>
            <p>{value if str(value).strip() else "-"}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def style_agent_row(row: pd.Series) -> list[str]:
    styles = [""] * len(row)
    priority_styles = {
        "P1": "background-color: #fee2e2; color: #7f1d1d; font-weight: 700;",
        "P2": "background-color: #ffedd5; color: #7c2d12; font-weight: 700;",
        "P3": "background-color: #fef9c3; color: #713f12; font-weight: 700;",
        "P4": "background-color: #dcfce7; color: #14532d; font-weight: 700;",
    }
    risk_styles = {
        "red": "background-color: #fecaca; color: #7f1d1d; font-weight: 700;",
        "orange": "background-color: #fed7aa; color: #7c2d12; font-weight: 700;",
        "yellow": "background-color: #fef08a; color: #713f12; font-weight: 700;",
        "green": "background-color: #bbf7d0; color: #14532d; font-weight: 700;",
    }

    for index, column in enumerate(row.index):
        if column == "case_priority_class":
            styles[index] = priority_styles.get(str(row[column]), "")
        if column == "escalation_risk_level":
            styles[index] = risk_styles.get(str(row[column]).lower(), "")
    return styles


def apply_theme() -> None:
    st.markdown(
        """
        <style>
        .stApp { background: #f5f7fa; color: #162033; }
        [data-testid="stSidebar"] {
            background: #ffffff;
            border-right: 1px solid #d8dee8;
        }
        .kpi-card, .detail-card, .empty-state {
            background: #ffffff;
            border: 1px solid #d8dee8;
            border-radius: 8px;
            box-shadow: 0 1px 2px rgba(16, 24, 40, 0.06);
        }
        .kpi-card {
            padding: 16px;
            min-height: 96px;
        }
        .kpi-card span {
            display: block;
            color: #667085;
            font-size: 13px;
            line-height: 1.25;
        }
        .kpi-card strong {
            display: block;
            margin-top: 12px;
            font-size: 30px;
            line-height: 1;
            color: #162033;
        }
        .detail-card {
            padding: 16px;
            min-height: 156px;
            margin-bottom: 12px;
        }
        .detail-card span {
            display: block;
            color: #667085;
            font-size: 12px;
            font-weight: 700;
            text-transform: uppercase;
        }
        .detail-card p {
            margin: 8px 0 0;
            line-height: 1.45;
            white-space: pre-wrap;
        }
        .empty-state {
            padding: 36px;
            margin-top: 24px;
        }
        .stButton > button, .stDownloadButton > button {
            border-radius: 6px;
            font-weight: 700;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
