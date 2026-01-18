import streamlit as st
from datetime import datetime

# =============================
# CONSTANTES
# =============================
MAX_CAFEINE = 400
HEURE_LIMITE = 16

CAFEINE_BOISSONS = {
    "Expresso": 70,
    "Café filtre": 100,
    "Thé": 40
}

# =============================
# INITIALISATION SESSION STATE
# =============================
if "total_cafeine" not in st.session_state:
    st.session_state.total_cafeine = 0

if "historique" not in st.session_state:
    st.session_state.historique = []

# =============================
# STATUT GLOBAL
# =============================
def stat_global():
    total = st.session_state.total_cafeine
    if total < 250:
        return "✅ Statut : Consommation saine"
    elif total < 400:
        return "⚠️ Statut : Attention à l’excès"
    else:
        return "❌ Statut : Excès dangereux"

# =============================
# CONSEILS SANTÉ
# =============================
def conseils_sante():
    total = st.session_state.total_cafeine
    if total < 200:
        return "🧠 Bonne vigilance sans risque."
    elif total < 350:
        return "❤️ Attention au stress et aux palpitations."
    else:
        return "😴 Risque élevé : sommeil et cœur affectés."

# =============================
# SAUVEGARDE TEXTE
# =============================
def generer_rapport():
    date = datetime.now().strftime("%Y-%m-%d")

    contenu = "📊 RAPPORT DE CONSOMMATION DE CAFÉINE\n\n"
    for h in st.session_state.historique:
        contenu += f"{h[2]}h - {h[0]} : {h[1]} mg\n"

    contenu += f"\nTotal : {st.session_state.total_cafeine} mg\n"
    contenu += stat_global()

    return contenu, f"rapport_cafeine_{date}.txt"

# =============================
# INTERFACE STREAMLIT
# =============================
st.title("☕ Suivi avancé de la caféine (version Web)")
st.write("Application convertie depuis Tkinter → Streamlit")

# Choix de boisson
boisson = st.selectbox("Choisissez une boisson :", list(CAFEINE_BOISSONS.keys()))

# Bouton d’ajout
if st.button("➕ Ajouter une tasse"):
    mg = CAFEINE_BOISSONS[boisson]
    heure = datetime.now().hour

    st.session_state.total_cafeine += mg
    st.session_state.historique.append((boisson, mg, heure))

    message = ""

    if heure >= HEURE_LIMITE:
        message += "⚠️ Café après 16h : risque pour le sommeil.\n\n"

    message += conseils_sante() + "\n" + stat_global()

    st.success(f"Ajouté : {boisson} (+{mg} mg)")
    st.info(message)

# Affichage état
st.subheader("Bilan actuel")
st.write(f"**Caféine totale : {st.session_state.total_cafeine} mg**")

# Historique
if st.session_state.historique:
    st.write("### Historique des consommations")
    for b, mg, h in st.session_state.historique:
        st.write(f"- {h}h : **{b}** (+{mg} mg)")

# Téléchargement rapport
rapport, filename = generer_rapport()
st.download_button("📁 Télécharger le rapport du jour", data=rapport, file_name=filename)

# Nouvelle journée
if st.button("🔄 Nouvelle journée"):
    st.session_state.total_cafeine = 0
    st.session_state.historique = []
    st.success("Nouvelle journée ! Les compteurs ont été réinitialisés.")


