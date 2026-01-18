# app.py
# Streamlit app: Étude Caféine (multi-participants) + stockage CSV + calcul automatique + recommandations (améliorées)
# Run:
#   pip install streamlit pandas
#   streamlit run app.py

import os
from datetime import datetime, date, timedelta

import pandas as pd
import streamlit as st

# -----------------------------
# Config
# -----------------------------
st.set_page_config(page_title="Étude Caféine - Jeunes", layout="wide")

DATA_DIR = "data"
PARTICIPANTS_CSV = os.path.join(DATA_DIR, "participants.csv")
LOGS_CSV = os.path.join(DATA_DIR, "daily_logs.csv")

# Catalogue caféine (mg) par unité standard (modifiable)
CAFFEINE_CATALOG = {
    "Espresso (30 ml)": 75,
    "Café filtre (250 ml)": 95,
    "Café instantané (250 ml)": 60,
    "Thé noir (250 ml)": 45,
    "Thé vert (250 ml)": 30,
    "Boisson énergétique (250 ml)": 80,
    "Cola (330 ml)": 35,
    "Chocolat (50 g)": 10,
}

# Symptômes avec traduction en anglais entre ()
SYMPTOMS = [
    ("palpitations", "Palpitations (Heart palpitations)"),
    ("headache", "Maux de tête (Headache)"),
    ("irritability", "Irritabilité (Irritability)"),
    ("digestive", "Troubles digestifs (Digestive issues)"),
]

# Heures proposées (0–23). Si tu veux strictement 1–23, remplace par range(1, 24).
HOURS = list(range(0, 24))


# -----------------------------
# Helpers (I/O)
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
                # symptoms
                "palpitations",
                "headache",
                "irritability",
                "digestive",
                # audit
                "drinks_detail",
                "created_at",
            ]
        ).to_csv(LOGS_CSV, index=False)


def load_participants() -> pd.DataFrame:
    df = pd.read_csv(PARTICIPANTS_CSV)
    if df.empty:
        return df
    df["participant_id"] = df["participant_id"].astype(str).str.upper()
    return df


def load_logs() -> pd.DataFrame:
    df = pd.read_csv(LOGS_CSV)
    if df.empty:
        return df
    df["participant_id"] = df["participant_id"].astype(str).str.upper()
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date
    return df


def save_participants(df: pd.DataFrame):
    df.to_csv(PARTICIPANTS_CSV, index=False)


def save_logs(df: pd.DataFrame):
    out = df.copy()
    if "date" in out.columns:
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
# Helpers (Calculs)
# -----------------------------
def compute_sleep_hours_from_hours(bed_hour: int, wake_hour: int) -> float:
    """
    Calcul de la durée de sommeil en heures à partir de 2 entiers (0..23),
    en gérant le passage par minuit.
    Ex: 23 -> 7 = 8h
    """
    bed = int(bed_hour)
    wake = int(wake_hour)
    if wake <= bed:
        wake += 24
    sleep_hours = wake - bed
    return round(float(sleep_hours), 2)


