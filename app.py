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
    cockpit_tab, reply_tab, export_tab = st.tabs(
        ["Agent Cockpit", "Reply Template", "Table View / Export"]
    )

    with cockpit_tab:
        selected_row = render_agent_cockpit(agent_view)

    with reply_tab:
        render_reply_template(selected_row)

    with export_tab:
        render_export(results, agent_view)


def render_hero() -> None:
    st.markdown(
        """
        <section class="hero">
            <div>
                <p class="hero-kicker">OEM Case Management</p>
                <h1>AI Case Engine MVP</h1>
                <h2>Priorisierung, Eskalationsrisiko und Antwortsteuerung für OEM Case Management</h2>
            </div>
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
    st.session_state["selected_case_id"] = first_value(agent_view, "case_id")
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
    kpis = [
        ("Cases gesamt", len(agent_view), "blue"),
        ("P1", int((safe_series(agent_view, "case_priority_class") == "P1").sum()), "red"),
        ("P2", int((safe_series(agent_view, "case_priority_class") == "P2").sum()), "orange"),
        ("Red Risk", int((safe_series(agent_view, "escalation_risk_level") == "red").sum()), "red"),
        (
            "Orange Risk",
            int((safe_series(agent_view, "escalation_risk_level") == "orange").sum()),
            "orange",
        ),
        (
            "High Business Value",
            int(safe_series(agent_view, "business_value_level").isin(["high", "very_high"]).sum()),
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


def render_agent_cockpit(agent_view: pd.DataFrame) -> pd.Series:
    if agent_view.empty:
        st.info("Keine Cases vorhanden.")
        return pd.Series(dtype=object)

    case_ids = safe_series(agent_view, "case_id").astype(str).tolist()
    current = st.session_state.get("selected_case_id")
    if current not in case_ids:
        current = case_ids[0]
        st.session_state["selected_case_id"] = current

    queue_col, workspace_col = st.columns([0.35, 0.65], gap="large")

    with queue_col:
        st.markdown('<div class="cockpit-heading">Case Queue</div>', unsafe_allow_html=True)
        selected_id = st.radio(
            "Case auswählen",
            case_ids,
            index=case_ids.index(current),
            format_func=lambda case_id: radio_label(agent_view, case_id),
            key="selected_case_id",
            label_visibility="collapsed",
        )
        selected_row = selected_case(agent_view, selected_id)
        render_case_queue(agent_view, selected_id)

    with workspace_col:
        render_case_workspace(selected_row)

    return selected_row


def render_case_queue(agent_view: pd.DataFrame, selected_id: str) -> None:
    for _, row in agent_view.iterrows():
        case_id = value(row, "case_id")
        selected_class = " selected" if str(case_id) == str(selected_id) else ""
        priority = value(row, "case_priority_class")
        risk = value(row, "escalation_risk_level")
        card_tone = queue_tone(priority, risk)
        st.markdown(
            f"""
            <div class="queue-card queue-{card_tone}{selected_class}">
                <div class="queue-topline">
                    <strong>{escape(case_id)}</strong>
                    <div class="badge-row">
                        {badge(priority, "priority")}
                        {badge(risk, "risk")}
                    </div>
                </div>
                <div class="queue-customer">{escape(value(row, "customer_name"))}</div>
                <div class="queue-model">{escape(value(row, "vehicle_model"))}</div>
                <div class="queue-meta">
                    <span>Urgency <b>{escape(value(row, "urgency_level"))}</b></span>
                    <span>Business <b>{escape(value(row, "business_value_level"))}</b></span>
                    <span>Score <b>{escape(value(row, "priority_score"))}</b></span>
                </div>
                <div class="queue-template">{escape(value(row, "recommended_template_id"))}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_case_workspace(row: pd.Series) -> None:
    if row.empty:
        st.info("Bitte einen Case auswählen.")
        return

    st.markdown('<div class="cockpit-heading">Case Workspace</div>', unsafe_allow_html=True)

    st.markdown('<div class="workspace-section-title">Customer & Case</div>', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(info_card("Kunde", value(row, "customer_name")), unsafe_allow_html=True)
    c2.markdown(info_card("Fahrzeugmodell", value(row, "vehicle_model")), unsafe_allow_html=True)
    c3.markdown(info_card("Case ID", value(row, "case_id")), unsafe_allow_html=True)
    c4.markdown(info_card("Template ID", value(row, "recommended_template_id")), unsafe_allow_html=True)

    st.markdown('<div class="workspace-section-title">Assessment</div>', unsafe_allow_html=True)
    a1, a2, a3, a4, a5, a6 = st.columns(6)
    a1.markdown(assessment_card("Priority", value(row, "case_priority_class"), "priority"), unsafe_allow_html=True)
    a2.markdown(assessment_card("Risk", value(row, "escalation_risk_level"), "risk"), unsafe_allow_html=True)
    a3.markdown(assessment_card("Score", value(row, "priority_score"), "score"), unsafe_allow_html=True)
    a4.markdown(assessment_card("Urgency", value(row, "urgency_level"), "neutral"), unsafe_allow_html=True)
    a5.markdown(assessment_card("Business Value", value(row, "business_value_level"), "neutral"), unsafe_allow_html=True)
    a6.markdown(assessment_card("Tone Level", value(row, "tone_level"), "neutral"), unsafe_allow_html=True)

    action_text = value(row, "recommended_next_action")
    st.markdown(
        f"""
        <div class="large-card action-card">
            <span>Recommended Next Action</span>
            <p>{escape(action_text) if action_text else "-"}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    warning = value(row, "agent_warning")
    if warning:
        st.markdown(
            f"""
            <div class="large-card warning-card">
                <span>Agent Warning</span>
                <p>{escape(warning)}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    forbidden = value(row, "forbidden_claims")
    st.markdown(
        f"""
        <div class="large-card forbidden-card">
            <span>Forbidden Claims</span>
            <p>{escape(forbidden) if forbidden else "-"}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.expander("Warum wurde dieser Case so bewertet?"):
        st.markdown("**Decision Reason**")
        st.write(value(row, "decision_reason") or "-")
        st.markdown("**Template Selection Reason**")
        st.write(value(row, "template_selection_reason") or "-")


def render_reply_template(row: pd.Series) -> None:
    st.markdown('<div class="cockpit-heading">Empfohlenes Antworttemplate</div>', unsafe_allow_html=True)
    if row.empty:
        st.info("Bitte zuerst einen Case auswählen.")
        return

    st.markdown(
        f"""
        <div class="reply-context">
            <span>{escape(value(row, "case_id"))}</span>
            <strong>{escape(value(row, "customer_name"))}</strong>
            <em>{escape(value(row, "recommended_template_id"))}</em>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.text_area(
        "Recommended Customer Reply",
        value=value(row, "recommended_customer_reply"),
        height=320,
        label_visibility="collapsed",
        key=f"reply_template_{value(row, 'case_id')}",
    )
    st.markdown(
        f"""
        <div class="large-card deescalation-card">
            <span>Deescalation Phrases</span>
            <p>{escape(value(row, "deescalation_phrases")) or "-"}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_export(results: pd.DataFrame, agent_view: pd.DataFrame) -> None:
    st.markdown('<div class="cockpit-heading">Table View / Export</div>', unsafe_allow_html=True)
    visible_cols = [col for col in AGENT_VIEW_COLUMNS if col in agent_view.columns]

    st.markdown('<div class="table-title">Agent View</div>', unsafe_allow_html=True)
    st.dataframe(agent_view[visible_cols], use_container_width=True, hide_index=True, height=360)

    st.markdown('<div class="table-title">Output Simulation</div>', unsafe_allow_html=True)
    st.dataframe(results, use_container_width=True, hide_index=True, height=360)

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


def selected_case(agent_view: pd.DataFrame, case_id: str) -> pd.Series:
    if "case_id" not in agent_view.columns or agent_view.empty:
        return pd.Series(dtype=object)
    match = agent_view[agent_view["case_id"].astype(str) == str(case_id)]
    if match.empty:
        return agent_view.iloc[0]
    return match.iloc[0]


def radio_label(agent_view: pd.DataFrame, case_id: str) -> str:
    row = selected_case(agent_view, case_id)
    return f"{value(row, 'case_id')} | {value(row, 'customer_name')} | {value(row, 'case_priority_class')}"


def safe_series(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series([""] * len(df), index=df.index, dtype="object")
    return df[column].fillna("")


def first_value(df: pd.DataFrame, column: str) -> str:
    if df.empty or column not in df.columns:
        return ""
    return str(df.iloc[0].get(column, ""))


def value(row: pd.Series, column: str) -> str:
    if row.empty:
        return ""
    raw = row.get(column, "")
    if pd.isna(raw):
        return ""
    return str(raw)


def queue_tone(priority: str, risk: str) -> str:
    if str(priority).upper() == "P1" or str(risk).lower() == "red":
        return "critical"
    if str(priority).upper() == "P2" or str(risk).lower() == "orange":
        return "elevated"
    return "standard"


def badge(text: str, kind: str) -> str:
    normalized = str(text).lower()
    tone = "neutral"
    if kind == "priority":
        tone = {"p1": "red", "p2": "orange", "p3": "yellow", "p4": "green"}.get(normalized, "neutral")
    if kind == "risk":
        tone = {"red": "red", "orange": "orange", "yellow": "yellow", "green": "green"}.get(
            normalized,
            "neutral",
        )
    return f'<span class="badge badge-{tone}">{escape(str(text) or "-")}</span>'


def info_card(title: str, text: str) -> str:
    return f"""
    <div class="info-card">
        <span>{escape(title)}</span>
        <strong>{escape(text) if text else "-"}</strong>
    </div>
    """


def assessment_card(title: str, text: str, kind: str) -> str:
    tone = "neutral"
    normalized = str(text).lower()
    if kind == "priority":
        tone = {"p1": "red", "p2": "orange", "p3": "yellow", "p4": "green"}.get(normalized, "neutral")
    elif kind == "risk":
        tone = {"red": "red", "orange": "orange", "yellow": "yellow", "green": "green"}.get(
            normalized,
            "neutral",
        )
    elif kind == "score":
        tone = "blue"
    return f"""
    <div class="assessment-card assess-{tone}">
        <span>{escape(title)}</span>
        <strong>{escape(text) if text else "-"}</strong>
    </div>
    """


def apply_theme() -> None:
    st.markdown(
        """
        <style>
        :root {
            --ink: #172033;
            --muted: #667085;
            --line: #d9e1ec;
            --surface: #ffffff;
            --page: #f4f7fb;
            --blue: #2563eb;
            --red: #dc2626;
            --orange: #f97316;
            --yellow: #ca8a04;
            --violet: #6d28d9;
            --green: #16a34a;
        }

        .stApp {
            background: var(--page);
            color: var(--ink);
        }

        .block-container {
            max-width: 1520px;
            padding-bottom: 3rem;
            padding-top: 1rem;
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
            align-items: center;
            background: linear-gradient(135deg, #ffffff 0%, #eef4ff 100%);
            border: 1px solid var(--line);
            border-radius: 16px;
            box-shadow: 0 8px 24px rgba(16, 24, 40, 0.06);
            display: flex;
            min-height: 118px;
            margin-bottom: 18px;
            padding: 22px 28px;
        }

        .hero-kicker,
        .eyebrow {
            color: var(--blue);
            font-size: 12px;
            font-weight: 800;
            margin: 0 0 6px;
            text-transform: uppercase;
        }

        .hero h1 {
            color: var(--ink);
            font-size: 34px;
            line-height: 1.05;
            margin: 0;
            letter-spacing: 0;
        }

        .hero h2 {
            color: #344054;
            font-size: 17px;
            font-weight: 700;
            letter-spacing: 0;
            margin: 8px 0 0;
        }

        .start-card,
        .kpi-card,
        .queue-card,
        .info-card,
        .assessment-card,
        .large-card {
            background: var(--surface);
            border: 1px solid var(--line);
            border-radius: 16px;
            box-shadow: 0 8px 24px rgba(16, 24, 40, 0.06);
        }

        .start-card {
            padding: 30px;
        }

        .start-card h3 {
            color: var(--ink);
            font-size: 26px;
            letter-spacing: 0;
            margin: 0 0 20px;
        }

        .steps {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 14px;
        }

        .step {
            background: #f8fafc;
            border: 1px solid var(--line);
            border-radius: 14px;
            padding: 16px;
        }

        .step span {
            align-items: center;
            background: var(--blue);
            border-radius: 999px;
            color: #ffffff;
            display: inline-flex;
            font-weight: 800;
            height: 30px;
            justify-content: center;
            margin-bottom: 12px;
            width: 30px;
        }

        .step strong {
            color: var(--ink);
            display: block;
            font-size: 15px;
        }

        .kpi-card {
            border-top: 5px solid var(--blue);
            min-height: 104px;
            padding: 18px 18px 16px;
        }

        .kpi-card span,
        .info-card span,
        .assessment-card span,
        .large-card span {
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
            font-size: 34px;
            line-height: 1;
            margin-top: 14px;
        }

        .kpi-blue { border-top-color: var(--blue); }
        .kpi-red { border-top-color: var(--red); }
        .kpi-orange { border-top-color: var(--orange); }
        .kpi-violet { border-top-color: var(--violet); }

        .cockpit-heading {
            color: var(--ink);
            font-size: 22px;
            font-weight: 850;
            margin: 12px 0 14px;
        }

        .workspace-section-title,
        .table-title {
            color: #344054;
            font-size: 14px;
            font-weight: 850;
            margin: 18px 0 10px;
            text-transform: uppercase;
        }

        .queue-card {
            border-left: 6px solid #94a3b8;
            margin: 12px 0;
            padding: 16px;
        }

        .queue-card.selected {
            outline: 3px solid rgba(37, 99, 235, 0.22);
        }

        .queue-critical { border-left-color: var(--red); }
        .queue-elevated { border-left-color: var(--orange); }

        .queue-topline {
            align-items: center;
            display: flex;
            gap: 10px;
            justify-content: space-between;
        }

        .queue-topline strong {
            color: var(--ink);
            font-size: 17px;
        }

        .badge-row {
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
            justify-content: flex-end;
        }

        .badge {
            border-radius: 999px;
            display: inline-block;
            font-size: 11px;
            font-weight: 850;
            line-height: 1;
            padding: 7px 9px;
            text-transform: uppercase;
        }

        .badge-red { background: #fee2e2; color: #7f1d1d; }
        .badge-orange { background: #ffedd5; color: #7c2d12; }
        .badge-yellow { background: #fef9c3; color: #713f12; }
        .badge-green { background: #dcfce7; color: #14532d; }
        .badge-neutral { background: #e2e8f0; color: #334155; }

        .queue-customer {
            color: var(--ink);
            font-size: 16px;
            font-weight: 800;
            margin-top: 12px;
        }

        .queue-model {
            color: var(--muted);
            font-size: 14px;
            margin-top: 2px;
        }

        .queue-meta {
            display: grid;
            gap: 6px;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            margin-top: 14px;
        }

        .queue-meta span {
            background: #f8fafc;
            border-radius: 10px;
            color: var(--muted);
            font-size: 11px;
            padding: 8px;
        }

        .queue-meta b {
            color: var(--ink);
            display: block;
            font-size: 13px;
            margin-top: 3px;
            overflow-wrap: anywhere;
        }

        .queue-template {
            border-top: 1px solid var(--line);
            color: #344054;
            font-size: 12px;
            font-weight: 800;
            margin-top: 12px;
            overflow-wrap: anywhere;
            padding-top: 10px;
        }

        .info-card,
        .assessment-card {
            min-height: 104px;
            padding: 17px;
        }

        .info-card strong,
        .assessment-card strong {
            color: var(--ink);
            display: block;
            font-size: 20px;
            line-height: 1.2;
            margin-top: 12px;
            overflow-wrap: anywhere;
        }

        .assessment-card {
            border-top: 5px solid #94a3b8;
        }

        .assess-red { border-top-color: var(--red); }
        .assess-orange { border-top-color: var(--orange); }
        .assess-yellow { border-top-color: var(--yellow); }
        .assess-green { border-top-color: var(--green); }
        .assess-blue { border-top-color: var(--blue); }

        .large-card {
            margin-top: 16px;
            padding: 20px;
        }

        .large-card p {
            color: var(--ink);
            font-size: 18px;
            line-height: 1.5;
            margin: 12px 0 0;
            overflow-wrap: anywhere;
            white-space: pre-wrap;
        }

        .action-card { border-left: 6px solid var(--blue); }
        .warning-card { border-left: 6px solid var(--orange); background: #fff7ed; }
        .forbidden-card { border-left: 6px solid var(--red); background: #fff7f7; }
        .deescalation-card { border-left: 6px solid var(--green); }

        .reply-context {
            align-items: center;
            background: #ffffff;
            border: 1px solid var(--line);
            border-radius: 16px;
            display: flex;
            gap: 14px;
            margin-bottom: 14px;
            padding: 14px 16px;
        }

        .reply-context span {
            background: #e0ecff;
            border-radius: 999px;
            color: #1d4ed8;
            font-weight: 850;
            padding: 7px 10px;
        }

        .reply-context strong {
            color: var(--ink);
            font-size: 16px;
        }

        .reply-context em {
            color: var(--muted);
            font-style: normal;
            font-weight: 700;
            margin-left: auto;
        }

        textarea {
            background: #ffffff !important;
            color: #111827 !important;
            font-size: 16px !important;
            line-height: 1.5 !important;
        }

        [data-testid="stSidebar"] input,
        [data-testid="stSidebar"] textarea {
            background-color: #111827 !important;
            border: 1px solid #475569 !important;
            caret-color: #ffffff !important;
            color: #ffffff !important;
            -webkit-text-fill-color: #ffffff !important;
        }

        .stTabs [data-baseweb="tab-list"] {
            gap: 10px;
            margin-top: 18px;
        }

        .stTabs [data-baseweb="tab"] {
            background: #ffffff;
            border: 1px solid var(--line);
            border-radius: 14px 14px 0 0;
            color: var(--ink);
            font-weight: 800;
            padding: 12px 18px;
        }

        .stRadio [role="radiogroup"] {
            background: #ffffff;
            border: 1px solid var(--line);
            border-radius: 16px;
            padding: 10px;
        }

        [data-testid="stSidebar"] .stRadio [role="radiogroup"] {
            background: rgba(255, 255, 255, 0.08);
            border-color: rgba(255, 255, 255, 0.18);
        }

        .stButton > button,
        .stDownloadButton > button {
            border-radius: 12px;
            font-weight: 850;
            min-height: 44px;
        }

        @media (max-width: 900px) {
            .steps,
            .queue-meta {
                grid-template-columns: 1fr;
            }
            .hero {
                min-height: auto;
                padding: 20px;
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
