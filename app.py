import json
import unicodedata
from collections import defaultdict, Counter
import rapidfuzz.fuzz as fuzz
import pandas as pd
import streamlit as st
import plotly.express as px

st.set_page_config(
    page_title="Dashboard de Posgrados por Ingeniería",
    page_icon="📊",
    layout="centered",
    initial_sidebar_state="auto"
)

# Título general
st.title("📊 Dashboard de Posgrados por Ingeniería")

# ---------- Función de normalización de nombres de universidad / strings ----------
def normalizar_nombre(s: str) -> str:
    s = s.strip().lower()
    s = ''.join(
        ch for ch in unicodedata.normalize('NFD', s)
        if unicodedata.category(ch) != 'Mn'
    )
    return s

# ---------- Función para cargar y procesar datos ----------
def cargar_y_procesar(path_json: str):
    with open(path_json, 'r', encoding='utf-8') as f:
        perfiles = json.load(f)

    pregrados_interes = {
        "Ingeniería de Sistemas",
        "Ingeniería Electrónica",
        "Ingeniería Agroindustrial",
        "Ingeniería Agronómica"
    }
    post_types = ['Especialización', 'Maestría', 'Doctorado', 'Postdoctorado']

    # Filtrar perfiles que tengan al menos uno de los pregrados de interés
    filtered = []
    for perfil in perfiles:
        educ = perfil.get('education', [])
        pregrados_usuario = {
            e.get('degree')
            for e in educ
            if e.get('degree2') == 'Pregrado' and e.get('degree')
        }
        if pregrados_interes.intersection(pregrados_usuario):
            filtered.append(perfil)

    # 1) Cantidad de perfiles por cada Pregrado de interés
    pregrado_counts = Counter()
    # 2) Total de posgrados cursados por cada perfil (para histograma y boxplot)
    posgrados_por_perfil = {}
    # 3) Cantidad de perfiles que cursaron cada tipo de posgrado, por pregrado
    post_counts = {pt: Counter() for pt in post_types}
    # 4) Universidades elegidas por combinación Pregrado – posgrado (normalizado)
    post_inst_users = {pt: defaultdict(lambda: defaultdict(set)) for pt in post_types}

    for perfil in filtered:
        uid = perfil.get('id')
        educ = perfil.get('education', [])

        # Pregrados que este perfil cursó
        pregrados_usuario = {
            e.get('degree')
            for e in educ
            if e.get('degree2') == 'Pregrado' and e.get('degree')
        } & pregrados_interes

        # Para el histograma/boxplot: sumar total de posgrados (independientemente de tipo)
        total_pos = sum(1 for e in educ if e.get('degree2') in post_types)
        posgrados_por_perfil[uid] = total_pos

        # 1) Contar pregrado
        for deg in pregrados_usuario:
            pregrado_counts[deg] += 1

        # 2) Contar posgrados por tipo y pregrado
        tipos_cursados = {e.get('degree2') for e in educ if e.get('degree2') in post_types}
        for pt in tipos_cursados:
            for pg in pregrados_usuario:
                post_counts[pt][pg] += 1

        # 3) Rellenar post_inst_users con universidades normalizadas
        for e in educ:
            tp = e.get('degree2')
            uni = e.get('title')
            if tp in post_types and uni:
                uni_norm = normalizar_nombre(uni)
                for pg in pregrados_usuario:
                    post_inst_users[tp][pg][uni_norm].add(uid)

    # 4) Top universidades por Pregrado – posgrado (hasta 10)
    post_top_unis = {pt: {} for pt in post_types}
    for pt in post_types:
        for pg, inst_dict in post_inst_users[pt].items():
            inst_counter = Counter({uni: len(ids) for uni, ids in inst_dict.items()})
            post_top_unis[pt][pg] = inst_counter.most_common(10)

    return {
        "total_filtrados": len(filtered),
        "pregrado_counts": pregrado_counts,
        "posgrados_por_perfil": posgrados_por_perfil,
        "post_counts": post_counts,
        "post_top_unis": post_top_unis,
        "pregrados_interes": pregrados_interes,
        "post_types": post_types,
        "perfiles_filtrados": filtered
    }

# ---------- Cargar datos ----------
datos = cargar_y_procesar('perfiles_limpios.json')
with open('perfiles_limpios.json', 'r', encoding='utf-8') as f:
    raw_profiles = json.load(f)

# --------------------------------------------------------------
# Crear dos pestañas: "Dashboard" y "Datos"
# --------------------------------------------------------------
tab1, tab2 = st.tabs(["📊 Dashboard", "📋 Datos"])