def compute_caffeine_total(drink_qty: dict) -> tuple[int, str]:
    total = 0
    parts = []
    for drink, qty in drink_qty.items():
        qty = int(qty)
        if qty <= 0:
            continue
        mg_unit = CAFFEINE_CATALOG.get(drink, 0)
        mg = qty * mg_unit
        total += mg
        parts.append(f"{drink} x{qty} ({mg} mg)")
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
# Recommandations (améliorées)
# -----------------------------
def build_recommendations(participant_row: pd.Series | None, logs_df: pd.DataFrame) -> dict:
    """
    Retourne un dictionnaire avec:
    - summary: résumé simple
    - today: recommandations basées sur la dernière saisie
    - patterns: recommandations basées sur tendances (plusieurs jours)
    """
    if logs_df.empty:
        return {
            "summary": ["Aucune donnée pour ce participant."],
            "today": [],
            "patterns": [],
        }

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

    # --- Résumé
    summary = [
        f"**Dernière date :** {latest.get('date')}",
        f"**Caféine totale :** {int(caf)} mg (**niveau : {level}**)",
        f"**Dernière prise :** {last_h}h",
        f"**Sommeil :** {sleep_h:.1f} h (qualité {safe_int(latest.get('sleep_quality_1_5'), 0)}/5)",
        f"**Anxiété :** {anxiety}/10 • **Stress :** {stress}/10 • **Concentration :** {focus}/10",
    ]
    if sensitivity:
        summary.append(f"**Sensibilité déclarée :** {sensitivity}")

    # --- Conseils du jour (clairs & simples)
    today = []

    # Effets sur le sommeil / cerveau
    if last_h >= 17 and caf >= 100:
        today.append(
            "🧠 **Cerveau & sommeil :** ta dernière prise est tardive (≥ 17h). "
            "La caféine peut retarder l’endormissement et réduire la qualité du sommeil. "
            "➡️ Essaie de terminer la caféine avant **16–17h**."
        )
    if sleep_h < 7:
        today.append(
            "🌙 **Sommeil :** tu as dormi moins de 7h. "
            "➡️ Priorise la récupération (routine de coucher, écran ↓, caféine plus tôt). "
            "Le manque de sommeil augmente fatigue, stress et baisse la mémoire/concentration."
        )

    # Effets sur le cœur
    if caf > 200:
        today.append(
            "❤️ **Cœur :** dose élevée (> 200 mg). Cela peut augmenter le rythme cardiaque, provoquer nervosité et palpitations. "
            "➡️ Réduis progressivement (ex: -25 à -50 mg par jour) et évite de concentrer toute la caféine en une seule prise."
        )
    if palpitations == 1:
        today.append(
            "❤️ **Cœur :** palpitations signalées aujourd’hui. "
            "➡️ Diminue la caféine, évite les boissons énergétiques, hydrate-toi bien. "
            "Si ça se répète souvent ou devient gênant, il vaut mieux demander avis médical."
        )

    # Effets sur concentration
    if 80 <= caf <= 150:
        today.append(
            "🎯 **Concentration :** ta dose est dans une zone souvent utile pour l’alerte (≈ 80–150 mg). "
            "➡️ Pour rester stable, préfère des petites doses réparties plutôt qu’un “gros shot”."
        )
    if caf > 200:
        today.append(
            "⚡ **Concentration :** au-dessus de 200 mg, on voit souvent des effets inverses : agitation, difficulté à se concentrer, “crash”. "
            "➡️ Diminue la dose ou remplace une boisson par décaféiné/thé léger."
        )

    # Stress/anxiété
    if anxiety >= 7 and caf >= 150:
        today.append(
            "😰 **Anxiété :** anxiété élevée + caféine modérée/forte. "
            "➡️ Réduis la caféine, surtout les énergétiques, et essaie une alternative (eau, tisane)."
        )
    if stress >= 7 and caf >= 150:
        today.append(
            "🧩 **Stress :** stress élevé + caféine élevée peut amplifier la tension. "
            "➡️ Fais une pause (respiration 2–3 minutes), hydrate-toi, et évite une nouvelle dose tardive."
        )

    # Symptômes secondaires
    if headache == 1:
        today.append(
            "🤕 **Maux de tête :** parfois liés à excès de caféine, déshydratation, ou manque de sommeil. "
            "➡️ Eau + sommeil + réduction progressive si consommation élevée."
        )
    if irritability == 1:
        today.append(
            "😤 **Irritabilité :** peut augmenter quand la caféine est trop forte ou quand le sommeil est faible. "
            "➡️ Ajuste la dose et évite les prises tardives."
        )
    if digestive == 1:
        today.append(
            "🫃 **Digestif :** le café/caféine peut irriter l’estomac chez certains. "
            "➡️ Évite à jeun et préfère une dose plus faible."
        )

    # Sensibilité
    if sensitivity.lower() == "forte" and caf >= 150:
        today.append(
            "🧬 **Sensibilité forte :** tu pourrais ressentir les effets avec des doses plus faibles. "
            "➡️ Essaie de rester ≤ **150 mg/jour** et observe l’impact sur le sommeil et l’anxiété."
        )
    if sensitivity.lower() == "faible" and caf > 300:
        today.append(
            "🧬 **Même si sensibilité faible :** >300 mg/jour augmente quand même le risque (sommeil, anxiété, cœur). "
            "➡️ Essaie de revenir vers **200–250 mg max**."
        )

    if not today:
        today.append(
            "✅ **Globalement :** rien d’alarmant détecté aujourd’hui selon les seuils. "
            "➡️ Garde une consommation modérée et une dernière prise assez tôt."
        )

    # --- Tendances (plusieurs jours)
    patterns = []
    last7 = df.tail(7).copy()
    last7["caffeine_mg_total"] = pd.to_numeric(last7["caffeine_mg_total"], errors="coerce")
    last7["sleep_hours"] = pd.to_numeric(last7["sleep_hours"], errors="coerce")
    last7["sleep_quality_1_5"] = pd.to_numeric(last7["sleep_quality_1_5"], errors="coerce")
    last7["anxiety_1_10"] = pd.to_numeric(last7["anxiety_1_10"], errors="coerce")
    last7["stress_1_10"] = pd.to_numeric(last7["stress_1_10"], errors="coerce")

    if len(last7) >= 3:
        low_sleep_days = int((last7["sleep_hours"] < 7).sum())
        high_caf_days = int((last7["caffeine_mg_total"] > 200).sum())
        late_days = int((pd.to_numeric(last7["last_caffeine_hour"], errors="coerce") >= 17).sum())

        if high_caf_days >= 3:
            patterns.append(
                f"📌 **Tendance (7 derniers jours) :** {high_caf_days} jours avec caféine > 200 mg. "
                "➡️ Objectif simple : réduire à **≤ 200 mg** la plupart des jours."
            )
        if late_days >= 3:
            patterns.append(
                f"📌 **Tendance :** {late_days} jours avec dernière prise ≥ 17h. "
                "➡️ Avancer la dernière prise est souvent le changement le plus efficace pour améliorer le sommeil."
            )
        if low_sleep_days >= 3:
            patterns.append(
                f"📌 **Tendance :** {low_sleep_days} jours avec sommeil < 7h. "
                "➡️ Le manque de sommeil peut augmenter envie de caféine → cercle vicieux. "
                "Essaye d’abord de stabiliser l’heure de coucher."
            )

        # comparaison faible vs élevé si on a assez
        last7["caf_bin"] = pd.cut(
            last7["caffeine_mg_total"],
            bins=[-1, 99, 200, 10_000],
            labels=["Faible (<100)", "Moyen (100–200)", "Élevé (>200)"],
        )
        g = last7.groupby("caf_bin", observed=True).agg(
            sleep_q=("sleep_quality_1_5", "mean"),
            sleep_h=("sleep_hours", "mean"),
            anxiety=("anxiety_1_10", "mean"),
            n=("caf_bin", "size"),
        ).reset_index()

        if not g.empty and g["n"].sum() >= 5:
            # pick any present bins
            try:
                best = g.dropna(subset=["sleep_q"]).sort_values("sleep_q", ascending=False).iloc[0]
                worst = g.dropna(subset=["sleep_q"]).sort_values("sleep_q", ascending=True).iloc[0]
                patterns.append(
                    f"📊 **Comparaison (sur tes données) :** meilleure qualité de sommeil en **{best['caf_bin']}** "
                    f"(≈ {best['sleep_q']:.2f}/5), plus faible en **{worst['caf_bin']}** (≈ {worst['sleep_q']:.2f}/5)."
                )
            except Exception:
                pass

    if not patterns:
        patterns.append("Pas assez de jours (ou trop de valeurs manquantes) pour dégager une tendance fiable.")

    return {"summary": summary, "today": today, "patterns": patterns}


