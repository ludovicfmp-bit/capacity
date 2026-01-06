import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
import numpy as np

st.set_page_config(page_title="Analyse MV - Glissant 20min", page_icon="📊", layout="wide")

st.title("📊 Analyse MV - Minimum de Viabilité")
st.markdown("*Corrélation Charge LOAD vs Score OCC - Fenêtres glissantes 20 minutes*")

# ============================================
# SIDEBAR
# ============================================

with st.sidebar:
    st.header("📁 Fichiers")

    uploaded_occ = st.file_uploader(
        "1️⃣ OCC (occupation minute)", 
        type=['csv'], 
        key='occ',
        help="Fichier OCC avec 1440 minutes"
    )

    uploaded_load = st.file_uploader(
        "2️⃣ LOAD (charges glissantes 20min)", 
        type=['csv'], 
        key='load',
        help="Fichier LOAD avec 72 colonnes (0:00-1:00, 0:20-1:20...)"
    )

    st.divider()
    st.header("⚙️ Seuils")

    sustain = st.number_input(
        "SUSTAIN (av/min)", 
        min_value=0.0, 
        max_value=30.0,
        value=20.0, 
        step=0.5,
        help="Seuil secteur groupé"
    )

    peak = st.number_input(
        "PEAK (av/min)", 
        min_value=0.0, 
        max_value=40.0,
        value=25.0, 
        step=0.5,
        help="Seuil dégroupement"
    )

    tolerance = st.number_input(
        "Tolérance (av)", 
        min_value=0.0, 
        max_value=5.0,
        value=1.0, 
        step=0.5,
        help="Marge au-dessus de SUSTAIN"
    )

    st.info(f"🎯 Viable : ≤ {sustain + tolerance} av/min")
    st.warning(f"⚠️ Dégroupement : > {peak} av/min")

    st.divider()
    st.header("📊 Scoring")

    st.markdown("""
    **Option A** 🔹
    - ≤ seuil → +1
    - > seuil → -(écart)

    **Option B** 🔸
    - ≤ seuil → +1
    - ≤ PEAK → 0
    - > PEAK → -2×(écart)
    """)

# ============================================
# CHARGEMENT DONNÉES (ROBUSTE)
# ============================================

if uploaded_occ is None or uploaded_load is None:
    st.info("👈 **Chargez OCC et LOAD**")
    st.stop()

# Charger OCC
try:
    occ_df = pd.read_csv(uploaded_occ, sep=';')
    
    # Lire TV (colonne B, index 1)
    tv_occ = occ_df.iloc[0, 1]
    
    # Convertir Date SEULEMENT si colonne existe et format correct
    if 'Date' in occ_df.columns:
        # Parser dates au format dd/mm/yyyy
        occ_df['Date'] = pd.to_datetime(occ_df['Date'], format='%d/%m/%Y', errors='coerce')
    
    # Colonnes OCC
    minute_cols = [col for col in occ_df.columns if 'Duration 11 Min' in col]
    
    st.success(f"✅ OCC : **{tv_occ}** | {len(occ_df)} lignes | {len(minute_cols)} minutes")
    
except Exception as e:
    st.error(f"❌ Erreur OCC : {e}")
    st.stop()

# Charger LOAD
try:
    load_df = pd.read_csv(uploaded_load, sep=';')
    
    # Lire TV (colonne B, index 1)
    tv_load = load_df.iloc[0, 1]
    
    # Convertir Date SEULEMENT si colonne existe
    if 'Date' in load_df.columns:
        load_df['Date'] = pd.to_datetime(load_df['Date'], format='%d/%m/%Y', errors='coerce')
    
    # Colonnes LOAD
    load_cols = [col for col in load_df.columns if ':' in col and '-' in col]
    
    st.success(f"✅ LOAD : **{tv_load}** | {len(load_df)} lignes | {len(load_cols)} fenêtres")
    
except Exception as e:
    st.error(f"❌ Erreur LOAD : {e}")
    st.stop()

# Vérification TV
if str(tv_occ).strip() != str(tv_load).strip():
    st.error(f"❌ TV différents : OCC='{tv_occ}', LOAD='{tv_load}'")
    st.stop()
else:
    tv_detected = str(tv_occ).strip()
    st.balloons()
    st.info(f"🎯 TV confirmée : **{tv_detected}**")



# ============================================
# FONCTIONS SCORING
# ============================================

