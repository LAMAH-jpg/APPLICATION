# app.py
# Streamlit app: Étude Caféine (multi-participants) + stockage CSV + calcul automatique + recommandations
# Run:
#   pip install streamlit pandas
#   streamlit run app.py

import os
from datetime import datetime, date, time, timedelta

import pandas as pd
import streamlit as st

# -----------------------------
# Config
# -----------------------------
st.set_page_config(page_title="Étude Caféine - Jeunes", layout="wide")

DATA_DIR = "data"
PARTICIPANTS_CSV = os.path.join(DATA_DIR, "participants.csv")
LOGS_CSV = os.path.join(DATA_DIR, "daily_logs.csv")

# Catalogue caféine (mg) par unité standard
# (Tu peux ajuster selon tes références / ton protocole)
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

SYMPTOMS = [
    ("palpitations", "Palpitations"),
    ("headache", "Maux de tête"),
    ("irritability", "Irritabilité"),
    ("digestive", "Troubles digestifs"),
]

# -----------------------------
# Helpers
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
                "bed_time",
                "wake_time",
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
                # optional: raw drinks detail (for audit)
                "drinks_detail",
                "created_at",
            ]
        ).to_csv(LOGS_CSV, index=False)


def load_participants() -> pd.DataFrame:
    df = pd.read_csv(PARTICIPANTS_CSV)
    if df.empty:
        return df
    # keep types reasonable
    df["participant_id"] = df["participant_id"].astype(str)
    return df


def load_logs() -> pd.DataFrame:
    df = pd.read_csv(LOGS_CSV)
    if df.empty:
        return df
    df["participant_id"] = df["participant_id"].astype(str)
    # parse date column safely
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date
    return df


def save_participants(df: pd.DataFrame):
    df.to_csv(PARTICIPANTS_CSV, index=False)


def save_logs(df: pd.DataFrame):
    # store date as ISO string for portability
    out = df.copy()
    if "date" in out.columns:
        out["date"] = out["date"].apply(lambda d: d.isoformat() if isinstance(d, date) else d)
    out.to_csv(LOGS_CSV, index=False)


def next_participant_id(existing_ids) -> str:
    # Generate P001, P002, ...
    max_n = 0
    for pid in existing_ids:
        pid = str(pid).strip().upper()
        if pid.startswith("P") and pid[1:].isdigit():
            max_n = max(max_n, int(pid[1:]))
    return f"P{max_n+1:03d}"


def compute_sleep_hours(bed: time, wake: time) -> float:
    # Compute duration, handling crossing midnight
    bed_dt = datetime.combine(date.today(), bed)
    wake_dt = datetime.combine(date.today(), wake)
    if wake_dt <= bed_dt:
        wake_dt += timedelta(days=1)
    delta = wake_dt - bed_dt
    hours = delta.total_seconds() / 3600.0
    # clamp to realistic range (optional)
    return round(hours, 2)


def compute_caffeine_total(drink_qty: dict) -> tuple[int, str]:
    """
    drink_qty: {drink_name: qty_int}
    returns: (mg_total_int, detail_str)
    """
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
    detail = " | ".join(parts) if parts else ""
    return int(total), detail


def risk_level(caffeine_mg_total: float) -> str:
    # Simple binning (modifiable)
    if caffeine_mg_total < 100:
        return "Faible"
    if caffeine_mg_total <= 200:
        return "Moyen"
    return "Élevé"


