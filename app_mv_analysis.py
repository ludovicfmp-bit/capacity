import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
import numpy as np

st.set_page_config(page_title="Analyse MV - Charge vs Score", page_icon="📊", layout="wide")

st.title("📊 Analyse MV - Minimum de Viabilité")
st.markdown("*Corrélation entre charges horaires (LOAD) et scores d'occupation (OCC)*")

# ============================================
# SIDEBAR
# ============================================

with st.sidebar:
    st.header("📁 Fichiers de données")

    uploaded_occ = st.file_uploader(
        "1️⃣ OCC (occupation minute)", 
        type=['csv'], 
        key='occ',
        help="Fichier OCC avec occupation minute par minute"
    )

    uploaded_load = st.file_uploader(
        "2️⃣ LOAD (charges horaires)", 
        type=['csv'], 
        key='load',
        help="Fichier LOAD avec charges horaires"
    )

    st.divider()
    st.header("⚙️ Configuration")

    sustain = st.number_input(
        "SUSTAIN (av/min)", 
        min_value=0.0, 
        max_value=30.0,
        value=20.0, 
        step=0.5,
        help="Seuil minimal pour secteur groupé"
    )

    peak = st.number_input(
        "PEAK (av/min)", 
        min_value=0.0, 
        max_value=40.0,
        value=25.0, 
        step=0.5,
        help="Seuil de dégroupement"
    )

    tolerance = st.number_input(
        "Tolérance (av)", 
        min_value=0.0, 
        max_value=5.0,
        value=1.0, 
        step=0.5,
        help="SUSTAIN + Tolérance = zone acceptable"
    )

    st.info(f"🎯 Zone viable : ≤ {sustain + tolerance} av/min")
    st.warning(f"⚠️ Dégroupement : > {peak} av/min")

    st.divider()
    st.header("📊 Méthodes")

    st.markdown("""
    **Option A : Linéaire**
    - OCC ≤ seuil → +1
    - OCC > seuil → -(dépassement)

    **Option B : Trois zones**
    - OCC ≤ seuil → +1
    - seuil < OCC ≤ PEAK → 0
    - OCC > PEAK → -(dépassement)×2
    """)

# ============================================
# CHARGEMENT DONNÉES
# ============================================

if uploaded_occ is None or uploaded_load is None:
    st.info("👈 **Chargez OCC et LOAD dans la barre latérale**")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("""
        ### 🎯 Objectif

        Trouver la **MV (Minimum de Viabilité)** :
        - Quelle charge horaire max avant dégradation ?
        - Graphique : **Charge (X) vs Score (Y)**
        - MV = limite où le score chute
        """)

    with col2:
        st.markdown("""
        ### 📈 Analyse

        Pour chaque heure :
        1. Calcul score OCC (60 minutes)
        2. Récupération charge LOAD
        3. Point sur graphique
        4. Identification seuil critique
        """)

    st.stop()

# Charger OCC
try:
    occ_df = pd.read_csv(uploaded_occ, sep=';', index_col=0)
    occ_df.index.name = 'Date'
    tv_occ = occ_df['ID'].iloc[0]

except Exception as e:
    st.error(f"❌ Erreur OCC : {e}")
    st.stop()

# Charger LOAD
try:
    load_df = pd.read_csv(uploaded_load, sep=';')
    tv_load = load_df['ID'].iloc[0]

    if tv_load != tv_occ:
        st.warning(f"⚠️ TV différents : LOAD={tv_load}, OCC={tv_occ}")

    tv_detected = tv_load

except Exception as e:
    st.error(f"❌ Erreur LOAD : {e}")
    st.stop()

st.success(f"✅ **TV : {tv_detected}** | OCC : {len(occ_df)} jours | LOAD : {len(load_df)} jours")

# ============================================
# FONCTIONS SCORING
# ============================================

def score_option_a(occ_minutes, sustain, tolerance):
    """Option A : Dégradation linéaire simple"""
    score = 0
    for occ in occ_minutes:
        if occ <= sustain + tolerance:
            score += 1
        else:
            score -= (occ - sustain - tolerance)
    return score

def score_option_b(occ_minutes, sustain, tolerance, peak):
    """Option B : Trois zones avec PEAK"""
    score = 0
    for occ in occ_minutes:
        if occ <= sustain + tolerance:
            score += 1
        elif occ <= peak:
            score += 0  # Zone d'alerte
        else:
            score -= (occ - peak) * 2  # Dégroupement pénalisé
    return score

# ============================================
# CALCUL
# ============================================

