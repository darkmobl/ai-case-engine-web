# AI Case Engine MVP Streamlit App

Lokale Streamlit-Web-App für das bestehende MVP `run_engine_mvp_v7.py`.

Die fachliche Source of Truth bleibt:

- `engine.py`: modularisierte Logik aus `run_engine_mvp_v7.py`
- `02_Regelmatrix/AI_Case_Engine_rulebook_MVP_Step1_Fleet_v7_TemplateMaster.xlsx`

## Start

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Erwarteter Case Input

Die App akzeptiert Excel, XLS oder CSV. Bei Excel wird bevorzugt das Sheet `case_input` gelesen.

Pflichtspalten:

- `case_id`
- `customer_name`
- `vehicle_model`
- `vin`
- `case_subject`
- `case_text`
- `previous_cases`
- `language`

Wenn Spalten fehlen, zeigt die App:

```text
Folgende Input-Spalten fehlen: ...
```

## Erwartetes Rulebook

Default-Rulebook:

```text
02_Regelmatrix/AI_Case_Engine_rulebook_MVP_Step1_Fleet_v7_TemplateMaster.xlsx
```

Pflicht-Sheets:

- `business_value_matrix`
- `customer_type_rules`
- `fleet_value_rules`
- `urgency_keywords`
- `escalation_keywords`
- `emotion_keywords`
- `case_type_rules`
- `score_weights`
- `scoring_config`
- `priority_floor_rules`
- `template_master`

Wenn Sheets fehlen, zeigt die App:

```text
Folgende Rulebook-Sheets fehlen: ...
```

## App-Funktionen

- Dashboard mit Cases gesamt, P1/P2, Red/Orange Risk, Very High Urgency und High Business Value
- Excel/CSV Upload für echte MVP Cases
- Manuelle Einzelfall-Erfassung mit exakt den MVP-Feldern
- Agent View mit den MVP-v7 Ergebnisfeldern
- Case Detail mit Decision Reason, Recommended Customer Reply, Forbidden Claims und Deescalation Phrases
- Excel Export mit `Output_Simulation_MVP` und `Agent_View_MVP`