# -----------------------------
# App start
# -----------------------------
ensure_data_files()
participants = load_participants()
logs = load_logs()

st.title("☕ Étude : consommation quotidienne de caféine chez les jeunes")
st.caption("Multi-participants (IDs) • Stockage CSV • Calcul automatique (caféine + sommeil) • Recommandations")

# -----------------------------
# Navigation (Dashboard supprimé)
# + système de 'Suivant' depuis la page Participants
# -----------------------------
PAGES = ["1) Participants", "2) Journal quotidien", "3) Recommandations", "4) Export & Qualité"]

if "page" not in st.session_state:
    st.session_state.page = PAGES[0]

# Sidebar navigation
selected = st.sidebar.radio("Navigation", PAGES, index=PAGES.index(st.session_state.page))
st.session_state.page = selected

page = st.session_state.page

participant_ids = participants["participant_id"].tolist() if not participants.empty else []

# -----------------------------
# Page 1: Participants (partie droite supprimée)
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
        screen_time = st.selectbox("Temps écran après 21h (optionnel)", ["", "0–60 min", "1–2h", ">2h"])
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

    # Bouton "Suivant" (passer à la page suivante)
    st.divider()
    if st.button("➡️ Passer au Journal quotidien", type="primary"):
        st.session_state.page = "2) Journal quotidien"
        st.rerun()

