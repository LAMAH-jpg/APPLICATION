# app.py
# Streamlit app: Étude Caféine (multi-participants) + stockage CSV + calcul automatique + recommandations
# Pages: Participants -> Journal quotidien -> Recommandations
#
# Run:
#   pip install streamlit pandas
#   streamlit run app.py

import os
from datetime import datetime, date
import pandas as pd
import streamlit as st


# -----------------------------
# Config
# -----------------------------
st.set_page_config(page_title="Si youssef lghzal hhhhh ", layout="wide")

DATA_DIR = "data"
PARTICIPANTS_CSV = os.path.join(DATA_DIR, "participants.csv")
LOGS_CSV = os.path.join(DATA_DIR, "daily_logs.csv")

# Heures (comme demandé): 1h .. 23h
HOURS = list(range(1, 24))

# Unités simplifiées (plus faciles): nb de tasses/canettes/portions
# Tu peux ajuster les mg selon ton protocole.
UNIT_OPTIONS = {
    "Café espresso (tasse)": 75,
    "Café filtre (tasse)": 95,
    "Café instantané (tasse)": 60,
    "Thé noir (tasse)": 45,
    "Thé vert (tasse)": 30,
    "Boisson énergétique (canette machi tassa hhhhhhh)": 80,
    "Soda/Cola (canette)": 35,
    "Chocolat (portion)": 10,
}

SYMPTOMS = [
    ("palpitations", "Palpitations (Heart palpitations)"),
    ("headache", "Maux de tête (Headache)"),
    ("irritability", "Irritabilité (Irritability)"),
    ("digestive", "Troubles digestifs (Digestive issues)"),
]

PAGES = ["1) Participants", "2) Journal quotidien", "3) Recommandations"]


# -----------------------------
# I/O Helpers
# -----------------------------
def ensure_data_files():
    os.makedirs(DATA_DIR, exist_ok=True)

    if not os.path.exists(PARTICIPANTS_CSV):
        pd.DataFrame(
            columns=[
                "participant_id",
                "age",
                "sex",
                "sensitivity",
                "screen_time_evening",
                "sport",
                "created_at",
            ]
        ).to_csv(PARTICIPANTS_CSV, index=False)

    if not os.path.exists(LOGS_CSV):
        pd.DataFrame(
            columns=[
                "date",
                "participant_id",
                "caffeine_mg_total",
                "last_caffeine_hour",
                "bed_hour",
                "wake_hour",
                "sleep_hours",
                "sleep_quality_1_5",
                "stress_1_10",
                "anxiety_1_10",
                "focus_1_10",
                "palpitations",
                "headache",
                "irritability",
                "digestive",
                "drinks_detail",
                "created_at",
            ]
        ).to_csv(LOGS_CSV, index=False)


def load_participants() -> pd.DataFrame:
    df = pd.read_csv(PARTICIPANTS_CSV)
    if df.empty:
        return df
    df["participant_id"] = df["participant_id"].astype(str).str.strip().str.upper()
    return df


def load_logs() -> pd.DataFrame:
    df = pd.read_csv(LOGS_CSV)
    if df.empty:
        return df
    df["participant_id"] = df["participant_id"].astype(str).str.strip().str.upper()
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date
    return df


def save_participants(df: pd.DataFrame):
    df.to_csv(PARTICIPANTS_CSV, index=False)


def save_logs(df: pd.DataFrame):
    out = df.copy()
    out["date"] = out["date"].apply(lambda d: d.isoformat() if isinstance(d, date) else d)
    out.to_csv(LOGS_CSV, index=False)


def next_participant_id(existing_ids) -> str:
    max_n = 0
    for pid in existing_ids:
        pid = str(pid).strip().upper()
        if pid.startswith("P") and pid[1:].isdigit():
            max_n = max(max_n, int(pid[1:]))
    return f"P{max_n+1:03d}"


# -----------------------------
# Calculation Helpers
# -----------------------------
def compute_sleep_hours_from_hours(bed_hour: int, wake_hour: int) -> float:
    """
    Calcul automatique du temps de sommeil à partir de l'heure de coucher et de réveil.
    Gère le passage par minuit.
    Ex: 23 -> 7 = 8h
    """
    bed = int(bed_hour)
    wake = int(wake_hour)
    if wake <= bed:
        wake += 24
    return float(wake - bed)


def compute_caffeine_from_units(unit_counts: dict) -> tuple[int, str]:
    total = 0
    parts = []
    for unit_label, count in unit_counts.items():
        count = int(count)
        if count <= 0:
            continue
        mg_unit = UNIT_OPTIONS.get(unit_label, 0)
        mg = count * mg_unit
        total += mg
        parts.append(f"{unit_label} x{count} ({mg} mg)")
    return int(total), (" | ".join(parts) if parts else "")