st.divider()
if st.button("🚀 Calculer scores et générer graphique", type="primary", use_container_width=True):

    with st.spinner("🔄 Calcul en cours..."):

        # Colonnes OCC
        minute_cols = [col for col in occ_df.columns if 'Duration 11 Min' in col]

        # Colonnes LOAD
        load_cols = [col for col in load_df.columns if ':' in col and '-' in col]

        results = []

        # Pour chaque date dans OCC
        for date in occ_df.index:
            row_occ = occ_df.loc[date]

            # Trouver ligne correspondante dans LOAD
            row_load = load_df[load_df['Date'] == date]

            if len(row_load) == 0:
                continue  # Pas de correspondance LOAD

            row_load = row_load.iloc[0]

            # Extraire toutes valeurs OCC (1440 minutes)
            occ_values = []
            for col in minute_cols:
                try:
                    occ_values.append(float(row_occ[col]))
                except:
                    occ_values.append(0)

            # Analyser par heure (0-23)
            for hour in range(24):
                start_min = hour * 60
                end_min = (hour + 1) * 60
                occ_hour = occ_values[start_min:end_min]

                # Scores
                score_a = score_option_a(occ_hour, sustain, tolerance)
                score_b = score_option_b(occ_hour, sustain, tolerance, peak)

                # Charge LOAD correspondante
                load_col_name = f"{hour}:00-{hour+1}:00"
                try:
                    load_value = float(row_load[load_col_name])
                except:
                    load_value = None

                # Stats OCC
                avg_occ = np.mean(occ_hour)
                max_occ = np.max(occ_hour)

                results.append({
                    'Date': date,
                    'Hour': hour,
                    'Load': load_value,
                    'Score_A': round(score_a, 2),
                    'Score_B': round(score_b, 2),
                    'Avg_OCC': round(avg_occ, 2),
                    'Max_OCC': round(max_occ, 2)
                })

        df_results = pd.DataFrame(results)

        # Filtrer lignes avec LOAD valide
        df_results = df_results[df_results['Load'].notna()]

        st.success(f"✅ **{len(df_results)} heures analysées**")

        # ============================================
        # GRAPHIQUES
        # ============================================

        st.markdown("### 📊 Graphique : Charge LOAD vs Score OCC")

        tab1, tab2, tab3 = st.tabs(["📈 Option A (Linéaire)", "📈 Option B (Trois zones)", "📊 Comparaison"])

        with tab1:
            st.markdown("**Option A : Dégradation linéaire simple**")

            fig1 = go.Figure()

            fig1.add_trace(go.Scatter(
                x=df_results['Load'],
                y=df_results['Score_A'],
                mode='markers',
                marker=dict(
                    size=6,
                    color=df_results['Score_A'],
                    colorscale='RdYlGn',
                    showscale=True,
                    colorbar=dict(title="Score"),
                    opacity=0.6
                ),
                text=[f"Date: {row['Date']}<br>Heure: {row['Hour']}h<br>Load: {row['Load']}<br>Score: {row['Score_A']}" 
                      for _, row in df_results.iterrows()],
                hovertemplate='%{text}<extra></extra>'
            ))

            fig1.add_hline(y=0, line_dash="dash", line_color="red", 
                          annotation_text="Seuil viabilité (score=0)")

            fig1.update_layout(
                title=f"Charge vs Score (Option A) - {tv_detected}",
                xaxis_title="Charge horaire LOAD (avions/heure)",
                yaxis_title="Score OCC (max = 60)",
                height=500
            )

            st.plotly_chart(fig1, use_container_width=True)

            # Stats Option A
            col1, col2, col3 = st.columns(3)
            with col1:
                viable_a = len(df_results[df_results['Score_A'] > 0])
                st.metric("Heures viables", f"{viable_a/len(df_results)*100:.1f}%", f"{viable_a} heures")
            with col2:
                avg_score_a = df_results['Score_A'].mean()
                st.metric("Score moyen", f"{avg_score_a:.1f}")
            with col3:
                # MV estimation
                viable_df = df_results[df_results['Score_A'] > 30]
                if len(viable_df) > 0:
                    mv_estimate = viable_df['Load'].quantile(0.95)
                    st.metric("MV estimée (P95)", f"{mv_estimate:.0f} av/h")

        with tab2:
            st.markdown("**Option B : Trois zones (SUSTAIN / PEAK / DÉGROUPEMENT)**")

            fig2 = go.Figure()

            fig2.add_trace(go.Scatter(
                x=df_results['Load'],
                y=df_results['Score_B'],
                mode='markers',
                marker=dict(
                    size=6,
                    color=df_results['Score_B'],
                    colorscale='RdYlGn',
                    showscale=True,
                    colorbar=dict(title="Score"),
                    opacity=0.6
                ),
                text=[f"Date: {row['Date']}<br>Heure: {row['Hour']}h<br>Load: {row['Load']}<br>Score: {row['Score_B']}" 
                      for _, row in df_results.iterrows()],
                hovertemplate='%{text}<extra></extra>'
            ))

            fig2.add_hline(y=0, line_dash="dash", line_color="red", 
                          annotation_text="Seuil viabilité")

            fig2.update_layout(
                title=f"Charge vs Score (Option B) - {tv_detected}",
                xaxis_title="Charge horaire LOAD (avions/heure)",
                yaxis_title="Score OCC (max = 60)",
                height=500
            )

            st.plotly_chart(fig2, use_container_width=True)

            # Stats Option B
            col1, col2, col3 = st.columns(3)
            with col1:
                viable_b = len(df_results[df_results['Score_B'] > 0])
                st.metric("Heures viables", f"{viable_b/len(df_results)*100:.1f}%", f"{viable_b} heures")
            with col2:
                avg_score_b = df_results['Score_B'].mean()
                st.metric("Score moyen", f"{avg_score_b:.1f}")
            with col3:
                viable_df_b = df_results[df_results['Score_B'] > 30]
                if len(viable_df_b) > 0:
                    mv_estimate_b = viable_df_b['Load'].quantile(0.95)
                    st.metric("MV estimée (P95)", f"{mv_estimate_b:.0f} av/h")

        with tab3:
            st.markdown("**Comparaison des deux méthodes**")

            fig3 = go.Figure()

            fig3.add_trace(go.Scatter(
                x=df_results['Load'],
                y=df_results['Score_A'],
                mode='markers',
                name='Option A (Linéaire)',
                marker=dict(size=5, color='blue', opacity=0.5)
            ))

            fig3.add_trace(go.Scatter(
                x=df_results['Load'],
                y=df_results['Score_B'],
                mode='markers',
                name='Option B (Trois zones)',
                marker=dict(size=5, color='orange', opacity=0.5)
            ))

            fig3.add_hline(y=0, line_dash="dash", line_color="red")

            fig3.update_layout(
                title="Comparaison Options A vs B",
                xaxis_title="Charge LOAD (av/h)",
                yaxis_title="Score OCC",
                height=500
            )

            st.plotly_chart(fig3, use_container_width=True)

            # Corrélation
            corr_ab = df_results['Score_A'].corr(df_results['Score_B'])
            st.info(f"🔗 Corrélation entre Option A et B : {corr_ab:.3f}")

        # ============================================
        # ANALYSE PAR TRANCHE DE CHARGE
        # ============================================

        st.markdown("### 📊 Analyse par tranche de charge")

        # Créer tranches
        df_results['Load_Bucket'] = pd.cut(df_results['Load'], bins=[0, 20, 40, 60, 80, 100, 200])

        tranches = df_results.groupby('Load_Bucket').agg({
            'Score_A': ['mean', 'min', 'max', 'count'],
            'Score_B': ['mean', 'min', 'max']
        }).round(2)

        st.dataframe(tranches, use_container_width=True)

        # ============================================
        # IDENTIFICATION MV
        # ============================================

        st.markdown("### 🎯 Identification MV")

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**Option A**")

            # Critère : Score > 30 (50% minutes OK)
            viable_loads_a = df_results[df_results['Score_A'] > 30]['Load']

            if len(viable_loads_a) > 0:
                mv_p50_a = viable_loads_a.quantile(0.50)
                mv_p75_a = viable_loads_a.quantile(0.75)
                mv_p95_a = viable_loads_a.quantile(0.95)

                st.metric("MV conservatrice (P50)", f"{mv_p50_a:.0f} av/h")
                st.metric("MV normale (P75)", f"{mv_p75_a:.0f} av/h")
                st.metric("MV optimiste (P95)", f"{mv_p95_a:.0f} av/h")
            else:
                st.warning("Aucune heure viable détectée")

        with col2:
            st.markdown("**Option B**")

            viable_loads_b = df_results[df_results['Score_B'] > 30]['Load']

            if len(viable_loads_b) > 0:
                mv_p50_b = viable_loads_b.quantile(0.50)
                mv_p75_b = viable_loads_b.quantile(0.75)
                mv_p95_b = viable_loads_b.quantile(0.95)

                st.metric("MV conservatrice (P50)", f"{mv_p50_b:.0f} av/h")
                st.metric("MV normale (P75)", f"{mv_p75_b:.0f} av/h")
                st.metric("MV optimiste (P95)", f"{mv_p95_b:.0f} av/h")
            else:
                st.warning("Aucune heure viable détectée")

        # ============================================
        # EXPORT
        # ============================================

        st.divider()
        st.markdown("### 💾 Export")

        csv_export = df_results.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Télécharger résultats (CSV)",
            data=csv_export,
            file_name=f"mv_load_vs_score_{tv_detected}_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )

st.markdown("---")
st.markdown("*Analyse MV : Corrélation Charge LOAD vs Score OCC*")