# -----------------------------
# Page 2: Journal quotidien (heures en 1..23/0..23)
# -----------------------------
elif page == "2) Journal quotidien":
    st.subheader("2) Journal quotidien (saisie + calculs automatiques)")

    if participants.empty:
        st.warning("Ajoute d’abord des participants dans la page 1).")
    else:
        left, right = st.columns([1.2, 0.8])

        with left:
            st.markdown("### 🧾 Saisie du jour")

            with st.form("daily_entry"):
                pid = st.selectbox("Participant ID", participant_ids, index=0)
                entry_date = st.date_input("Date", value=date.today())

                st.markdown("#### Boissons consommées (calcul automatique en mg)")
                drink_qty = {}
                cols = st.columns(2)
                items = list(CAFFEINE_CATALOG.items())
                for i, (drink, mg_unit) in enumerate(items):
                    with cols[i % 2]:
                        qty = st.number_input(
                            f"{drink}  •  {mg_unit} mg/unité",
                            min_value=0,
                            max_value=20,
                            value=0,
                            step=1,
                            key=f"qty_{drink}",
                        )
                        drink_qty[drink] = qty

                last_caffeine_hour = st.selectbox(
                    "Heure de dernière prise",
                    HOURS,
                    index=HOURS.index(16) if 16 in HOURS else 0,
                    format_func=lambda h: f"{h}h",
                )

                st.markdown("#### Sommeil (calcul automatique)")
                bed_hour = st.selectbox(
                    "Heure de coucher",
                    HOURS,
                    index=HOURS.index(23) if 23 in HOURS else 0,
                    format_func=lambda h: f"{h}h",
                )
                wake_hour = st.selectbox(
                    "Heure de réveil",
                    HOURS,
                    index=HOURS.index(7) if 7 in HOURS else 0,
                    format_func=lambda h: f"{h}h",
                )

                sleep_h = compute_sleep_hours_from_hours(bed_hour, wake_hour)
                st.info(f"🕒 Durée de sommeil calculée : **{sleep_h} h**")

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
                caf_total, detail = compute_caffeine_total(drink_qty)

                # Reload logs to avoid stale state
                logs = load_logs()

                # Check duplicates (same participant + date)
                if not logs.empty:
                    dup = logs[(logs["participant_id"] == pid) & (logs["date"] == entry_date)]
                    if not dup.empty:
                        st.error(
                            "Une saisie existe déjà pour ce participant à cette date. "
                            "Va à 'Export & Qualité' pour supprimer/corriger."
                        )
                    else:
                        new_row = {
                            "date": entry_date,
                            "participant_id": pid,
                            "caffeine_mg_total": caf_total,
                            "last_caffeine_hour": int(last_caffeine_hour),
                            "bed_hour": int(bed_hour),
                            "wake_hour": int(wake_hour),
                            "sleep_hours": sleep_h,
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
                            f"{caf_total} mg • Sommeil {sleep_h} h"
                        )
                else:
                    new_row = {
                        "date": entry_date,
                        "participant_id": pid,
                        "caffeine_mg_total": caf_total,
                        "last_caffeine_hour": int(last_caffeine_hour),
                        "bed_hour": int(bed_hour),
                        "wake_hour": int(wake_hour),
                        "sleep_hours": sleep_h,
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
                        f"{caf_total} mg • Sommeil {sleep_h} h"
                    )

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
# Page 3: Recommandations (développées)
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
            # période d'analyse
            min_d = dfp["date"].min()
            max_d = dfp["date"].max()
            start_date, end_date = st.date_input("Période d’analyse", value=(min_d, max_d))
            dff = dfp[(dfp["date"] >= start_date) & (dfp["date"] <= end_date)].copy()

            # get participant profile row
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