# ========== PESTAÑA 1: DASHBOARD ==========
with tab1:
    # --------------------------------------------------------------
    #  1) Pie Chart: proporción de estudiantes por Pregrado de interés
    # --------------------------------------------------------------
    st.subheader("📊 Proporción de estudiantes por Pregrado de interés")
    df_pie = pd.DataFrame.from_dict(
        datos["pregrado_counts"], orient="index", columns=["count"]
    ).reset_index().rename(columns={"index": "Pregrado"})
    fig_pie = px.pie(
        df_pie,
        names="Pregrado",
        values="count",
        title="Proporción de Estudiantes por Pregrado",
        hole=0.3
    )
    st.plotly_chart(fig_pie, use_container_width=True)

    st.markdown("---")

    # --------------------------------------------------------------
    # 2) Histograma: distribución de número de posgrados cursados por perfil
    # --------------------------------------------------------------
    st.subheader("📊 Histograma: Número total de posgrados cursados por perfil")

    lista_hist = [{"id": uid, "total_pos": total_pos}
                  for uid, total_pos in datos["posgrados_por_perfil"].items()]
    df_hist = pd.DataFrame(lista_hist)

    max_pos = df_hist["total_pos"].max()
    bins = list(range(0, max_pos + 2))

    fig_hist = px.histogram(
        df_hist,
        x="total_pos",
        color_discrete_sequence=["#636EFA"],
        category_orders={"total_pos": list(range(0, max_pos + 1))},
        nbins=len(bins)-1,
        title="Distribución de Cantidad de Posgrados por Perfil",
        labels={"total_pos": "Número de Posgrados", "count": "Cantidad de Perfiles"}
    )
    fig_hist.update_layout(
        xaxis=dict(
            tickmode="array",
            tickvals=list(range(0, max_pos + 1)),
            ticktext=[str(i) for i in range(0, max_pos + 1)],
            title_text="Número de Posgrados"
        ),
        yaxis=dict(title_text="Cantidad de Perfiles")
    )
    fig_hist.update_traces(texttemplate="%{y}", textposition="outside")
    st.plotly_chart(fig_hist, use_container_width=True)
    st.markdown("---")

    # -----------------------------------------------------------------------
    # 2b) Interactividad: seleccionar un número de posgrados y mostrar detalles
    # -----------------------------------------------------------------------
    st.subheader("🔍 Detalles de perfiles según número de posgrados seleccionados")

    opciones_num_pos = list(range(0, max_pos + 1))
    selected_num = st.selectbox(
        "Selecciona cuántos posgrados cursó el/los perfil(es):",
        opciones_num_pos
    )
    uids_filtrados = df_hist[df_hist["total_pos"] == selected_num]["id"].tolist()

    detalles = []
    for perfil in raw_profiles:
        uid = perfil.get("id")
        if uid in uids_filtrados:
            nombre = perfil.get("name", "Sin nombre")
            lista_estudios = []
            for e in perfil.get("education", []):
                grado2 = e.get("degree2", "").strip()
                titulo = e.get("title", "").strip()
                if grado2 in datos["post_types"]:
                    if grado2 and titulo:
                        lista_estudios.append(f"{grado2}: {titulo}")
                    elif grado2 and not titulo:
                        lista_estudios.append(f"{grado2}")
                    elif titulo:
                        lista_estudios.append(f"{titulo}")
            estudios_concat = "; ".join(lista_estudios) if lista_estudios else "Sin datos de posgrados"
            detalles.append({
                "Nombre": nombre,
                "Total de Posgrados": selected_num,
                "Posgrados (degree2: title)": estudios_concat
            })

    if not detalles:
        st.info(f"No hay perfiles que hayan cursado exactamente {selected_num} posgrados.")
    else:
        df_detalles = pd.DataFrame(detalles)
        st.write(f"Se encontraron {len(df_detalles)} perfil(es) con **{selected_num}** posgrados:")
        st.dataframe(df_detalles, use_container_width=True)

    st.markdown("---")
    
    # --------------------------------------------------------------
    # 4) Gráfico de barras: estudiantes por Pregrado
    # --------------------------------------------------------------
    st.subheader("📈 Gráfico de Barras: Estudiantes por Pregrado de Interés")
    df_barras_pre = pd.DataFrame.from_dict(
        datos["pregrado_counts"], orient="index", columns=["count"]
    ).reset_index().rename(columns={"index": "Pregrado"})
    fig_barras_pre = px.bar(
        df_barras_pre,
        x="Pregrado",
        y="count",
        color="Pregrado",
        title="Cantidad de Estudiantes por Pregrado de Interés",
        labels={"count": "Número de Perfiles"}
    )
    st.plotly_chart(fig_barras_pre, use_container_width=True)
    st.markdown("---")

    # --------------------------------------------------------------
    # 5) Para cada tipo de posgrado: barras con conteos por Pregrado
    # --------------------------------------------------------------
    for pt in datos["post_types"]:
        st.subheader(f"📊 Posgrado: {pt}")
        conteos = datos["post_counts"][pt]
        df_pt = pd.DataFrame.from_dict(
            conteos, orient="index", columns=["count"]
        ).reset_index().rename(columns={"index": "Pregrado"})
        if df_pt.empty:
            st.write("No hay registros para este posgrado.")
        else:
            fig_pt = px.bar(
                df_pt,
                x="Pregrado",
                y="count",
                color="Pregrado",
                title=f"Número de Estudiantes que cursaron {pt} de cada Pregrado",
                labels={"count": "# Perfiles"}
            )
            st.plotly_chart(fig_pt, use_container_width=True)
        st.markdown("---")

    # --------------------------------------------------------------
    # 6) Top universidades elegidas (con selectores)
    # --------------------------------------------------------------
    st.subheader("🎓 Universidades más optadas por Pregrado y Tipo de Posgrado")
    col_sel1, col_sel2 = st.columns(2)
    tipo_seleccionado = col_sel1.selectbox(
        "Selecciona Tipo de Posgrado",
        datos["post_types"]
    )
    pregrado_seleccionado = col_sel2.selectbox(
        "Selecciona Pregrado",
        sorted(datos["pregrados_interes"])
    )

    top_unis = datos["post_top_unis"][tipo_seleccionado].get(pregrado_seleccionado, [])
    if top_unis:
        df_unis = pd.DataFrame(top_unis, columns=["Universidad (normalizada)", "Cantidad de Perfiles"])
        fig_unis = px.bar(
            df_unis,
            x="Universidad (normalizada)",
            y="Cantidad de Perfiles",
            title=f"Top Universidades: {tipo_seleccionado} para {pregrado_seleccionado}",
            labels={"Cantidad de Perfiles": "# Perfiles", "Universidad (normalizada)": "Universidad"}
        )
        st.plotly_chart(fig_unis, use_container_width=True)
        st.dataframe(df_unis, use_container_width=True)
    else:
        st.write("No hay datos de universidades para esta combinación.")
    st.markdown("---")

    # --------------------------------------------------------------
    # 7) Programas de Posgrado más escogidos según Pregrado y Tipo de Posgrado
    # --------------------------------------------------------------
    st.subheader("🎯 Programas de Posgrado más escogidos por combinación Pregrado – Tipo de Posgrado")
    col_p7a, col_p7b = st.columns(2)
    pregrado_sel_p7 = col_p7a.selectbox(
        "Selecciona Pregrado:",
        sorted(datos["pregrados_interes"])
    )
    tipo_sel_p7 = col_p7b.selectbox(
        "Selecciona Tipo de Posgrado:",
        datos["post_types"]
    )
    raw_programas = []
    for perfil in raw_profiles:
        tiene_pre = any(
            (e.get("degree2") == "Pregrado" and e.get("degree") == pregrado_sel_p7)
            for e in perfil.get("education", [])
        )
        if not tiene_pre:
            continue
        for e in perfil.get("education", []):
            if e.get("degree2") == tipo_sel_p7:
                prog = e.get("degree", "").strip()
                if prog:
                    raw_programas.append(normalizar_nombre(prog))

    if not raw_programas:
        st.info(f"No se encontraron programas de **{tipo_sel_p7}** para el Pregrado **{pregrado_sel_p7}**.")
    else:
        counter_crudo = Counter(raw_programas)
        programas_unificados = {}
        usado = set()
        nombres = list(counter_crudo.keys())
        for i, base in enumerate(nombres):
            if base in usado:
                continue
            grupo = {base}
            usado.add(base)
            for otro in nombres[i+1:]:
                if otro in usado:
                    continue
                ratio = fuzz.token_sort_ratio(base, otro)
                if ratio >= 65:
                    grupo.add(otro)
                    usado.add(otro)
            nombre_canonico = max(grupo, key=lambda x: counter_crudo[x])
            total_en_grupo = sum(counter_crudo[v] for v in grupo)
            programas_unificados[nombre_canonico] = total_en_grupo

        df_prog = (
            pd.DataFrame.from_dict(
                programas_unificados, orient="index", columns=["Cantidad de Perfiles que lo eligieron"]
            )
            .reset_index()
            .rename(columns={"index": "Programa de Posgrado"})
            .sort_values(by="Cantidad de Perfiles que lo eligieron", ascending=False)
        )

        top_n = 10
        df_prog_top = df_prog.head(top_n).copy()
        fig_prog = px.bar(
            df_prog_top,
            x="Cantidad de Perfiles que lo eligieron",
            y="Programa de Posgrado",
            orientation="h",
            title=f"Top {top_n} Programas (agrupados) de {tipo_sel_p7} para Pregrado {pregrado_sel_p7}",
            labels={
                "Cantidad de Perfiles que lo eligieron": "# Perfiles",
                "Programa de Posgrado": "Programa Agrupado"
            },
            color_discrete_sequence=["#EF553B"]
        )
        fig_prog.update_layout(yaxis=dict(autorange="reversed"))
        st.plotly_chart(fig_prog, use_container_width=True)

        st.markdown(f"**Listado completo de programas (agrupados) para «{tipo_sel_p7}» en «{pregrado_sel_p7}»:**")
        st.dataframe(df_prog, use_container_width=True)
    st.markdown("---")

    # --------------------------------------------------------------
    # 8) Heatmap: Correlación Pregrado vs Tipo de Posgrado
    # --------------------------------------------------------------
    st.subheader("🔥 Heatmap: Número de estudiantes por Pregrado y Tipo de Posgrado")
    df_heat = pd.DataFrame(
        { pt: datos["post_counts"][pt] for pt in datos["post_types"] }
    ).fillna(0)
    df_heat = df_heat.reindex(index=list(datos["pregrados_interes"]), fill_value=0)

    fig_heat = px.imshow(
        df_heat.values,
        labels=dict(x="Tipo de Posgrado", y="Pregrado", color="Número de Perfiles"),
        x=df_heat.columns.tolist(),
        y=df_heat.index.tolist(),
        text_auto=True,
        aspect="auto",
        color_continuous_scale="Viridis",
        title="Número de Estudiantes por Pregrado y Tipo de Posgrado"
    )
    st.plotly_chart(fig_heat, use_container_width=True)
    st.markdown("---")

    # --------------------------------------------------------------
    # 9) Heatmap interactivo: Certificaciones vs Postgrados por Pregrado
    # --------------------------------------------------------------
    st.subheader("🔥 Heatmap: Certificaciones vs Tipos de Posgrado por Pregrado")
    pregrado_sel = st.selectbox(
        "Selecciona Pregrado para ver Certificaciones vs Postgrados:",
        sorted(datos["pregrados_interes"])
    )
    perfiles_pregrado = []
    for perfil in raw_profiles:
        educ = perfil.get("education", [])
        grados_usuario = {
            e.get("degree")
            for e in educ
            if e.get("degree2") == "Pregrado" and e.get("degree") in datos["pregrados_interes"]
        }
        if pregrado_sel in grados_usuario:
            perfiles_pregrado.append(perfil)

    if not perfiles_pregrado:
        st.info(f"No se encontraron perfiles con Pregrado «{pregrado_sel}».")
    else:
        counter_cert_crudo = Counter()
        perfil_to_certs_norm = {}
        for perfil in perfiles_pregrado:
            uid = perfil.get("id")
            raw_certs = []
            if "certifications" in perfil and isinstance(perfil["certifications"], list):
                for c in perfil["certifications"]:
                    nombre = c.get("name") or c.get("title") or c.get("cert_name")
                    if isinstance(nombre, str) and nombre.strip():
                        raw_certs.append(nombre.strip())
            elif "certification" in perfil and isinstance(perfil["certification"], list):
                for c in perfil["certification"]:
                    nombre = c.get("name") or c.get("title") or c.get("cert_name")
                    if isinstance(nombre, str) and nombre.strip():
                        raw_certs.append(nombre.strip())

            norm_list = []
            for rc in raw_certs:
                rc_norm = normalizar_nombre(rc)
                if rc_norm:
                    norm_list.append(rc_norm)
                    counter_cert_crudo[rc_norm] += 1

            perfil_to_certs_norm[uid] = norm_list

        if not counter_cert_crudo:
            st.info(f"No hay certificaciones registradas para perfiles de «{pregrado_sel}».")
        else:
            programas_unificados_certs = {}
            usado_c = set()
            nombres_c = list(counter_cert_crudo.keys())
            for i, base in enumerate(nombres_c):
                if base in usado_c:
                    continue
                grupo_c = {base}
                usado_c.add(base)
                for otro in nombres_c[i+1:]:
                    if otro in usado_c:
                        continue
                    ratio = fuzz.token_sort_ratio(base, otro)
                    if ratio >= 65:
                        grupo_c.add(otro)
                        usado_c.add(otro)
                canon = max(grupo_c, key=lambda x: counter_cert_crudo[x])
                total_grupo = sum(counter_cert_crudo[x] for x in grupo_c)
                programas_unificados_certs[canon] = total_grupo

            df_certs = (
                pd.DataFrame.from_dict(
                    programas_unificados_certs,
                    orient="index",
                    columns=["Cantidad de Perfiles que la tienen"]
                )
                .reset_index()
                .rename(columns={"index": "Certificación"})
                .sort_values(by="Cantidad de Perfiles que la tienen", ascending=False)
            )
            top10_certs = df_certs["Certificación"].head(10).tolist()

            post_types = datos["post_types"]
            matriz = {cert: {pt: 0 for pt in post_types} for cert in top10_certs}

            for perfil in perfiles_pregrado:
                uid = perfil.get("id")
                certs_norm = perfil_to_certs_norm.get(uid, [])
                certs_en_top10 = set()
                for cn in certs_norm:
                    for canon in top10_certs:
                        if fuzz.token_sort_ratio(cn, canon) >= 65:
                            certs_en_top10.add(canon)
                            break

                tipos_pos_perfil = {
                    e.get("degree2")
                    for e in perfil.get("education", [])
                    if e.get("degree2") in post_types
                }

                for cert in certs_en_top10:
                    for pt in tipos_pos_perfil:
                        matriz[cert][pt] += 1

            df_heat_certs_post = pd.DataFrame.from_dict(matriz, orient="index")
            df_heat_certs_post = df_heat_certs_post.reindex(columns=post_types, fill_value=0)

            fig_certs_post = px.imshow(
                df_heat_certs_post.values,
                labels=dict(x="Tipo de Posgrado", y="Certificación", color="# Perfiles"),
                x=df_heat_certs_post.columns.tolist(),
                y=df_heat_certs_post.index.tolist(),
                text_auto=True,
                aspect="auto",
                color_continuous_scale="Magma",
                title=f"Pregrado «{pregrado_sel}»: Top-10 Certificaciones vs Tipos de Posgrado"
            )
            st.plotly_chart(fig_certs_post, use_container_width=True)
            st.markdown("---")