def caffeine_level(mg: float) -> str:
    mg = float(mg or 0)
    if mg < 100:
        return "Faible"
    if mg <= 200:
        return "Moyen"
    return "Élevé"


def safe_int(x, default=0) -> int:
    try:
        if pd.isna(x):
            return default
        return int(float(x))
    except Exception:
        return default


def safe_float(x, default=0.0) -> float:
    try:
        if pd.isna(x):
            return default
        return float(x)
    except Exception:
        return default


# -----------------------------
# Recommendations (simple & claire)
# -----------------------------
def build_recommendations(participant_row: pd.Series | None, logs_df: pd.DataFrame) -> dict:
    if logs_df.empty:
        return {"summary": ["Aucune donnée pour ce participant."], "today": [], "patterns": []}

    df = logs_df.sort_values("date").copy()
    latest = df.iloc[-1]

    sensitivity = ""
    if participant_row is not None and not participant_row.empty:
        sensitivity = str(participant_row.get("sensitivity", "")).strip()

    caf = safe_float(latest.get("caffeine_mg_total"), 0)
    last_h = safe_int(latest.get("last_caffeine_hour"), 0)
    sleep_h = safe_float(latest.get("sleep_hours"), 0)
    anxiety = safe_int(latest.get("anxiety_1_10"), 0)
    stress = safe_int(latest.get("stress_1_10"), 0)
    focus = safe_int(latest.get("focus_1_10"), 0)

    palpitations = safe_int(latest.get("palpitations"), 0)
    headache = safe_int(latest.get("headache"), 0)
    irritability = safe_int(latest.get("irritability"), 0)
    digestive = safe_int(latest.get("digestive"), 0)

    level = caffeine_level(caf)

    summary = [
        f"**Dernière date :** {latest.get('date')}",
        f"**Caféine totale :** {int(caf)} mg (**niveau : {level}**)",
        f"**Dernière prise :** {last_h}h",
        f"**Sommeil (calculé) :** {sleep_h:.1f} h (qualité {safe_int(latest.get('sleep_quality_1_5'), 0)}/5)",
        f"**Anxiété :** {anxiety}/10 • **Stress :** {stress}/10 • **Concentration :** {focus}/10",
    ]
    if sensitivity:
        summary.append(f"**Sensibilité déclarée :** {sensitivity}")

    today = []

    # Cerveau / sommeil
    if last_h >= 17 and caf >= 100:
        today.append(
            "🧠 **Sommeil & cerveau :** dernière prise tardive (≥ 17h). "
            "➡️ Essaie de finir la caféine **avant 16–17h** (meilleur levier pour améliorer le sommeil)."
        )
    if sleep_h < 7:
        today.append(
            "🌙 **Sommeil :** < 7h. "
            "➡️ Le manque de sommeil baisse la mémoire et la concentration et augmente stress/anxiété."
        )

    # Cœur
    if caf > 200:
        today.append(
            "❤️ **Cœur :** > 200 mg (dose élevée). "
            "➡️ Peut augmenter le rythme cardiaque, provoquer nervosité/palpitations. Réduis progressivement."
        )
    if palpitations == 1:
        today.append(
            "❤️ **Palpitations :** signalées aujourd’hui. "
            "➡️ Réduis la caféine, évite les énergétiques, hydrate-toi. Si ça se répète souvent, avis médical."
        )

    # Concentration
    if 80 <= caf <= 150:
        today.append(
            "🎯 **Concentration :** 80–150 mg est souvent une zone ‘utile’. "
            "➡️ Préfère des petites doses réparties plutôt qu’une grosse dose."
        )
    if caf > 200:
        today.append(
            "⚡ **Concentration :** > 200 mg peut donner l’effet inverse : agitation, difficulté à se concentrer, ‘crash’. "
            "➡️ Diminue la dose ou remplace par thé léger/décaféiné."
        )

    # Anxiété / stress
    if anxiety >= 7 and caf >= 150:
        today.append(
            "😰 **Anxiété :** anxiété élevée + caféine ≥ 150 mg. "
            "➡️ Réduis la caféine (surtout énergétiques) et augmente hydratation."
        )
    if stress >= 7 and caf >= 150:
        today.append(
            "🧩 **Stress :** stress élevé + caféine élevée peut amplifier la tension. "
            "➡️ Pause + respiration + éviter une dose tardive."
        )

    # Symptômes
    if headache == 1:
        today.append("🤕 **Maux de tête :** parfois liés à caféine + déshydratation + manque de sommeil. ➡️ Eau + sommeil + réduction progressive.")
    if irritability == 1:
        today.append("😤 **Irritabilité :** souvent liée à excès de caféine ou sommeil faible. ➡️ Ajuster dose et éviter l’après-midi/soir.")
    if digestive == 1:
        today.append("🫃 **Digestif :** la caféine peut irriter l’estomac. ➡️ Évite à jeun et réduis la dose.")

    # Sensibilité
    if sensitivity.lower() == "forte" and caf >= 150:
        today.append("🧬 **Sensibilité forte :** essaie de viser **≤ 150 mg/jour** et observe l’effet sur sommeil/anxiété.")
    if sensitivity.lower() == "faible" and caf > 300:
        today.append("🧬 **Même sensibilité faible :** > 300 mg/jour augmente quand même les risques. ➡️ Revenir vers **200–250 mg max**.")

    if not today:
        today.append("✅ Rien d’alarmant détecté selon les seuils. ➡️ Garde une consommation modérée et une dernière prise assez tôt.")

    # Tendances (7 derniers jours si possible)
    patterns = []
    last7 = df.tail(7).copy()
    if len(last7) >= 3:
        last7["caffeine_mg_total"] = pd.to_numeric(last7["caffeine_mg_total"], errors="coerce")
        last7["sleep_hours"] = pd.to_numeric(last7["sleep_hours"], errors="coerce")
        last7["last_caffeine_hour"] = pd.to_numeric(last7["last_caffeine_hour"], errors="coerce")

        high_caf_days = int((last7["caffeine_mg_total"] > 200).sum())
        low_sleep_days = int((last7["sleep_hours"] < 7).sum())
        late_days = int((last7["last_caffeine_hour"] >= 17).sum())

        if high_caf_days >= 3:
            patterns.append(f"📌 **Tendance :** {high_caf_days} jours/7 avec caféine > 200 mg. ➡️ Objectif : ≤ 200 mg la plupart des jours.")
        if late_days >= 3:
            patterns.append(f"📌 **Tendance :** {late_days} jours/7 avec dernière prise ≥ 17h. ➡️ Avancer l’heure est souvent le changement le plus efficace.")
        if low_sleep_days >= 3:
            patterns.append(f"📌 **Tendance :** {low_sleep_days} jours/7 avec sommeil < 7h. ➡️ Stabiliser l’heure de coucher pour casser le cercle caféine-fatigue.")

    if not patterns:
        patterns.append("Pas assez de données (≥ 3 jours) pour dégager une tendance fiable.")

    return {"summary": summary, "today": today, "patterns": patterns}