def score_option_a(occ_minutes, sustain, tolerance):
    """Option A : Dégradation linéaire"""
    score = 0
    for occ in occ_minutes:
        if occ <= sustain + tolerance:
            score += 1
        else:
            score -= (occ - sustain - tolerance)
    return score

def score_option_b(occ_minutes, sustain, tolerance, peak):
    """Option B : Trois zones"""
    score = 0
    for occ in occ_minutes:
        if occ <= sustain + tolerance:
            score += 1
        elif occ <= peak:
            score += 0
        else:
            score -= (occ - peak) * 2
    return score

def parse_load_column(col_name):
    """Parse '10:20-11:20' → (10, 20) = heure début, minute début"""
    try:
        start_time = col_name.split('-')[0]
        hour, minute = start_time.split(':')
        return int(hour), int(minute)
    except:
        return None, None

# ============================================
# CALCUL
# ============================================

st.divider()
if st.button("🚀 Calculer MV (glissant 20min)", type="primary", use_container_width=True):

    with st.spinner(f"🔄 Calcul de {len(occ_df)} jours × {len(load_cols)} fenêtres..."):

        # Colonnes OCC
        minute_cols = [col for col in occ_df.columns if 'Duration 11 Min' in col]

        results = []

        # Pour chaque date
        for date in occ_df.index:
            row_occ = occ_df.loc[date]
            row_load = load_df[load_df['Date'] == date]

            if len(row_load) == 0:
                continue

            row_load = row_load.iloc[0]

            # Extraire OCC (1440 minutes)
            occ_values = []
            for col in minute_cols:
                try:
                    occ_values.append(float(row_occ[col]))
                except:
                    occ_values.append(0)

            # Pour chaque colonne LOAD
            for load_col in load_cols:
                hour_start, min_start = parse_load_column(load_col)

                if hour_start is None:
                    continue

                # Index minute début (0-1439)
                start_idx = hour_start * 60 + min_start
                end_idx = start_idx + 60  # Fenêtre 60 min

                # Extraire fenêtre OCC
                if end_idx <= len(occ_values):
                    occ_window = occ_values[start_idx:end_idx]
                else:
                    # Wrap around minuit
                    occ_window = occ_values[start_idx:] + occ_values[:end_idx-len(occ_values)]

                # Scores
                score_a = score_option_a(occ_window, sustain, tolerance)
                score_b = score_option_b(occ_window, sustain, tolerance, peak)

                # Charge LOAD
                try:
                    load_value = float(row_load[load_col])
                except:
                    load_value = None

                # Stats OCC
                avg_occ = np.mean(occ_window)
                max_occ = np.max(occ_window)

                results.append({
                    'Date': date,
                    'Window': load_col,
                    'Hour_Start': hour_start,
                    'Min_Start': min_start,
                    'Load': load_value,
                    'Score_A': round(score_a, 2),
                    'Score_B': round(score_b, 2),
                    'Avg_OCC': round(avg_occ, 2),
                    'Max_OCC': round(max_occ, 2)
                })

        df_results = pd.DataFrame(results)
        df_results = df_results[df_results['Load'].notna()]

        st.success(f"✅ **{len(df_results)} fenêtres analysées** ({len(df_results)/len(occ_df):.0f} par jour)")

        # ============================================
        # STATISTIQUES
        # ============================================

        st.markdown("### 📊 Vue d'ensemble")

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            viable_a = len(df_results[df_results['Score_A'] > 0])
            st.metric("Viables (A)", f"{viable_a/len(df_results)*100:.1f}%")

        with col2:
            viable_b = len(df_results[df_results['Score_B'] > 0])
            st.metric("Viables (B)", f"{viable_b/len(df_results)*100:.1f}%")

        with col3:
            avg_load = df_results['Load'].mean()
            st.metric("Charge moyenne", f"{avg_load:.1f} av/h")

        with col4:
            max_load = df_results['Load'].max()
            st.metric("Charge max", f"{max_load:.0f} av/h")

        # ============================================
        # GRAPHIQUES
        # ============================================

        st.markdown("### 📈 Graphiques Charge vs Score")

        tab1, tab2, tab3 = st.tabs(["🔹 Option A", "🔸 Option B", "⚖️ Comparaison"])

        with tab1:
            st.markdown(f"**Option A : Dégradation linéaire** (seuil = {sustain + tolerance} av/min)")

            fig1 = go.Figure()

            fig1.add_trace(go.Scatter(
                x=df_results['Load'],
                y=df_results['Score_A'],
                mode='markers',
                marker=dict(
                    size=5,
                    color=df_results['Score_A'],
                    colorscale='RdYlGn',
                    showscale=True,
                    colorbar=dict(title="Score"),
                    opacity=0.5,
                    line=dict(width=0)
                ),
                text=[f"{row['Date']}<br>{row['Window']}<br>Load: {row['Load']}<br>Score: {row['Score_A']}" 
                      for _, row in df_results.iterrows()],
                hovertemplate='%{text}<extra></extra>',
                name='Fenêtres'
            ))

            fig1.add_hline(y=0, line_dash="dash", line_color="red", line_width=2,
                          annotation_text="Seuil viabilité")

            fig1.update_layout(
                title=f"Charge LOAD vs Score OCC (Option A) - {tv_detected}",
                xaxis_title="Charge horaire (avions/heure)",
                yaxis_title="Score OCC (max = 60)",
                height=550,
                showlegend=False
            )

            st.plotly_chart(fig1, use_container_width=True)

            # Stats A
            col1, col2, col3 = st.columns(3)
            with col1:
                avg_score_a = df_results['Score_A'].mean()
                st.metric("Score moyen", f"{avg_score_a:.1f}")
            with col2:
                min_score_a = df_results['Score_A'].min()
                st.metric("Score min", f"{min_score_a:.1f}")
            with col3:
                viable_df_a = df_results[df_results['Score_A'] > 30]
                if len(viable_df_a) > 0:
                    mv_a = viable_df_a['Load'].quantile(0.75)
                    st.metric("MV (P75)", f"{mv_a:.0f} av/h")

        with tab2:
            st.markdown(f"**Option B : Trois zones** (seuil = {sustain + tolerance}, PEAK = {peak} av/min)")

            fig2 = go.Figure()

            fig2.add_trace(go.Scatter(
                x=df_results['Load'],
                y=df_results['Score_B'],
                mode='markers',
                marker=dict(
                    size=5,
                    color=df_results['Score_B'],
                    colorscale='RdYlGn',
                    showscale=True,
                    colorbar=dict(title="Score"),
                    opacity=0.5,
                    line=dict(width=0)
                ),
                text=[f"{row['Date']}<br>{row['Window']}<br>Load: {row['Load']}<br>Score: {row['Score_B']}" 
                      for _, row in df_results.iterrows()],
                hovertemplate='%{text}<extra></extra>',
                name='Fenêtres'
            ))

            fig2.add_hline(y=0, line_dash="dash", line_color="red", line_width=2,
                          annotation_text="Seuil viabilité")

            fig2.update_layout(
                title=f"Charge LOAD vs Score OCC (Option B) - {tv_detected}",
                xaxis_title="Charge horaire (avions/heure)",
                yaxis_title="Score OCC (max = 60)",
                height=550,
                showlegend=False
            )

            st.plotly_chart(fig2, use_container_width=True)

            # Stats B
            col1, col2, col3 = st.columns(3)
            with col1:
                avg_score_b = df_results['Score_B'].mean()
                st.metric("Score moyen", f"{avg_score_b:.1f}")
            with col2:
                min_score_b = df_results['Score_B'].min()
                st.metric("Score min", f"{min_score_b:.1f}")
            with col3:
                viable_df_b = df_results[df_results['Score_B'] > 30]
                if len(viable_df_b) > 0:
                    mv_b = viable_df_b['Load'].quantile(0.75)
                    st.metric("MV (P75)", f"{mv_b:.0f} av/h")

        with tab3:
            st.markdown("**Comparaison Option A vs Option B**")

            fig3 = go.Figure()

            fig3.add_trace(go.Scatter(
                x=df_results['Load'],
                y=df_results['Score_A'],
                mode='markers',
                name='Option A',
                marker=dict(size=4, color='#1f77b4', opacity=0.4)
            ))

            fig3.add_trace(go.Scatter(
                x=df_results['Load'],
                y=df_results['Score_B'],
                mode='markers',
                name='Option B',
                marker=dict(size=4, color='#ff7f0e', opacity=0.4)
            ))

            fig3.add_hline(y=0, line_dash="dash", line_color="red", line_width=2)

            fig3.update_layout(
                title="Superposition A vs B",
                xaxis_title="Charge (av/h)",
                yaxis_title="Score OCC",
                height=500
            )

            st.plotly_chart(fig3, use_container_width=True)

            corr = df_results['Score_A'].corr(df_results['Score_B'])
            st.info(f"🔗 Corrélation A-B : **{corr:.3f}**")

        # ============================================
        # ANALYSE TRANCHES
        # ============================================

        st.markdown("### 📊 Analyse par tranche de charge")

        df_results['Load_Bucket'] = pd.cut(
            df_results['Load'], 
            bins=[0, 20, 30, 40, 50, 60, 70, 200],
            labels=['0-20', '20-30', '30-40', '40-50', '50-60', '60-70', '70+']
        )

        tranches = df_results.groupby('Load_Bucket').agg({
            'Score_A': ['mean', 'min', 'max', 'count'],
            'Score_B': ['mean', 'min', 'max']
        }).round(1)

        st.dataframe(tranches, use_container_width=True)

        # ============================================
        # IDENTIFICATION MV
        # ============================================

        st.markdown("### 🎯 Identification MV")

        st.markdown("""
        **MV = Charge maximale** où le score reste **> 30** (50% minutes viables)

        - **P50 (conservateur)** : 50% des fenêtres viables ≤ MV
        - **P75 (recommandé)** : 75% des fenêtres viables ≤ MV ⭐
        - **P90 (optimiste)** : 90% des fenêtres viables ≤ MV
        """)

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("#### 🔹 Option A")

            viable_loads_a = df_results[df_results['Score_A'] > 30]['Load']

            if len(viable_loads_a) > 10:
                mv_p50_a = viable_loads_a.quantile(0.50)
                mv_p75_a = viable_loads_a.quantile(0.75)
                mv_p90_a = viable_loads_a.quantile(0.90)

                st.metric("MV P50", f"{mv_p50_a:.0f} av/h", help="Conservateur")
                st.metric("MV P75 ⭐", f"{mv_p75_a:.0f} av/h", help="Recommandé")
                st.metric("MV P90", f"{mv_p90_a:.0f} av/h", help="Optimiste")

                st.info(f"📊 {len(viable_loads_a)} fenêtres viables (score > 30)")
            else:
                st.warning("Pas assez de données")

        with col2:
            st.markdown("#### 🔸 Option B")

            viable_loads_b = df_results[df_results['Score_B'] > 30]['Load']

            if len(viable_loads_b) > 10:
                mv_p50_b = viable_loads_b.quantile(0.50)
                mv_p75_b = viable_loads_b.quantile(0.75)
                mv_p90_b = viable_loads_b.quantile(0.90)

                st.metric("MV P50", f"{mv_p50_b:.0f} av/h", help="Conservateur")
                st.metric("MV P75 ⭐", f"{mv_p75_b:.0f} av/h", help="Recommandé")
                st.metric("MV P90", f"{mv_p90_b:.0f} av/h", help="Optimiste")

                st.info(f"📊 {len(viable_loads_b)} fenêtres viables (score > 30)")
            else:
                st.warning("Pas assez de données")

        # ============================================
        # HISTOGRAMMES
        # ============================================

        st.markdown("### 📊 Distribution des scores")

        col1, col2 = st.columns(2)

        with col1:
            fig_hist_a = go.Figure()
            fig_hist_a.add_trace(go.Histogram(
                x=df_results['Score_A'],
                nbinsx=30,
                marker_color='#1f77b4',
                name='Option A'
            ))
            fig_hist_a.update_layout(
                title="Distribution Score A",
                xaxis_title="Score",
                yaxis_title="Nombre de fenêtres",
                height=300
            )
            st.plotly_chart(fig_hist_a, use_container_width=True)

        with col2:
            fig_hist_b = go.Figure()
            fig_hist_b.add_trace(go.Histogram(
                x=df_results['Score_B'],
                nbinsx=30,
                marker_color='#ff7f0e',
                name='Option B'
            ))
            fig_hist_b.update_layout(
                title="Distribution Score B",
                xaxis_title="Score",
                yaxis_title="Nombre de fenêtres",
                height=300
            )
            st.plotly_chart(fig_hist_b, use_container_width=True)

        # ============================================
        # EXPORT
        # ============================================

        st.divider()
        st.markdown("### 💾 Export")

        csv_export = df_results.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Télécharger tous les résultats (CSV)",
            data=csv_export,
            file_name=f"mv_sliding20_{tv_detected}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv",
            use_container_width=True
        )

st.markdown("---")
st.markdown(f"*Analyse MV glissante 20min | {tv_detected if 'tv_detected' in locals() else 'TV'} | SUSTAIN={sustain} | PEAK={peak}*")