# -----------------------------
# Page 4: Export & Qualité
# -----------------------------
elif page == "4) Export & Qualité":
    st.subheader("4) Export & Qualité des données")

    logs = load_logs()
    participants = load_participants()
    participant_ids = participants["participant_id"].tolist() if not participants.empty else []

    if logs.empty:
        st.info("Aucune donnée à exporter.")
    else:
        c1, c2, c3 = st.columns([1, 1, 1])
        with c1:
            pid_choice = st.selectbox("Participant (export)", ["Tous"] + participant_ids, key="export_pid")
        with c2:
            min_d = logs["date"].min()
            max_d = logs["date"].max()
            start_date, end_date = st.date_input("Période (export)", value=(min_d, max_d), key="export_period")
        with c3:
            st.caption("Tu peux supprimer des lignes en cas d’erreur de saisie.")

        df = logs[(logs["date"] >= start_date) & (logs["date"] <= end_date)].copy()
        if pid_choice != "Tous":
            df = df[df["participant_id"] == pid_choice].copy()

        st.markdown("### ✅ Contrôles qualité")
        dup = df.duplicated(subset=["participant_id", "date"], keep=False)
        n_dup = int(dup.sum())
        if n_dup > 0:
            st.warning(f"Doublons détectés (participant + date) : {n_dup}")
            st.dataframe(df[dup].sort_values(["participant_id", "date"]), use_container_width=True)
        else:
            st.success("Pas de doublons (participant + date) sur la sélection.")

        df["caffeine_mg_total"] = pd.to_numeric(df["caffeine_mg_total"], errors="coerce")
        out = df[df["caffeine_mg_total"] > 800]
        if not out.empty:
            st.warning("Valeurs caféine très élevées (> 800 mg) détectées : vérifie si c’est correct.")
            st.dataframe(out, use_container_width=True)

        st.markdown("### 📋 Données sélectionnées")
        st.dataframe(df.sort_values(["participant_id", "date"]), use_container_width=True)

        st.markdown("### ⬇️ Export CSV")
        export_df = df.copy()
        export_df["date"] = export_df["date"].apply(lambda d: d.isoformat() if isinstance(d, date) else str(d))
        csv_bytes = export_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Télécharger l’export CSV",
            data=csv_bytes,
            file_name=f"export_caffeine_{pid_choice}_{start_date.isoformat()}_{end_date.isoformat()}.csv",
            mime="text/csv",
        )

        st.markdown("### 🗑️ Supprimer une saisie (corriger une erreur)")
        st.caption("Suppression basée sur (participant_id + date).")

        del_c1, del_c2 = st.columns([1, 1])
        with del_c1:
            del_pid = st.selectbox("Participant à corriger", participant_ids, key="del_pid")
        with del_c2:
            pid_dates = logs[logs["participant_id"] == del_pid]["date"].sort_values().tolist()
            if pid_dates:
                del_date = st.selectbox("Date à supprimer", pid_dates, key="del_date")
            else:
                del_date = None
                st.info("Ce participant n’a pas de saisies.")

        if st.button("Supprimer la saisie", type="secondary", disabled=(del_date is None)):
            logs = logs[~((logs["participant_id"] == del_pid) & (logs["date"] == del_date))].reset_index(drop=True)
            save_logs(logs)
            st.success(f"✅ Saisie supprimée: {del_pid} • {del_date}")
            st.rerun()

# Footer
st.sidebar.markdown("---")
st.sidebar.caption("Tu peux ajuster CAFFEINE_CATALOG (mg) selon ton protocole.")