# -----------------------------
# App Start
# -----------------------------
ensure_data_files()

if "page" not in st.session_state:
    st.session_state.page = PAGES[0]

st.title("☕ Étude : consommation quotidienne de caféine chez les jeunes")
st.caption("Multi-participants (IDs) • Stockage CSV • Calcul automatique (caféine + sommeil) • Recommandations")

# Sidebar navigation (Dashboard + Export supprimés)
selected = st.sidebar.radio("Navigation", PAGES, index=PAGES.index(st.session_state.page))
st.session_state.page = selected
page = st.session_state.page

participants = load_participants()
logs = load_logs()
participant_ids = participants["participant_id"].tolist() if not participants.empty else []


# -----------------------------
# Page 1: Participants
# (partie droite supprimée + bouton pour passer à l'autre page)
# -----------------------------
if page == "1) Participants":
    st.subheader("1) Ajouter un participant")

    existing_ids = set(participant_ids)
    auto_id = next_participant_id(existing_ids) if existing_ids else "P001"

    with st.form("add_participant"):
        pid = st.text_input("Participant ID", value=auto_id).strip().upper()
        age = st.number_input("Âge", min_value=12, max_value=30, value=20)
        sex = st.selectbox("Sexe (optionnel)", ["", "F", "M", "Autre"])
        sensitivity = st.selectbox("Sensibilité caféine", ["Faible", "Moyenne", "Forte"])
        screen_time = st.selectbox(
            "Temps écran après 21h (téléphone, ordinateur, tablette, TV…) (optionnel)",
            ["", "0–60 min", "1–2h", ">2h"],
        )
        sport = st.selectbox("Sport (optionnel)", ["", "Oui", "Non"])
        add_btn = st.form_submit_button("Enregistrer")

    if add_btn:
        if not pid:
            st.error("Participant ID est obligatoire.")
        elif pid in existing_ids:
            st.error("Cet ID existe déjà. Choisis un autre ID.")
        else:
            new_row = {
                "participant_id": pid,
                "age": int(age),
                "sex": sex,
                "sensitivity": sensitivity,
                "screen_time_evening": screen_time,
                "sport": sport,
                "created_at": datetime.now().isoformat(timespec="seconds"),
            }
            participants = pd.concat([participants, pd.DataFrame([new_row])], ignore_index=True)
            save_participants(participants)
            st.success(f"✅ Participant {pid} ajouté.")
            st.rerun()

    st.divider()
    st.subheader("Liste des participants")
    participants = load_participants()
    if participants.empty:
        st.info("Aucun participant pour le moment.")
    else:
        st.dataframe(participants, use_container_width=True)

    st.divider()
    if st.button("➡️ Passer au Journal quotidien", type="primary"):
        st.session_state.page = "2) Journal quotidien"
        st.rerun()