def recommendations_for_row(row: pd.Series) -> list[str]:
    recs = []

    caf = float(row.get("caffeine_mg_total", 0) or 0)
    last_h = row.get("last_caffeine_hour", None)
    sleep_h = float(row.get("sleep_hours", 0) or 0)
    anxiety = float(row.get("anxiety_1_10", 0) or 0)
    stress = float(row.get("stress_1_10", 0) or 0)
    palpitations = int(row.get("palpitations", 0) or 0)

    if caf > 200:
        recs.append("Dose élevée aujourd’hui (> 200 mg). Essaie de réduire progressivement (ex: -25 à -50 mg).")

    if last_h is not None and str(last_h).strip() != "":
        try:
            last_h_int = int(float(last_h))
            if last_h_int >= 17 and caf >= 100:
                recs.append("Dernière prise tardive (≥ 17h) : risque de sommeil perturbé. Vise plutôt avant 16–17h.")
        except Exception:
            pass

    if sleep_h < 7:
        recs.append("Sommeil < 7h : priorité à l’hygiène du sommeil (écran ↓ le soir, routine, caféine plus tôt).")

    if anxiety >= 7 and caf >= 150:
        recs.append("Anxiété élevée + caféine modérée/forte : réduis la caféine et évite les boissons énergétiques.")

    if stress >= 7 and caf >= 150:
        recs.append("Stress élevé : privilégie hydratation + pauses, et limite la caféine surtout l’après-midi.")

    if palpitations == 1:
        recs.append("Palpitations signalées : forte sensibilité possible. Diminue la caféine et évite les énergétiques.")

    if not recs:
        recs.append("RAS majeur détecté aujourd’hui. Garde une consommation modérée et une dernière prise assez tôt.")

    return recs


def weekly_insights(logs_df: pd.DataFrame) -> list[str]:
    """
    Produce simple insights from a participant’s filtered logs (at least a few days).
    """
    insights = []
    if logs_df.empty or len(logs_df) < 5:
        return ["Pas assez de données (≥ 5 jours) pour générer des insights fiables."]

    df = logs_df.copy()
    df["caffeine_mg_total"] = pd.to_numeric(df["caffeine_mg_total"], errors="coerce")
    df["sleep_quality_1_5"] = pd.to_numeric(df["sleep_quality_1_5"], errors="coerce")
    df["sleep_hours"] = pd.to_numeric(df["sleep_hours"], errors="coerce")
    df["anxiety_1_10"] = pd.to_numeric(df["anxiety_1_10"], errors="coerce")

    # group by caffeine bin
    df["caf_bin"] = pd.cut(
        df["caffeine_mg_total"],
        bins=[-1, 99, 200, 10_000],
        labels=["Faible (<100)", "Moyen (100–200)", "Élevé (>200)"],
    )

    g = df.groupby("caf_bin", observed=True).agg(
        sleep_hours_mean=("sleep_hours", "mean"),
        sleep_quality_mean=("sleep_quality_1_5", "mean"),
        anxiety_mean=("anxiety_1_10", "mean"),
        n=("caf_bin", "size"),
    ).reset_index()

    if not g.empty:
        # Find best and worst sleep quality by bin (if present)
        valid = g.dropna(subset=["sleep_quality_mean"])
        if len(valid) >= 2:
            best = valid.sort_values("sleep_quality_mean", ascending=False).iloc[0]
            worst = valid.sort_values("sleep_quality_mean", ascending=True).iloc[0]
            insights.append(
                f"Comparaison qualité sommeil : meilleure en **{best['caf_bin']}** "
                f"(moyenne {best['sleep_quality_mean']:.2f}, n={int(best['n'])}), "
                f"plus faible en **{worst['caf_bin']}** "
                f"(moyenne {worst['sleep_quality_mean']:.2f}, n={int(worst['n'])})."
            )

        # Simple correlation hints (Spearman-like quick via pandas corr)
        corr = df[["caffeine_mg_total", "sleep_hours", "sleep_quality_1_5", "anxiety_1_10"]].corr(numeric_only=True)
        if not corr.empty and "caffeine_mg_total" in corr.columns:
            csq = corr.loc["caffeine_mg_total", "sleep_quality_1_5"]
            csh = corr.loc["caffeine_mg_total", "sleep_hours"]
            cax = corr.loc["caffeine_mg_total", "anxiety_1_10"]
            insights.append(f"Corrélation (approx.) caféine ↔ qualité sommeil : **{csq:.2f}**.")
            insights.append(f"Corrélation (approx.) caféine ↔ durée sommeil : **{csh:.2f}**.")
            insights.append(f"Corrélation (approx.) caféine ↔ anxiété : **{cax:.2f}**.")

    if not insights:
        insights.append("Insights non générés (données insuffisantes ou trop de valeurs manquantes).")
    return insights


# -----------------------------
# App start
# -----------------------------
ensure_data_files()