# ========== PESTAÑA 2: DATOS ==========
with tab2:
    st.subheader("📋 Todos los perfiles filtrados (estructura resumida)")

    filas = []
    # Recorremos SÓLO los perfiles YA filtrados (es decir, que tienen uno de los pregrados de interés)
    for perfil in datos["perfiles_filtrados"]:
        uid = perfil.get("id")
        nombre = perfil.get("name", "Sin nombre")

        # --- Pregrados (solo aquellos de interés) ---
        educ = perfil.get("education", [])
        pregrados_usuario = sorted({
            (e.get("degree") or "").strip()
            for e in educ
            if (e.get("degree2") or "").strip() == "Pregrado"
               and (e.get("degree") or "").strip() in datos["pregrados_interes"]
        })

        # --- Posgrados (solo aquellos con degree2 en datos["post_types"]) ---
        pos_list = []
        for e in educ:
            grado2 = (e.get("degree2") or "").strip()
            titulo = (e.get("degree") or "").strip()
            if grado2 in datos["post_types"]:
                if grado2 and titulo:
                    pos_list.append(f"{grado2}: {titulo}")
                elif grado2 and not titulo:
                    pos_list.append(f"{grado2}")
                elif titulo:
                    pos_list.append(f"{titulo}")

        # --- Certificaciones (raw) ---
        raw_certs = []
        if "certifications" in perfil and isinstance(perfil["certifications"], list):
            for c in perfil["certifications"]:
                nombre_c = c.get("name") or c.get("title") or c.get("cert_name")
                if isinstance(nombre_c, str) and nombre_c.strip():
                    raw_certs.append(nombre_c.strip())
        elif "certification" in perfil and isinstance(perfil["certification"], list):
            for c in perfil["certification"]:
                nombre_c = c.get("name") or c.get("title") or c.get("cert_name")
                if isinstance(nombre_c, str) and nombre_c.strip():
                    raw_certs.append(nombre_c.strip())

        filas.append({
            "ID": uid,
            "Nombre": nombre,
            "Pregrados de Interés": "; ".join(pregrados_usuario) if pregrados_usuario else "—",
            "Posgrados (degree2: title)": "; ".join(pos_list) if pos_list else "—",
            "Certificaciones (raw)": "; ".join(raw_certs) if raw_certs else "—"
        })

    df_todos = pd.DataFrame(filas)
    st.dataframe(df_todos, use_container_width=True)
