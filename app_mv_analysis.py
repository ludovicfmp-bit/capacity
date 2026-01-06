import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
import numpy as np

st.set_page_config(page_title="Analyse MV (Minimum de Viabilité)", page_icon="📊", layout="wide")

st.title("📊 Analyse MV - Minimum de Viabilité TV")
st.markdown("*Calcul des scores de viabilité basé sur occupation (OCC) vs seuils SUSTAIN/PEAK*")

# ============================================
# SIDEBAR : UPLOAD & CONFIGURATION
# ============================================

with st.sidebar:
    st.header("📁 Fichiers de données")

    uploaded_occ = st.file_uploader(
        "1️⃣ OCC (occupation minute)", 
        type=['csv'], 
        key='occ',
        help="Fichier OCC_XXX.csv avec occupation minute par minute"
    )

    uploaded_load = st.file_uploader(
        "2️⃣ LOAD (charges horaires)", 
        type=['csv'], 
        key='load',
        help="Fichier LOAD_XXX.csv - optionnel pour comparaison"
    )

    st.divider()
    st.header("⚙️ Configuration seuils")

    sustain = st.number_input(
        "SUSTAIN (av/min)", 
        min_value=0.0, 
        max_value=30.0,
        value=20.0, 
        step=0.5,
        help="Seuil minimal pour maintenir secteur groupé"
    )

    peak = st.number_input(
        "PEAK (av/min)", 
        min_value=0.0, 
        max_value=40.0,
        value=25.0, 
        step=0.5,
        help="Seuil de dégroupement (si dépassé)"
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

# ============================================
# MAIN : CHARGEMENT DONNÉES
# ============================================

if uploaded_occ is None:
    st.info("👈 **Commencez par charger le fichier OCC dans la barre latérale**")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("""
        ### 📝 Fichier requis

        **OCC_XXX.csv**
        - Occupation minute par minute
        - Format : `0:00 - Duration 11 Min`, `0:01 - Duration 11 Min`...
        - Colonne B = ID du TV (ex: LFEKHN)
        """)

    with col2:
        st.markdown("""
        ### 🎯 Méthodes de scoring

        **1. Fenêtre glissante 5 min**
        - Lisse la volatilité
        - Score minute par minute

        **2. Percentile 90 horaire**
        - Ignore pics isolés (10% pires valeurs)
        - Score par heure fixe

        **3. Règle de dégroupement**
        - OCC > PEAK → Dégroupement obligatoire
        """)

    st.stop()

# Charger OCC
try:
    occ_df = pd.read_csv(uploaded_occ, sep=';', index_col=0)
    occ_df.index.name = 'Date'

    # Détecter TV
    tv_detected = occ_df['ID'].iloc[0]

    st.success(f"✅ **TV détecté : {tv_detected}**")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("📍 Secteur", tv_detected)
    with col2:
        st.metric("📅 Jours", len(occ_df))
    with col3:
        st.metric("📆 Période", f"{occ_df.index[0]} → {occ_df.index[-1]}")

except Exception as e:
    st.error(f"❌ **Erreur lecture OCC :** {e}")
    st.stop()

# Charger LOAD (optionnel)
load_df = None
if uploaded_load:
    try:
        load_df = pd.read_csv(uploaded_load, sep=';')
        st.info(f"✅ LOAD chargé : {len(load_df)} jours")
    except:
        st.warning("⚠️ Erreur lecture LOAD (ignoré)")

# ============================================
# FONCTIONS DE SCORING
# ============================================

def score_sliding_window(occ_minutes, sustain, tolerance, window=5):
    """Score avec fenêtre glissante 5 minutes"""
    scores = []
    n = len(occ_minutes)
    half_window = window // 2

    for i in range(n):
        start = max(0, i - half_window)
        end = min(n, i + half_window + 1)
        avg_occ = np.mean(occ_minutes[start:end])

        if avg_occ <= sustain + tolerance:
            scores.append(1)
        else:
            scores.append(-(avg_occ - sustain - tolerance))

    return sum(scores)

def score_percentile(occ_hour, sustain, tolerance):
    """Score basé sur percentile 90"""
    p90 = np.percentile(occ_hour, 90)

    if p90 <= sustain:
        return 60
    elif p90 <= sustain + tolerance:
        return 30
    else:
        return -60 * (p90 - sustain - tolerance)

def detect_degroupement(occ_minutes, peak):
    """Détecte les minutes de dégroupement (OCC > PEAK)"""
    return sum(1 for occ in occ_minutes if occ > peak)

# ============================================
# CALCUL DES SCORES
# ============================================

st.divider()
col1, col2 = st.columns([3, 1])
with col1:
    st.subheader("🔬 Analyse MV")
with col2:
    if st.button("🚀 Calculer", type="primary", use_container_width=True):
        st.session_state['calculate'] = True

if st.session_state.get('calculate', False):
    with st.spinner("🔄 Calcul des scores MV en cours..."):

        # Identifier colonnes minutes
        minute_cols = [col for col in occ_df.columns if 'Duration 11 Min' in col]

        results = []

        for date in occ_df.index:
            row = occ_df.loc[date]

            # Extraire occupation
            occ_values = []
            for col in minute_cols:
                try:
                    occ_values.append(float(row[col]))
                except:
                    occ_values.append(0)

            # Analyser par heure
            for hour in range(24):
                start_min = hour * 60
                end_min = (hour + 1) * 60
                occ_hour = occ_values[start_min:end_min]

                # Scores
                score_m1 = score_sliding_window(occ_hour, sustain, tolerance)
                score_m2 = score_percentile(occ_hour, sustain, tolerance)

                # Dégroupement
                nb_degroup = detect_degroupement(occ_hour, peak)

                # Stats
                avg_occ = np.mean(occ_hour)
                max_occ = np.max(occ_hour)
                p90_occ = np.percentile(occ_hour, 90)

                results.append({
                    'Date': date,
                    'Hour': hour,
                    'Avg_OCC': round(avg_occ, 2),
                    'Max_OCC': round(max_occ, 2),
                    'P90_OCC': round(p90_occ, 2),
                    'Score_M1': round(score_m1, 2),
                    'Score_M2': round(score_m2, 2),
                    'Minutes_Degroup': nb_degroup,
                    'Status': '🚨 DÉGROUPÉ' if nb_degroup > 0 else '✅ GROUPÉ'
                })

        df_results = pd.DataFrame(results)

        # ============================================
        # AFFICHAGE RÉSULTATS
        # ============================================

        st.success(f"✅ **{len(df_results)} heures analysées**")

        # Stats globales
        st.markdown("### 📈 Statistiques globales")

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            viable_m1 = len(df_results[df_results['Score_M1'] > 0])
            st.metric(
                "Heures viables (M1)",
                f"{viable_m1/len(df_results)*100:.1f}%",
                f"{viable_m1} / {len(df_results)}"
            )

        with col2:
            viable_m2 = len(df_results[df_results['Score_M2'] > 0])
            st.metric(
                "Heures viables (M2)",
                f"{viable_m2/len(df_results)*100:.1f}%",
                f"{viable_m2} / {len(df_results)}"
            )

        with col3:
            degroup_hours = len(df_results[df_results['Minutes_Degroup'] > 0])
            st.metric(
                "Heures avec dégroupement",
                f"{degroup_hours/len(df_results)*100:.1f}%",
                f"{degroup_hours} heures"
            )

        with col4:
            total_degroup_min = df_results['Minutes_Degroup'].sum()
            st.metric(
                "Total minutes dégroupées",
                f"{total_degroup_min:,} min",
                f"{total_degroup_min/60:.0f}h"
            )

        # Graphique 1 : Distribution scores
        st.markdown("### 📊 Distribution des scores")

        tab1, tab2, tab3 = st.tabs(["📈 Scores par heure", "🕐 Scores par heure de la journée", "📅 Scores par jour"])

        with tab1:
            fig1 = go.Figure()

            fig1.add_trace(go.Scatter(
                x=df_results.index,
                y=df_results['Score_M1'],
                name='Méthode 1 (Fenêtre 5min)',
                mode='lines',
                line=dict(color='#1f77b4', width=1)
            ))

            fig1.add_trace(go.Scatter(
                x=df_results.index,
                y=df_results['Score_M2'],
                name='Méthode 2 (P90)',
                mode='lines',
                line=dict(color='#ff7f0e', width=1)
            ))

            fig1.add_hline(y=0, line_dash="dash", line_color="red", 
                          annotation_text="Seuil viabilité")

            fig1.update_layout(
                title=f"Évolution des scores MV - {tv_detected}",
                xaxis_title="Heures chronologiques",
                yaxis_title="Score MV",
                height=400
            )

            st.plotly_chart(fig1, use_container_width=True)

        with tab2:
            hourly_avg = df_results.groupby('Hour').agg({
                'Score_M1': 'mean',
                'Score_M2': 'mean',
                'Minutes_Degroup': 'sum'
            }).reset_index()

            fig2 = go.Figure()

            fig2.add_trace(go.Bar(
                x=hourly_avg['Hour'],
                y=hourly_avg['Score_M1'],
                name='Méthode 1',
                marker_color='#1f77b4'
            ))

            fig2.add_trace(go.Bar(
                x=hourly_avg['Hour'],
                y=hourly_avg['Score_M2'],
                name='Méthode 2',
                marker_color='#ff7f0e'
            ))

            fig2.update_layout(
                title="Score moyen par heure de la journée",
                xaxis_title="Heure (0-23h)",
                yaxis_title="Score moyen",
                barmode='group',
                height=400
            )

            st.plotly_chart(fig2, use_container_width=True)

        with tab3:
            daily_stats = df_results.groupby('Date').agg({
                'Score_M1': 'sum',
                'Score_M2': 'sum',
                'Minutes_Degroup': 'sum'
            }).reset_index()

            fig3 = go.Figure()

            fig3.add_trace(go.Scatter(
                x=daily_stats['Date'],
                y=daily_stats['Score_M2'],
                name='Score M2 journalier',
                mode='lines+markers',
                line=dict(color='#2ca02c', width=2)
            ))

            fig3.add_hline(y=0, line_dash="dash", line_color="red")

            fig3.update_layout(
                title="Score MV par jour (Méthode 2)",
                xaxis_title="Date",
                yaxis_title="Score total journalier",
                height=400
            )

            st.plotly_chart(fig3, use_container_width=True)

        # Graphique 2 : Dégroupements
        st.markdown("### 🚨 Analyse des dégroupements")

        col1, col2 = st.columns(2)

        with col1:
            degroup_by_hour = df_results.groupby('Hour')['Minutes_Degroup'].sum()

            fig4 = go.Figure(data=[go.Bar(
                x=degroup_by_hour.index,
                y=degroup_by_hour.values,
                marker_color='#d62728'
            )])

            fig4.update_layout(
                title="Minutes de dégroupement par heure",
                xaxis_title="Heure",
                yaxis_title="Total minutes dégroupées",
                height=350
            )

            st.plotly_chart(fig4, use_container_width=True)

        with col2:
            # Heatmap occupation moyenne
            heatmap_data = df_results.pivot_table(
                values='Avg_OCC',
                index='Hour',
                columns=df_results['Date'],
                aggfunc='mean'
            )

            fig5 = go.Figure(data=go.Heatmap(
                z=heatmap_data.values,
                x=heatmap_data.columns,
                y=heatmap_data.index,
                colorscale='RdYlGn_r',
                hovertemplate='Date: %{x}<br>Heure: %{y}h<br>OCC: %{z:.1f}<extra></extra>'
            ))

            fig5.update_layout(
                title="Heatmap occupation moyenne",
                xaxis_title="Date",
                yaxis_title="Heure",
                height=350
            )

            st.plotly_chart(fig5, use_container_width=True)

        # Top journées problématiques
        st.markdown("### 🚨 Top 10 journées problématiques")

        daily_stats_sorted = daily_stats.sort_values('Score_M2')

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**Pires journées (Score M2)**")
            worst_days = daily_stats_sorted.head(10)
            st.dataframe(
                worst_days[['Date', 'Score_M2', 'Minutes_Degroup']],
                hide_index=True,
                use_container_width=True
            )

        with col2:
            st.markdown("**Meilleures journées (Score M2)**")
            best_days = daily_stats_sorted.tail(10).sort_values('Score_M2', ascending=False)
            st.dataframe(
                best_days[['Date', 'Score_M2', 'Minutes_Degroup']],
                hide_index=True,
                use_container_width=True
            )

        # Export
        st.divider()
        st.markdown("### 💾 Export des données")

        col1, col2 = st.columns(2)

        with col1:
            csv_hourly = df_results.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Télécharger scores horaires (CSV)",
                data=csv_hourly,
                file_name=f"mv_scores_hourly_{tv_detected}_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )

        with col2:
            csv_daily = daily_stats.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Télécharger scores journaliers (CSV)",
                data=csv_daily,
                file_name=f"mv_scores_daily_{tv_detected}_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )

st.markdown("---")
st.markdown("*Analyse MV (Minimum de Viabilité) - Scoring basé sur OCC vs SUSTAIN/PEAK*")