participants = load_participants()
logs = load_logs()

st.title("☕ Étude : consommation quotidienne de caféine chez les jeunes")
st.caption("Multi-participants (IDs) • Stockage CSV • Calcul automatique (caféine + sommeil) • Dashboard + Recommandations")

# Sidebar navigation
page = st.sidebar.radio(
    "Navigation",
    ["1) Participants", "2) Journal quotidien", "3) Dashboard", "4) Recommandations", "5) Export & Qualité"],
)

# Common: Participant selector (used in several pages)
participant_ids = participants["participant_id"].tolist() if not participants.empty else []
default_pid = participant_ids[0] if participant_ids else None

# -----------------------------
# Page 1: Participants
# -----------------------------
if page == "1) Participants":
    st.subheader("1) Gestion des participants (IDs)")

    colA, colB = st.columns([1, 1])

    with colA:
        st.markdown("### ➕ Ajouter un participant")
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

    with colB:
        st.markdown("### 📋 Liste des participants")
        if participants.empty:
            st.info("Aucun participant pour le moment. Ajoute-en un à gauche.")
        else:
            st.dataframe(participants, use_container_width=True)

        st.markdown("### 🗑️ Supprimer un participant (optionnel)")
        if participants.empty:
            st.caption("—")
        else:
            del_pid = st.selectbox("Choisir un ID à supprimer", [""] + participant_ids)
            delete_logs = st.checkbox("Supprimer aussi ses données (daily logs)", value=False)
            if st.button("Supprimer", type="secondary", disabled=(del_pid == "")):
                participants = participants[participants["participant_id"] != del_pid].reset_index(drop=True)
                save_participants(participants)

                if delete_logs and not logs.empty:
                    logs = logs[logs["participant_id"] != del_pid].reset_index(drop=True)
                    save_logs(logs)

                st.success(f"✅ Participant {del_pid} supprimé.")
                st.rerun()

