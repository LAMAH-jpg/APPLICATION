import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime
import matplotlib.pyplot as plt

ACCOUNTS_FILE = "accounts.json"
DATA_CSV = "budget_history.csv"

# --------- Gestion comptes ----------
def load_accounts():
    if os.path.exists(ACCOUNTS_FILE):
        try:
            with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_accounts(accounts):
    with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
        json.dump(accounts, f, ensure_ascii=False, indent=2)

# ---------- Analyse budget ----------
def analyze_budget(salary, reste, expenses):
    if salary <= 0:
        return 0, "Salaire invalide pour l'analyse."

    ratio = reste / salary
    if reste <= 0:
        msg = ("Votre budget est déficitaire. Réduisez les dépenses non essentielles : loisirs, vêtements, sorties.")
        suggestion = 0
    elif ratio >= 0.30:
        suggestion = 30
        msg = f"Bon reste ({ratio*100:.1f}%). Vous pouvez épargner ~30%."
    elif ratio >= 0.10:
        suggestion = 15
        msg = f"Reste correct ({ratio*100:.1f}%). Vous pouvez épargner ~15%."
    else:
        suggestion = 5
        msg = f"Reste faible ({ratio*100:.1f}%). Essayez de réduire certaines dépenses."

    top_exp = sorted(expenses.items(), key=lambda x: x[1], reverse=True)[:3]
    if any(v > 0 for _, v in top_exp):
        msg += " | Dépenses principales : " + ", ".join([f"{k}: {v} MAD" for k, v in top_exp])

    return suggestion, msg

# ---------- Sauvegarde CSV ----------
def save_budget_to_csv(username, data_dict):
    df = pd.DataFrame([data_dict])
    if not os.path.exists(DATA_CSV):
        df.to_csv(DATA_CSV, index=False, encoding="utf-8")
    else:
        df.to_csv(DATA_CSV, mode='a', index=False, header=False, encoding="utf-8")


# ---------- Interface Streamlit ----------
st.set_page_config(page_title="Gestion Budget", layout="wide")
st.title("💰 Gestionnaire de Budget – Version Web")

accounts = load_accounts()

# ----- Système Login -----
if "user" not in st.session_state:
    st.session_state.user = None

if st.session_state.user is None:
    tab1, tab2, tab3 = st.tabs(["Connexion", "Créer un compte", "Invité"])

    with tab1:
        username = st.text_input("Nom d'utilisateur")
        password = st.text_input("Mot de passe", type="password")
        if st.button("Se connecter"):
            if username in accounts and accounts[username]["password"] == password:
                st.session_state.user = username
                st.success(f"Bienvenue {username}")
            else:
                st.error("Identifiants incorrects")

    with tab2:
        new_user = st.text_input("Créer un nom d'utilisateur")
        new_pass = st.text_input("Créer un mot de passe", type="password")
        if st.button("Créer le compte"):
            if new_user in accounts:
                st.error("Ce nom existe déjà.")
            else:
                accounts[new_user] = {"password": new_pass}
                save_accounts(accounts)
                st.success("Compte créé ! Connectez-vous.")

    with tab3:
        if st.button("Continuer en invité"):
            st.session_state.user = "Invité"
            st.info("Mode invité activé.")

    st.stop()

# ----- Interface principale -----
st.sidebar.title(f"👤 Utilisateur : {st.session_state.user}")
if st.sidebar.button("Déconnexion"):
    st.session_state.user = None
    st.rerun()

col1, col2 = st.columns([1, 2])

with col1:
    statut = st.radio("Statut familial", ["Célibataire", "Marié(e)"])

    salary = st.number_input("Salaire (MAD)", min_value=0.0, step=100.0)

    st.subheader("Dépenses")
    categories = ["Logement", "Alimentation", "Transport",
                  "Factures", "Loisirs", "Sport", "Vêtements", "Autre"]

    expenses = {}
    for cat in categories:
        expenses[cat] = st.number_input(cat, min_value=0.0, step=50.0)

    children = 0
    if statut == "Marié(e)":
        children = st.number_input("Charges enfants", min_value=0.0, step=50.0)

    if st.button("Calculer le reste"):
        total_exp = sum(expenses.values()) + children
        reste = salary - total_exp

        suggested_pct, analysis_msg = analyze_budget(salary, reste, expenses)

        st.session_state.last = {
            "salary": salary,
            "expenses": expenses,
            "children": children,
            "total": total_exp,
            "reste": reste,
            "pct": suggested_pct,
            "amt": reste * suggested_pct / 100
        }

with col2:
    st.subheader("Analyse")

    if "last" in st.session_state:
        data = st.session_state.last
        
        st.write(f"### Résultats")
        st.write(f"**Salaire :** {data['salary']} MAD")
        st.write(f"**Total dépenses :** {data['total']} MAD")
        st.write(f"**Reste :** {data['reste']} MAD")
        st.write(f"**Épargne conseillée :** {data['pct']}% ({data['amt']} MAD)")

        st.info(analysis_msg)

        # Camembert
        labels = [k for k, v in data["expenses"].items() if v > 0]
        sizes = [v for v in data["expenses"].values() if v > 0]

        if data["children"] > 0:
            labels.append("Enfants")
            sizes.append(data["children"])

        fig, ax = plt.subplots()
        ax.pie(sizes, labels=labels, autopct='%1.1f%%')
        ax.axis("equal")
        st.pyplot(fig)

        # Sauvegarde CSV
        if st.button("Sauvegarder dans CSV"):
            row = {
                "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "username": st.session_state.user,
                "salary": data["salary"],
                "total_expenses": data["total"],
                "reste": data["reste"],
                "suggested_pct": data["pct"],
                "suggested_amt": data["amt"]
            }
            for k, v in data["expenses"].items():
                row[f"exp_{k}"] = v
            row["children"] = data["children"]

            save_budget_to_csv(st.session_state.user, row)
            st.success("Sauvegardé !")

# Objectifs
st.subheader("🎯 Objectif d'épargne")
goal_name = st.text_input("Nom de l'objectif")
goal_amount = st.number_input("Montant (MAD)", min_value=0.0)
goal_months = st.number_input("Mois", min_value=1)

if st.button("Vérifier faisabilité"):
    if "last" not in st.session_state:
        st.warning("Calculez d'abord votre budget.")
    else:
        monthly_possible = st.session_state.last["amt"]
        required = goal_amount / goal_months

        if monthly_possible >= required:
            st.success(f"L'objectif est réalisable : besoin {required:.2f} MAD/mois.")
        else:
            st.error(f"Objectif difficile : besoin {required:.2f} MAD/mois, vous pouvez {monthly_possible:.2f}.")
