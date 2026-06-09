from __future__ import annotations

from html import escape
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
    render_hero()

    cases = render_sidebar()
    results = st.session_state.get("results")
    agent_view = st.session_state.get("agent_view")

    if results is None or agent_view is None:
        render_start_state()
        return

    render_dashboard(agent_view)
    agent_tab, detail_tab, export_tab = st.tabs(
        ["Agent View", "Case Detail & Template", "Output / Export"]
    )

    with agent_tab:
        filtered = render_agent_view(agent_view)

    with detail_tab:
        render_case_detail(filtered)

    with export_tab:
        render_export(results, agent_view)


def render_hero() -> None:
    st.markdown(
        """
        <section class="hero">
            <p class="hero-kicker">OEM Case Management</p>
            <h1>AI Case Engine MVP</h1>
            <h2>Priorisierung, Eskalationsrisiko und Antwortsteuerung für OEM Case Management</h2>
            <p>
                Die App bewertet eingehende Cases nach Business Value, Dringlichkeit,
                Eskalationsrisiko und Kommunikationsbedarf.
            </p>
        </section>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar() -> pd.DataFrame | None:
    with st.sidebar:
        st.markdown('<div class="sidebar-title">AI Case Engine</div>', unsafe_allow_html=True)

        st.markdown('<div class="sidebar-section">Case Input</div>', unsafe_allow_html=True)
        case_mode = st.radio(
            "Case Input",
            ["Excel Upload", "Manuelle Eingabe"],
            label_visibility="collapsed",
        )
        cases = load_uploaded_or_manual_cases(case_mode)

        st.markdown('<div class="sidebar-section">Rulebook</div>', unsafe_allow_html=True)
        rulebook_upload = st.file_uploader("Rulebook Upload", type=["xlsx"], key="rulebook")
        rulebook_source = rulebook_upload if rulebook_upload else DEFAULT_RULEBOOK_FILE
        if rulebook_upload:
            st.success("Rulebook Upload aktiv")
        else:
            st.info(f"Default Rulebook aktiv: {DEFAULT_RULEBOOK_FILE.name}")

        st.markdown('<div class="sidebar-section">Analyse</div>', unsafe_allow_html=True)
        if st.button("Analyse starten", type="primary", use_container_width=True):
            run_analysis(cases, rulebook_source)
        st.caption("Keine echten Kundendaten in öffentlicher Demo verwenden.")

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

    with st.form("manual_case_form"):
        values = {
            "case_id": st.text_input("case_id", "C-DEMO-001"),
            "customer_name": st.text_input("customer_name", "Muster GmbH"),
            "vehicle_model": st.text_input("vehicle_model", "Crafter"),
            "vin": st.text_input("vin", "WVDEMO123456789"),
            "case_subject": st.text_input("case_subject", "Fahrzeug nicht einsatzbereit"),
            "case_text": st.text_area(
                "case_text",
                "Unser Fahrzeug ist nicht fahrbereit. Wir verlieren Kundentermine und brauchen dringend eine Lösung.",
                height=140,
            ),
            "previous_cases": st.text_input("previous_cases", "2"),
            "language": st.text_input("language", "DE"),
        }
        submitted = st.form_submit_button("Case übernehmen", use_container_width=True)

    if submitted or "manual_case_df" not in st.session_state:
        st.session_state["manual_case_df"] = pd.DataFrame([values], columns=REQUIRED_INPUT_COLUMNS)

    return st.session_state["manual_case_df"]


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
    steps = [
        ("1", "Case Input wählen"),
        ("2", "Rulebook laden"),
        ("3", "Analyse starten"),
        ("4", "Agent View prüfen"),
    ]
    step_html = "".join(
        f'<div class="step"><span>{number}</span><strong>{escape(label)}</strong></div>'
        for number, label in steps
    )
    st.markdown(
        f"""
        <section class="start-card">
            <p class="eyebrow">Start</p>
            <h3>Bereit für die MVP-Analyse</h3>
            <div class="steps">{step_html}</div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def render_dashboard(agent_view: pd.DataFrame) -> None:
    st.markdown('<div class="section-heading">Dashboard</div>', unsafe_allow_html=True)
    kpis = [
        ("Cases gesamt", len(agent_view), "blue"),
        ("P1 Cases", int((agent_view["case_priority_class"] == "P1").sum()), "red"),
        ("P2 Cases", int((agent_view["case_priority_class"] == "P2").sum()), "orange"),
        ("Red Risk", int((agent_view["escalation_risk_level"] == "red").sum()), "red"),
        ("Orange Risk", int((agent_view["escalation_risk_level"] == "orange").sum()), "orange"),
        ("Very High Urgency", int((agent_view["urgency_level"] == "very_high").sum()), "yellow"),
        (
            "High Business Value",
            int(agent_view["business_value_level"].isin(["high", "very_high"]).sum()),
            "violet",
        ),
    ]

    cols = st.columns(len(kpis))
    for col, (label, value, tone) in zip(cols, kpis):
        col.markdown(
            f"""
            <div class="kpi-card kpi-{tone}">
                <span>{escape(label)}</span>
                <strong>{value}</strong>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_agent_view(agent_view: pd.DataFrame) -> pd.DataFrame:
    st.markdown('<div class="tab-heading">Agent View</div>', unsafe_allow_html=True)
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
        height=500,
    )
    return filtered


def render_case_detail(agent_view: pd.DataFrame) -> None:
    st.markdown('<div class="tab-heading">Case Detail & Template</div>', unsafe_allow_html=True)
    if agent_view.empty:
        st.info("Keine Cases in der aktuellen Filterauswahl.")
        return

    selected = st.selectbox("Case auswählen", agent_view["case_id"].astype(str).tolist())
    row = agent_view[agent_view["case_id"].astype(str) == selected].iloc[0]

    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(status_card("Priority", row.get("case_priority_class", ""), "priority"), unsafe_allow_html=True)
    c2.markdown(status_card("Risk", row.get("escalation_risk_level", ""), "risk"), unsafe_allow_html=True)
    c3.markdown(metric_card("Template ID", row.get("recommended_template_id", "")), unsafe_allow_html=True)
    c4.markdown(metric_card("Tone Level", row.get("tone_level", "")), unsafe_allow_html=True)

    left, right = st.columns(2)
    with left:
        detail_card("Recommended Next Action", row.get("recommended_next_action", ""))
        detail_card("Agent Warning", row.get("agent_warning", ""))
        detail_card("Forbidden Claims", row.get("forbidden_claims", ""))
    with right:
        detail_card("Deescalation Phrases", row.get("deescalation_phrases", ""))
        detail_card("Recommended Customer Reply", row.get("recommended_customer_reply", ""))
        detail_card("Decision Reason", row.get("decision_reason", ""))


def render_export(results: pd.DataFrame, agent_view: pd.DataFrame) -> None:
    st.markdown('<div class="tab-heading">Output / Export</div>', unsafe_allow_html=True)
    st.markdown('<div class="table-title">Output Simulation</div>', unsafe_allow_html=True)
    st.dataframe(results, use_container_width=True, hide_index=True, height=320)

    st.markdown('<div class="table-title">Agent View</div>', unsafe_allow_html=True)
    visible_cols = [col for col in AGENT_VIEW_COLUMNS if col in agent_view.columns]
    st.dataframe(agent_view[visible_cols], use_container_width=True, hide_index=True, height=320)

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


def metric_card(title: str, value) -> str:
    safe_value = escape(str(value).strip() or "-")
    return f"""
    <div class="metric-card">
        <span>{escape(title)}</span>
        <strong>{safe_value}</strong>
    </div>
    """


def status_card(title: str, value, kind: str) -> str:
    normalized = str(value).lower()
    tone = "neutral"
    if kind == "priority":
        tone = {"p1": "red", "p2": "orange", "p3": "yellow", "p4": "green"}.get(normalized, "neutral")
    if kind == "risk":
        tone = {"red": "red", "orange": "orange", "yellow": "yellow", "green": "green"}.get(
            normalized,
            "neutral",
        )
    return f"""
    <div class="metric-card status-{tone}">
        <span>{escape(title)}</span>
        <strong>{escape(str(value).strip() or "-")}</strong>
    </div>
    """


def detail_card(title: str, value) -> None:
    safe_value = escape(str(value).strip() or "-")
    st.markdown(
        f"""
        <div class="detail-card">
            <span>{escape(title)}</span>
            <p>{safe_value}</p>
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
        :root {
            --ink: #162033;
            --muted: #667085;
            --line: #d8dee8;
            --surface: #ffffff;
            --page: #f4f7fb;
            --blue: #2563eb;
            --red: #dc2626;
            --orange: #f97316;
            --yellow: #eab308;
            --violet: #6d28d9;
            --green: #16a34a;
        }

        .stApp {
            background: var(--page);
            color: var(--ink);
        }

        .block-container {
            padding-bottom: 3rem;
            padding-top: 1.25rem;
            max-width: 1480px;
        }

        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #0f172a 0%, #111827 100%);
            border-right: 1px solid #263244;
        }

        [data-testid="stSidebar"] * {
            color: #f8fafc !important;
        }

        [data-testid="stSidebar"] .stAlert {
            background: rgba(255, 255, 255, 0.08);
            border: 1px solid rgba(255, 255, 255, 0.14);
        }

        [data-testid="stSidebar"] input,
        [data-testid="stSidebar"] textarea {
            background-color: #111827 !important;
            border: 1px solid #475569 !important;
            caret-color: #ffffff !important;
            color: #ffffff !important;
            -webkit-text-fill-color: #ffffff !important;
        }

        [data-testid="stSidebar"] input::placeholder,
        [data-testid="stSidebar"] textarea::placeholder {
            color: #cbd5e1 !important;
            -webkit-text-fill-color: #cbd5e1 !important;
            opacity: 1 !important;
        }

        .sidebar-title {
            font-size: 24px;
            font-weight: 800;
            letter-spacing: 0;
            margin: 8px 0 24px;
        }

        .sidebar-section {
            margin: 24px 0 10px;
            padding-top: 16px;
            border-top: 1px solid rgba(255, 255, 255, 0.15);
            color: #cbd5e1 !important;
            font-size: 12px;
            font-weight: 800;
            text-transform: uppercase;
        }

        .hero {
            background: linear-gradient(135deg, #ffffff 0%, #eef4ff 100%);
            border: 1px solid var(--line);
            border-radius: 8px;
            padding: 28px 32px;
            margin-bottom: 24px;
            box-shadow: 0 1px 2px rgba(16, 24, 40, 0.06);
        }

        .hero-kicker,
        .eyebrow {
            color: var(--blue);
            font-size: 12px;
            font-weight: 800;
            margin: 0 0 8px;
            text-transform: uppercase;
        }

        .hero h1 {
            color: var(--ink);
            font-size: 38px;
            line-height: 1.1;
            margin: 0;
            letter-spacing: 0;
        }

        .hero h2 {
            color: #344054;
            font-size: 18px;
            font-weight: 700;
            margin: 10px 0 8px;
            letter-spacing: 0;
        }

        .hero p {
            color: var(--muted);
            font-size: 15px;
            line-height: 1.5;
            margin: 0;
            max-width: 860px;
        }

        .section-heading,
        .tab-heading {
            color: var(--ink);
            font-size: 20px;
            font-weight: 800;
            margin: 8px 0 14px;
        }

        .start-card,
        .kpi-card,
        .metric-card,
        .detail-card {
            background: var(--surface);
            border: 1px solid var(--line);
            border-radius: 8px;
            box-shadow: 0 1px 2px rgba(16, 24, 40, 0.06);
        }

        .start-card {
            padding: 28px;
        }

        .start-card h3 {
            color: var(--ink);
            font-size: 24px;
            margin: 0 0 18px;
            letter-spacing: 0;
        }

        .steps {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 12px;
        }

        .step {
            background: #f8fafc;
            border: 1px solid var(--line);
            border-radius: 8px;
            padding: 14px;
        }

        .step span {
            align-items: center;
            background: var(--blue);
            border-radius: 999px;
            color: #ffffff;
            display: inline-flex;
            font-weight: 800;
            height: 28px;
            justify-content: center;
            margin-bottom: 10px;
            width: 28px;
        }

        .step strong {
            color: var(--ink);
            display: block;
            font-size: 14px;
        }

        .kpi-card {
            border-top: 4px solid var(--blue);
            min-height: 106px;
            padding: 16px;
        }

        .kpi-card span,
        .metric-card span,
        .detail-card span {
            color: var(--muted);
            display: block;
            font-size: 12px;
            font-weight: 800;
            line-height: 1.25;
            text-transform: uppercase;
        }

        .kpi-card strong {
            color: var(--ink);
            display: block;
            font-size: 32px;
            line-height: 1;
            margin-top: 14px;
        }

        .kpi-red { border-top-color: var(--red); }
        .kpi-orange { border-top-color: var(--orange); }
        .kpi-yellow { border-top-color: var(--yellow); }
        .kpi-violet { border-top-color: var(--violet); }
        .kpi-blue { border-top-color: var(--blue); }

        .metric-card {
            min-height: 96px;
            padding: 16px;
        }

        .metric-card strong {
            color: var(--ink);
            display: block;
            font-size: 20px;
            line-height: 1.2;
            margin-top: 12px;
            overflow-wrap: anywhere;
        }

        .status-red { border-top: 4px solid var(--red); }
        .status-orange { border-top: 4px solid var(--orange); }
        .status-yellow { border-top: 4px solid var(--yellow); }
        .status-green { border-top: 4px solid var(--green); }
        .status-neutral { border-top: 4px solid var(--blue); }

        .detail-card {
            margin-bottom: 12px;
            min-height: 138px;
            padding: 16px;
        }

        .detail-card p {
            color: var(--ink);
            line-height: 1.5;
            margin: 10px 0 0;
            overflow-wrap: anywhere;
            white-space: pre-wrap;
        }

        .table-title {
            color: var(--ink);
            font-size: 15px;
            font-weight: 800;
            margin: 12px 0 8px;
        }

        .stTabs [data-baseweb="tab-list"] {
            gap: 8px;
        }

        .stTabs [data-baseweb="tab"] {
            background: #ffffff;
            border: 1px solid var(--line);
            border-radius: 8px 8px 0 0;
            color: var(--ink);
            font-weight: 700;
            padding: 10px 16px;
        }

        .stButton > button,
        .stDownloadButton > button {
            border-radius: 6px;
            font-weight: 800;
        }

        @media (max-width: 900px) {
            .steps {
                grid-template-columns: 1fr;
            }
            .hero {
                padding: 22px;
            }
            .hero h1 {
                font-size: 30px;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
