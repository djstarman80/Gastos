    # ... (Después de generar proyeccion_list)

    df_proy = pd.DataFrame(proyeccion_list)
    st.table(df_proy)

    # --- NUEVA SECCIÓN: TOTALES Y PROMEDIOS ANUALES ---
    st.subheader("📈 Resumen Anual Proyectado")
    
    # Convertimos los strings formateados de vuelta a float para calcular
    total_anual_m = sum([monto_uy_a_float(d["Marcelo"]) for d in proyeccion_list])
    total_anual_y = sum([monto_uy_a_float(d["Yenny"]) for d in proyeccion_list])
    total_general = total_anual_m + total_anual_y

    col_res1, col_res2, col_res3 = st.columns(3)
    
    with col_res1:
        st.metric("Promedio Mensual Marcelo", f"${float_a_monto_uy(total_anual_m / 12)}")
        st.caption(f"Total 12 meses: ${float_a_monto_uy(total_anual_m)}")

    with col_res2:
        st.metric("Promedio Mensual Yenny", f"${float_a_monto_uy(total_anual_y / 12)}")
        st.caption(f"Total 12 meses: ${float_a_monto_uy(total_anual_y)}")

    with col_res3:
        st.metric("Costo Total Mensual (M+Y)", f"${float_a_monto_uy(total_general / 12)}")
        st.caption(f"Gasto Total 12 meses: ${float_a_monto_uy(total_general)}")

    st.info("💡 **Tip de Ahorro:** Si sus ingresos sumados superan el 'Costo Total Mensual', la diferencia es su capacidad de ahorro real para este año.")