# -----------------------------
# Page 2: Daily Journal
# -----------------------------
elif page == "2) Journal quotidien":
    st.subheader("2) Journal quotidien (saisie + calculs automatiques)")

    if participants.empty:
        st.warning("Ajoute d’abord des participants dans la page 1).")
    else:
        left, right = st.columns([1.1, 0.9])

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
                        qty = st.number_input(f"{drink}  •  {mg_unit} mg/unité", min_value=0, max_value=20, value=0, step=1, key=f"qty_{drink}")
                        drink_qty[drink] = qty

                last_caffeine_hour = st.slider("Heure de dernière prise (0–23)", 0, 23, 16)

                st.markdown("#### Sommeil (calcul automatique)")
                bed_time = st.time_input("Heure de coucher", value=time(23, 30))
                wake_time = st.time_input("Heure de réveil", value=time(7, 0))
                sleep_h = compute_sleep_hours(bed_time, wake_time)
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

                # Check duplicate (same pid + date)
                if not logs.empty:
                    dup = logs[(logs["participant_id"] == pid) & (logs["date"] == entry_date)]
                    if not dup.empty:
                        st.error("Une saisie existe déjà pour ce participant à cette date. Va à 'Export & Qualité' pour corriger/supprimer.")
                    else:
                        new_row = {
                            "date": entry_date,
                            "participant_id": pid,
                            "caffeine_mg_total": caf_total,
                            "last_caffeine_hour": int(last_caffeine_hour),
                            "bed_time": bed_time.strftime("%H:%M"),
                            "wake_time": wake_time.strftime("%H:%M"),
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
                        st.success(f"✅ Enregistré: {pid} • {entry_date.isoformat()} • {caf_total} mg • Sommeil {sleep_h} h")
                else:
                    new_row = {
                        "date": entry_date,
                        "participant_id": pid,
                        "caffeine_mg_total": caf_total,
                        "last_caffeine_hour": int(last_caffeine_hour),
                        "bed_time": bed_time.strftime("%H:%M"),
                        "wake_time": wake_time.strftime("%H:%M"),
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
                    st.success(f"✅ Enregistré: {pid} • {entry_date.isoformat()} • {caf_total} mg • Sommeil {sleep_h} h")

        with right:
            st.markdown("### 🔎 Aperçu (dernières saisies)")
            if logs.empty:
                st.info("Aucune saisie pour le moment.")
            else:
                tmp = logs.copy()
                tmp["date"] = pd.to_datetime(tmp["date"], errors="coerce")
                tmp = tmp.sort_values("date", ascending=False).head(10)
                tmp["date"] = tmp["date"].dt.date
                st.dataframe(tmp, use_container_width=True)

# -----------------------------
# Page 3: Dashboard
# -----------------------------
elif page == "3) Dashboard":
    st.subheader("3) Dashboard (par participant ou global)")

    if logs.empty:
        st.info("Aucune donnée. Ajoute des saisies dans 2) Journal quotidien.")
    else:
        logs2 = logs.copy()

        # Filters
        fcol1, fcol2, fcol3 = st.columns([1, 1, 1])
        with fcol1:
            pid_choice = st.selectbox("Filtrer participant", ["Tous"] + participant_ids)
        with fcol2:
            min_d = logs2["date"].min()
            max_d = logs2["date"].max()
            start_date, end_date = st.date_input("Période", value=(min_d, max_d))
        with fcol3:
            st.caption("Niveaux caféine: <100 faible • 100–200 moyen • >200 élevé")

        # Apply filters
        df = logs2[(logs2["date"] >= start_date) & (logs2["date"] <= end_date)].copy()
        if pid_choice != "Tous":
            df = df[df["participant_id"] == pid_choice].copy()

        if df.empty:
            st.warning("Aucune donnée pour ces filtres.")
        else:
            # numeric conversions
            for c in ["caffeine_mg_total", "sleep_hours", "sleep_quality_1_5", "stress_1_10", "anxiety_1_10", "focus_1_10"]:
                df[c] = pd.to_numeric(df[c], errors="coerce")
            df = df.sort_values("date")

            # KPIs
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Saisies", int(len(df)))
            k2.metric("Caféine moyenne (mg)", f"{df['caffeine_mg_total'].mean():.1f}")
            k3.metric("Sommeil moyen (h)", f"{df['sleep_hours'].mean():.2f}")
            k4.metric("Anxiété moyenne", f"{df['anxiety_1_10'].mean():.2f}")

            st.markdown("### 📈 Tendances")
            c1, c2 = st.columns(2)
            with c1:
                st.write("Caféine (mg) vs Durée de sommeil (h)")
                st.line_chart(df.set_index("date")[["caffeine_mg_total", "sleep_hours"]])
            with c2:
                st.write("Caféine (mg) vs Anxiété / Stress")
                st.line_chart(df.set_index("date")[["caffeine_mg_total", "anxiety_1_10", "stress_1_10"]])

            st.markdown("### 📊 Répartition des niveaux de caféine")
            df["caf_level"] = df["caffeine_mg_total"].apply(risk_level)
            st.bar_chart(df["caf_level"].value_counts().reindex(["Faible", "Moyen", "Élevé"]).fillna(0))

            st.markdown("### 🔗 Corrélations (approx.)")
            corr = df[["caffeine_mg_total", "sleep_hours", "sleep_quality_1_5", "stress_1_10", "anxiety_1_10", "focus_1_10"]].corr(numeric_only=True)
            st.dataframe(corr, use_container_width=True)

            st.markdown("### 📋 Données filtrées")
            st.dataframe(df, use_container_width=True)

# -----------------------------
# Page 4: Recommendations
# -----------------------------
elif page == "4) Recommandations":
    st.subheader("4) Recommandations (par participant)")

    if logs.empty or participants.empty:
        st.info("Ajoute des participants et des saisies pour voir les recommandations.")
    else:
        pid = st.selectbox("Choisir participant", participant_ids)
        dfp = logs[logs["participant_id"] == pid].copy()

        if dfp.empty:
            st.warning("Aucune donnée pour ce participant.")
        else:
            dfp = dfp.sort_values("date")
            latest = dfp.iloc[-1]

            st.markdown("### ✅ Recommandations du dernier jour")
            left, right = st.columns([1, 1])
            with left:
                st.write(f"**Date :** {latest['date']}")
                st.write(f"**Caféine :** {latest['caffeine_mg_total']} mg")
                st.write(f"**Dernière prise :** {latest['last_caffeine_hour']}h")
                st.write(f"**Sommeil :** {latest['sleep_hours']} h (qualité {latest['sleep_quality_1_5']}/5)")
                st.write(f"**Anxiété :** {latest['anxiety_1_10']}/10 • **Stress :** {latest['stress_1_10']}/10 • **Focus :** {latest['focus_1_10']}/10")
                if str(latest.get("drinks_detail", "")).strip():
                    st.caption(f"Détails boissons: {latest['drinks_detail']}")
            with right:
                recs = recommendations_for_row(latest)
                for r in recs:
                    st.markdown(f"- {r}")

            st.markdown("### 📌 Insights (sur la période)")
            # Allow period selection
            min_d = dfp["date"].min()
            max_d = dfp["date"].max()
            start_date, end_date = st.date_input("Période d’analyse", value=(min_d, max_d), key="insights_period")
            dff = dfp[(dfp["date"] >= start_date) & (dfp["date"] <= end_date)].copy()

            insights = weekly_insights(dff)
            for ins in insights:
                st.markdown(f"- {ins}")

            st.markdown("### ⚠️ Alerte simple (si cumul de signes)")
            # Simple multi-day check: last 3 entries
            last_n = dff.sort_values("date").tail(3).copy()
            if len(last_n) >= 3:
                last_n["sleep_hours"] = pd.to_numeric(last_n["sleep_hours"], errors="coerce")
                last_n["caffeine_mg_total"] = pd.to_numeric(last_n["caffeine_mg_total"], errors="coerce")
                last_n["anxiety_1_10"] = pd.to_numeric(last_n["anxiety_1_10"], errors="coerce")

                cond_sleep = (last_n["sleep_hours"] < 7).sum()
                cond_caf = (last_n["caffeine_mg_total"] > 200).sum()
                cond_anx = (last_n["anxiety_1_10"] >= 7).sum()

                if cond_sleep >= 2 and cond_caf >= 2:
                    st.error("Alerte: sur les 3 derniers jours, caféine élevée + sommeil faible → risque de fatigue et baisse performance.")
                elif cond_sleep >= 2 and cond_anx >= 2:
                    st.warning("Attention: sommeil faible + anxiété élevée sur plusieurs jours → réduire caféine et prioriser récupération.")
                else:
                    st.success("Pas d’alerte forte sur les 3 derniers jours (selon les seuils définis).")
            else:
                st.info("Ajoute au moins 3 jours de données pour l’alerte multi-jours.")

# -----------------------------
# Page 5: Export & Data Quality
# -----------------------------
elif page == "5) Export & Qualité":
    st.subheader("5) Export & Qualité des données")

    if logs.empty:
        st.info("Aucune donnée à exporter.")
    else:
        # Filters
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
        # duplicates: participant + date
        dup = df.duplicated(subset=["participant_id", "date"], keep=False)
        n_dup = int(dup.sum())
        if n_dup > 0:
            st.warning(f"Doublons détectés (participant + date) : {n_dup}")
            st.dataframe(df[dup].sort_values(["participant_id", "date"]), use_container_width=True)
        else:
            st.success("Pas de doublons (participant + date) sur la sélection.")

        # outliers
        df["caffeine_mg_total"] = pd.to_numeric(df["caffeine_mg_total"], errors="coerce")
        out = df[df["caffeine_mg_total"] > 800]
        if not out.empty:
            st.warning("Valeurs caféine très élevées (> 800 mg) détectées : vérifie si c’est correct.")
            st.dataframe(out, use_container_width=True)

        st.markdown("### 📋 Données sélectionnées")
        st.dataframe(df.sort_values(["participant_id", "date"]), use_container_width=True)

        st.markdown("### ⬇️ Export CSV")
        export_df = df.copy()
        # ensure dates are strings for download consistency
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
            # list dates available for selected participant
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
st.sidebar.caption("Astuce: tu peux modifier le catalogue caféine dans le code (CAFFEINE_CATALOG).")