# -----------------------------
# Page 2: Journal quotidien
# - Heures: choix 1..23
# - Durée calculée automatiquement à partir des heures choisies
# - Boissons: choix simples (nb de tasses/canettes/portions)
# - Bouton pour passer à l'autre navigation
# -----------------------------
elif page == "2) Journal quotidien":
    st.subheader("2) Journal quotidien (saisie + calculs automatiques)")

    if participants.empty:
        st.warning("Ajoute d’abord des participants dans la page 1).")
    else:
        left, right = st.columns([1.25, 0.75])

        with left:
            st.markdown("### 🧾 Saisie du jour")

            with st.form("daily_entry"):
                pid = st.selectbox("Participant ID", participant_ids, index=0)
                entry_date = st.date_input("Date", value=date.today())

                st.markdown("#### Boissons consommées (simple)")
                st.caption("Choisis le **nombre de tasses/canettes/portions**. L’app calcule automatiquement les mg.")
                unit_counts = {}
                ucols = st.columns(2)
                items = list(UNIT_OPTIONS.items())
                for i, (label, mg_unit) in enumerate(items):
                    with ucols[i % 2]:
                        unit_counts[label] = st.selectbox(
                            f"{label} (≈ {mg_unit} mg / unité)",
                            [0, 1, 2, 3, 4, 5],
                            index=0,
                            key=f"unit_{label}",
                        )

                st.markdown("#### Heure de dernière prise")
                last_caffeine_hour = st.selectbox(
                    "Dernière prise de caféine",
                    HOURS,
                    index=HOURS.index(16) if 16 in HOURS else 0,
                    format_func=lambda h: f"{h}h",
                )

                st.markdown("#### Sommeil (calcul automatique)")
                bed_hour = st.selectbox(
                    "Heure de coucher",
                    HOURS,
                    index=HOURS.index(23) if 23 in HOURS else len(HOURS) - 1,
                    format_func=lambda h: f"{h}h",
                )
                wake_hour = st.selectbox(
                    "Heure de réveil",
                    HOURS,
                    index=HOURS.index(7) if 7 in HOURS else 0,
                    format_func=lambda h: f"{h}h",
                )

                # Calcul automatique (mise à jour selon les heures choisies)
                sleep_h = compute_sleep_hours_from_hours(bed_hour, wake_hour)
                st.info(f"🕒 Durée de sommeil calculée : **{sleep_h:.1f} h** (de {bed_hour}h à {wake_hour}h)")

                sleep_quality = st.slider("Qualité de sommeil (1–5)", 1, 5, 3)
                stress = st.slider("Stress (1–10)", 1, 10, 5)
                anxiety = st.slider("Anxiété (1–10)", 1, 10, 4)
                focus = st.slider("Concentration (1–10)", 1, 10, 6)

                st.markdown("#### Symptômes")
                sym_values = {}
                sym_cols = st.columns(2)
                for i, (sym_key, sym_label) in enumerate(SYMPTOMS):
                    with sym_cols[i % 2]:
                        sym_values[sym_key] = st.checkbox(sym_label)

                submit = st.form_submit_button("Enregistrer")

            if submit:
                caf_total, detail = compute_caffeine_from_units(unit_counts)

                # reload logs (safe)
                logs = load_logs()

                # duplicate check
                if not logs.empty:
                    dup = logs[(logs["participant_id"] == pid) & (logs["date"] == entry_date)]
                    if not dup.empty:
                        st.error(
                            "Une saisie existe déjà pour ce participant à cette date. "
                            "➡️ Supprime/édite la ligne directement dans data/daily_logs.csv."
                        )
                    else:
                        new_row = {
                            "date": entry_date,
                            "participant_id": pid,
                            "caffeine_mg_total": caf_total,
                            "last_caffeine_hour": int(last_caffeine_hour),
                            "bed_hour": int(bed_hour),
                            "wake_hour": int(wake_hour),
                            "sleep_hours": float(sleep_h),
                            "sleep_quality_1_5": int(sleep_quality),
                            "stress_1_10": int(stress),
                            "anxiety_1_10": int(anxiety),
                            "focus_1_10": int(focus),
                            "palpitations": int(sym_values["palpitations"]),
                            "headache": int(sym_values["headache"]),
                            "irritability": int(sym_values["irritability"]),
                            "digestive": int(sym_values["digestive"]),
                            "drinks_detail": detail,
                            "created_at": datetime.now().isoformat(timespec="seconds"),
                        }
                        logs = pd.concat([logs, pd.DataFrame([new_row])], ignore_index=True)
                        save_logs(logs)
                        st.success(
                            f"✅ Enregistré: {pid} • {entry_date.isoformat()} • "
                            f"{caf_total} mg • Sommeil {sleep_h:.1f} h"
                        )
                else:
                    new_row = {
                        "date": entry_date,
                        "participant_id": pid,
                        "caffeine_mg_total": caf_total,
                        "last_caffeine_hour": int(last_caffeine_hour),
                        "bed_hour": int(bed_hour),
                        "wake_hour": int(wake_hour),
                        "sleep_hours": float(sleep_h),
                        "sleep_quality_1_5": int(sleep_quality),
                        "stress_1_10": int(stress),
                        "anxiety_1_10": int(anxiety),
                        "focus_1_10": int(focus),
                        "palpitations": int(sym_values["palpitations"]),
                        "headache": int(sym_values["headache"]),
                        "irritability": int(sym_values["irritability"]),
                        "digestive": int(sym_values["digestive"]),
                        "drinks_detail": detail,
                        "created_at": datetime.now().isoformat(timespec="seconds"),
                    }
                    logs = pd.concat([logs, pd.DataFrame([new_row])], ignore_index=True)
                    save_logs(logs)
                    st.success(
                        f"✅ Enregistré: {pid} • {entry_date.isoformat()} • "
                        f"{caf_total} mg • Sommeil {sleep_h:.1f} h"
                    )

            st.divider()
            if st.button("➡️ Passer aux Recommandations", type="primary"):
                st.session_state.page = "3) Recommandations"
                st.rerun()

        with right:
            st.markdown("### 🔎 Dernières saisies")
            logs = load_logs()
            if logs.empty:
                st.info("Aucune saisie pour le moment.")
            else:
                tmp = logs.copy()
                tmp["date"] = pd.to_datetime(tmp["date"], errors="coerce")
                tmp = tmp.sort_values("date", ascending=False).head(10)
                tmp["date"] = tmp["date"].dt.date
                st.dataframe(tmp, use_container_width=True)


# -----------------------------
# Page 3: Recommandations
# -----------------------------
elif page == "3) Recommandations":
    st.subheader("3) Recommandations (par participant)")

    logs = load_logs()
    participants = load_participants()
    participant_ids = participants["participant_id"].tolist() if not participants.empty else []

    if participants.empty or logs.empty:
        st.info("Ajoute des participants et des saisies pour voir les recommandations.")
    else:
        pid = st.selectbox("Choisir participant", participant_ids)
        dfp = logs[logs["participant_id"] == pid].copy()

        if dfp.empty:
            st.warning("Aucune donnée pour ce participant.")
        else:
            min_d = dfp["date"].min()
            max_d = dfp["date"].max()
            start_date, end_date = st.date_input("Période d’analyse", value=(min_d, max_d))
            dff = dfp[(dfp["date"] >= start_date) & (dfp["date"] <= end_date)].copy()

            prow = participants[participants["participant_id"] == pid]
            prow = prow.iloc[0] if not prow.empty else None

            pack = build_recommendations(prow, dff)

            st.markdown("### 📌 Résumé")
            for s in pack["summary"]:
                st.markdown(f"- {s}")

            st.markdown("### ✅ Conseils clairs (basés sur la dernière saisie)")
            for r in pack["today"]:
                st.markdown(f"- {r}")

            st.markdown("### 📈 Tendances & conseils (sur la période)")
            for p in pack["patterns"]:
                st.markdown(f"- {p}")

            st.divider()
            if st.button("⬅️ Retour au Journal quotidien"):
                st.session_state.page = "2) Journal quotidien"
                st.rerun()

st.sidebar.markdown("---")
st.sidebar.caption("Tu peux ajuster les mg/unité dans UNIT_OPTIONS selon ton protocole.")
