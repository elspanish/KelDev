import streamlit as st
import os
from dotenv import load_dotenv
from supabase import create_client
from integrations import (
    generate_project_tasks,
    parse_github_pull_request,
    parse_github_repository_url,
    validate_github_code_url,
)

REVIEW_MODE_LABELS = {"direct": "Directa", "layered": "Por capas"}
REVIEW_MODE_VALUES = {
    label: value for value, label in REVIEW_MODE_LABELS.items()
}


def render_task_details(task):
    skills = task.get("habilidades_requeridas") or []
    if isinstance(skills, dict):
        skills = list(skills)
    elif not isinstance(skills, list):
        skills = [str(skills)] if skills else []

    details = (
        ("Habilidades requeridas", ", ".join(str(skill) for skill in skills)),
        ("Instrucciones", task.get("instrucciones")),
        ("Objetivo", task.get("objetivo")),
        ("Restricciones", task.get("restricciones")),
        ("Entregables", task.get("entregables")),
        ("Recursos", task.get("recursos")),
        ("Criterios de aceptación", task.get("criterios_aceptacion")),
        ("Modo de entrega", task.get("modo_entrega")),
        (
            "Flujo de revisión",
            REVIEW_MODE_LABELS.get(task.get("review_mode"), "No definido"),
        ),
        ("Duración estimada", f"{task.get('duracion_estimada_horas') or '—'} horas"),
        ("Dificultad", task.get("dificultad")),
        (
            "Plazo de asignación",
            f"{task.get('claim_timeout_hours') or '—'} horas",
        ),
        (
            "Plazo de revisión por pares",
            f"{task.get('peer_review_timeout_hours') or '—'} horas",
        ),
        (
            "Plazo de revisión del creador",
            f"{task.get('creator_review_timeout_hours') or '—'} horas",
        ),
    )
    for label, value in details:
        st.write(f"**{label}:** {value or '—'}")

    repository_url = task.get("repositorio_url")
    if repository_url:
        st.link_button("Repositorio destino", repository_url)
    if task.get("deadline_at"):
        st.caption(f"Fecha límite actual: {task['deadline_at']}")


# 1. Cargar variables de entorno y configuración
load_dotenv("pcapp/.env")
st.set_page_config(page_title="Plataforma Dev", layout="wide")
st.markdown(
    """
    <style>
    .stApp {
        background: #f8fafc;
        color: #1f2937;
    }
    section[data-testid="stSidebar"] {
        background: #f1f5f9;
        border-right: 1px solid #cbd5e1;
    }
    div[data-testid="stMetric"] {
        background: #ffffff;
        border: 1px solid #cbd5e1;
        border-radius: 6px;
        padding: 10px 12px;
    }
    div.stButton > button {
        border-radius: 5px;
        font-weight: 500;
        min-height: 2rem;
        background: #ffffff;
        border-color: #cbd5e1;
        color: #1f2937;
    }
    div.stButton > button[kind="primary"] {
        background: #2563eb;
        border-color: #2563eb;
        color: #ffffff;
    }
    div.stButton > button[kind="primary"]:hover {
        background: #1d4ed8;
        border-color: #1d4ed8;
        color: #ffffff;
    }
    div[data-testid="stVerticalBlockBorderWrapper"] {
        border-color: #cbd5e1;
        border-radius: 6px;
        background: #ffffff;
    }
    div[data-testid="stDataEditor"] {
        border: 1px solid #cbd5e1;
        border-radius: 6px;
    }
    input, textarea, [data-baseweb="select"] > div {
        background-color: #ffffff !important;
        border-color: #94a3b8 !important;
        border-radius: 5px !important;
    }
    input, textarea, [data-baseweb="select"] input {
        color: #111827 !important;
        -webkit-text-fill-color: #111827 !important;
        caret-color: #111827 !important;
    }
    input::placeholder, textarea::placeholder {
        color: #64748b !important;
        -webkit-text-fill-color: #64748b !important;
        opacity: 1;
    }
    label, [data-testid="stMarkdownContainer"], [data-testid="stCaptionContainer"] {
        color: #1f2937;
    }
    [data-testid="stDataEditor"] * {
        color: #1f2937;
    }
    [data-testid="stAlert"] {
        border-color: #cbd5e1;
    }
    code, .stCode {
        font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    </style>
    """,
    unsafe_allow_html=True,
)

# 2. Inicializar cliente de Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

def get_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

if "supabase_client" not in st.session_state:
    st.session_state.supabase_client = get_supabase()
supabase = st.session_state.supabase_client

# 3. Estado de la sesión
if "user" not in st.session_state:
    st.session_state.user = None

if st.session_state.user is None and st.query_params.get("code"):
    try:
        auth_response = supabase.auth.exchange_code_for_session(
            {"auth_code": st.query_params["code"]}
        )
        st.session_state.user = auth_response.user
        st.query_params.clear()
        st.rerun()
    except Exception as e:
        st.error(f"No se pudo completar el inicio de sesión con GitHub: {e}")

# ---------------------------------------------------------
# PANTALLA 1: AUTENTICACIÓN (LOGIN / REGISTRO)
# ---------------------------------------------------------
if st.session_state.user is None:
    st.title("Plataforma Dev")
    st.caption("Colabora, crea proyectos y desarrolla tus habilidades.")

    with st.container(border=True):
        try:
            oauth_response = supabase.auth.sign_in_with_oauth({
                "provider": "github",
                "options": {
                    "redirect_to": os.getenv("APP_URL") or st.context.url
                },
            })
            st.link_button(
                "Continuar con GitHub",
                oauth_response.url,
                type="primary",
                use_container_width=True,
            )
        except Exception as e:
            st.error(f"Error al iniciar sesión con GitHub: {e}")

    tab_login, tab_registro = st.tabs(["Iniciar sesión", "Crear cuenta"])

    with tab_login:
        with st.container(border=True):
            st.subheader("Bienvenido de nuevo")
            email = st.text_input("Correo electrónico", key="login_email")
            password = st.text_input("Contraseña", type="password", key="login_pass")

            if st.button("Entrar", type="primary", use_container_width=True):
                try:
                    res = supabase.auth.sign_in_with_password(
                        {"email": email, "password": password}
                    )
                    st.session_state.user = res.user
                    st.success("Sesión iniciada.")
                    st.rerun()
                except Exception as e:
                    st.error(
                        "Error al iniciar sesión. Revisa tus credenciales "
                        f"o confirma tu correo. Detalle: {e}"
                    )

    with tab_registro:
        with st.container(border=True):
            st.subheader("Únete a la comunidad")
            reg_email = st.text_input("Correo electrónico", key="reg_email")
            reg_password = st.text_input(
                "Contraseña", type="password", key="reg_pass"
            )
            reg_nombre = st.text_input(
                "Nombre de desarrollador", key="reg_nombre"
            )

            if st.button("Crear cuenta", type="primary", use_container_width=True):
                try:
                    res = supabase.auth.sign_up(
                        {
                            "email": reg_email,
                            "password": reg_password,
                            "options": {"data": {"nombre": reg_nombre.strip()}},
                        }
                    )
                    st.success(
                        "Registro exitoso. Revisa tu bandeja para confirmar "
                        "tu correo antes de entrar. Tu perfil se crea "
                        "automáticamente."
                    )
                except Exception as e:
                    st.error(f"Error al registrarse: {e}")

# ---------------------------------------------------------
# PANTALLA 2: DASHBOARD PRINCIPAL
# ---------------------------------------------------------
else:
    usuario_activo = st.session_state.user.id

    opciones = {
        "Mi Perfil": "Mi Perfil",
        "Crear Proyecto": "Crear Proyecto",
        "Colaborar": "Colaborar",
        "Redactar tareas": "Redactar tareas",
        "Entregar Tarea": "Entregar Tarea",
        "Revisar tareas": "Revisar tareas",
        "Revisión del creador": "Revisión del creador",
        "Mis Entregas": "Mis Entregas",
    }
    if st.session_state.get("opcion_actual") not in opciones.values():
        st.session_state.opcion_actual = "Mi Perfil"

    with st.sidebar:
        st.title("Plataforma Dev")
        st.caption("Tu espacio para construir en comunidad")
        st.divider()
        st.markdown("**Sesión activa**")
        st.write(st.session_state.user.email)
        st.divider()
        st.markdown("**Navegación**")
        for etiqueta, destino in opciones.items():
            if st.button(
                etiqueta,
                key=f"nav_{destino}",
                type=(
                    "primary"
                    if st.session_state.opcion_actual == destino
                    else "secondary"
                ),
                use_container_width=True,
            ):
                st.session_state.opcion_actual = destino
                st.rerun()
        st.divider()
        if st.button("Cerrar sesión", use_container_width=True):
            try:
                supabase.auth.sign_out()
            except Exception as e:
                st.error(f"No se pudo cerrar la sesión: {e}")
            else:
                st.session_state.user = None
                st.rerun()

    opcion = st.session_state.opcion_actual
    st.title("Panel de trabajo")
    st.caption("Gestiona tus proyectos y contribuciones desde un solo lugar.")
    st.divider()

    # --- MI PERFIL ---
    if opcion == "Mi Perfil":
        try:
            perfil_res = (
                supabase.table("profiles")
                .select(
                    "email,nombre,descripcion,habilidades,reputacion,"
                    "tareas_completadas"
                )
                .eq("id", usuario_activo)
                .execute()
            )
        except Exception as e:
            st.error(f"No se pudo cargar tu perfil: {e}")
        else:
            if not perfil_res.data:
                st.error("No se encontró tu perfil.")
            else:
                perfil = perfil_res.data[0]
                habilidades_raw = perfil.get("habilidades") or {}
                if isinstance(habilidades_raw, dict):
                    habilidades = dict(habilidades_raw)
                elif isinstance(habilidades_raw, list):
                    habilidades = {
                        str(nombre).strip(): 0
                        for nombre in habilidades_raw
                        if str(nombre).strip()
                    }
                else:
                    habilidades = {}

                nombre = perfil.get("nombre") or "Desarrollador"
                reputacion_total = int(perfil.get("reputacion") or 0)
                with st.container(border=True):
                    st.markdown(f"### Hola, {nombre}")
                    st.caption(
                        f"Qué bueno tenerte aquí · "
                        f"{perfil.get('email') or st.session_state.user.email}"
                    )
                    metric_col, completed_col = st.columns(2)
                    with metric_col:
                        st.metric("Reputación total", reputacion_total)
                    with completed_col:
                        st.metric(
                            "Tareas completadas",
                            int(perfil.get("tareas_completadas") or 0),
                        )

                st.divider()
                st.subheader("Tus habilidades")
                if habilidades:
                    pares = sorted(
                        habilidades.items(),
                        key=lambda item: str(item[0]).casefold(),
                    )
                    columnas = st.columns(min(3, len(pares)))
                    for indice, (habilidad, puntos) in enumerate(pares):
                        with columnas[indice % len(columnas)]:
                            with st.container(border=True):
                                st.markdown(f"**{habilidad}**")
                                st.metric("Puntos", int(puntos or 0))
                else:
                    with st.container(border=True):
                        st.info(
                            "Aún no tienes habilidades. Añade algunas para "
                            "encontrar tareas compatibles."
                        )

                col_editar, col_agregar = st.columns(2)
                with col_editar:
                    with st.expander("Editar perfil"):
                        with st.form("form_editar_nombre"):
                            nombre_nuevo = st.text_input(
                                "Nombre de desarrollador",
                                value=perfil.get("nombre") or "",
                            )
                            descripcion_nueva = st.text_area(
                                "Descripción para proyectos y tareas",
                                value=perfil.get("descripcion") or "",
                            )
                            guardar_nombre = st.form_submit_button(
                                "Actualizar nombre",
                                use_container_width=True,
                            )
                        if guardar_nombre:
                            if not nombre_nuevo.strip():
                                st.warning("El nombre no puede quedar vacío.")
                            else:
                                try:
                                    (
                                        supabase.table("profiles")
                                        .update({
                                            "nombre": nombre_nuevo.strip(),
                                            "descripcion": descripcion_nueva.strip(),
                                        })
                                        .eq("id", usuario_activo)
                                        .execute()
                                    )
                                    st.success("Nombre actualizado.")
                                    st.rerun()
                                except Exception as e:
                                    st.error(
                                        f"No se pudo actualizar el nombre: {e}"
                                    )

                with col_agregar:
                    with st.expander("Añadir habilidades"):
                        with st.form("form_agregar_habilidades"):
                            nuevas_texto = st.text_input(
                                "Habilidades separadas por comas",
                                placeholder="Python, SQL, Diseño",
                            )
                            agregar = st.form_submit_button(
                                "Guardar habilidades",
                                use_container_width=True,
                            )
                        if agregar:
                            nuevas = [
                                nombre_habilidad.strip()
                                for nombre_habilidad in nuevas_texto.split(",")
                                if nombre_habilidad.strip()
                            ]
                            if not nuevas:
                                st.warning("Escribe al menos una habilidad.")
                            else:
                                for nombre_habilidad in nuevas:
                                    existe = any(
                                        str(actual).casefold()
                                        == nombre_habilidad.casefold()
                                        for actual in habilidades
                                    )
                                    if not existe:
                                        habilidades[nombre_habilidad] = 0
                                try:
                                    (
                                        supabase.table("profiles")
                                        .update({"habilidades": habilidades})
                                        .eq("id", usuario_activo)
                                        .execute()
                                    )
                                    st.success("Habilidades actualizadas.")
                                    st.rerun()
                                except Exception as e:
                                    st.error(
                                        f"No se pudieron actualizar las habilidades: {e}"
                                    )

    # --- OPCIÓN 1: CREAR PROYECTO Y TAREAS ---
    elif opcion == "Crear Proyecto":
        st.subheader("Crear un nuevo proyecto")
        with st.container(border=True):
            if st.session_state.pop("clear_project_form", False):
                st.session_state.project_title = ""
                st.session_state.project_description = ""
            st.write(
                "Define el proyecto y sus tareas, o genera un borrador editable "
                "con Gemini antes de publicarlo."
            )
            proj_titulo = st.text_input("Nombre del proyecto", key="project_title")
            proj_desc = st.text_area(
                "Descripción del proyecto", key="project_description"
            )
            review_mode_label = st.selectbox(
                "Flujo de entrega",
                options=[
                    "Pull Request directa",
                    "Revisión por dos colaboradores y el creador",
                ],
                help=(
                    "La revisión por capas exige dos revisiones independientes "
                    "antes de que el creador registre la PR final."
                ),
            )
            review_mode = (
                "layered"
                if review_mode_label.startswith("Revisión por dos")
                else "direct"
            )
            creation_mode = st.radio(
                "Cómo definir el trabajo",
                ["Redactaré las tareas", "Publicaré módulos para recibir propuestas"],
                horizontal=True,
            )
            if creation_mode == "Publicaré módulos para recibir propuestas":
                st.caption(
                    "Cada módulo se asigna a un colaborador compatible. "
                    "El creador revisa y aprueba las tareas propuestas antes "
                    "de publicarlas."
                )
                if "project_module_drafts" not in st.session_state:
                    st.session_state.project_module_drafts = [{
                        "titulo": "",
                        "descripcion": "",
                        "repositorio_url": "",
                        "habilidades_requeridas": "",
                        "claim_timeout_hours": 72,
                        "creator_review_timeout_hours": 72,
                        "task_claim_timeout_hours": 72,
                        "peer_review_timeout_hours": 48,
                    }]
                    st.session_state.project_module_draft_version = 0
                module_drafts = st.data_editor(
                    st.session_state.project_module_drafts,
                    key=(
                        "project_modules_editor_"
                        f"{st.session_state.project_module_draft_version}"
                    ),
                    num_rows="dynamic",
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "titulo": st.column_config.TextColumn("Módulo"),
                        "descripcion": st.column_config.TextColumn(
                            "Alcance del módulo"
                        ),
                        "repositorio_url": st.column_config.TextColumn(
                            "Repositorio destino de GitHub"
                        ),
                        "habilidades_requeridas": st.column_config.TextColumn(
                            "Habilidades separadas por comas"
                        ),
                        "claim_timeout_hours": st.column_config.NumberColumn(
                            "Plazo de redacción (h)",
                            min_value=1,
                            max_value=720,
                            step=1,
                            required=True,
                        ),
                        "creator_review_timeout_hours": st.column_config.NumberColumn(
                            "Plazo de revisión de propuestas y entregas (h)",
                            min_value=1,
                            max_value=720,
                            step=1,
                            required=True,
                        ),
                        "task_claim_timeout_hours": st.column_config.NumberColumn(
                            "Plazo de ejecución de tareas (h)",
                            min_value=1,
                            max_value=720,
                            step=1,
                            required=True,
                        ),
                        "peer_review_timeout_hours": st.column_config.NumberColumn(
                            "Plazo de revisión entre pares (h)",
                            min_value=1,
                            max_value=720,
                            step=1,
                            required=True,
                        ),
                    },
                )
                if st.button("Publicar proyecto y módulos", type="primary"):
                    modules_to_save = []
                    errors = []
                    for index, module in enumerate(module_drafts, start=1):
                        skills = module.get("habilidades_requeridas") or ""
                        if isinstance(skills, str):
                            skills = skills.split(",")
                        normalized_module = {
                            "titulo": str(module.get("titulo") or "").strip(),
                            "descripcion": str(
                                module.get("descripcion") or ""
                            ).strip(),
                            "repositorio_url": str(
                                module.get("repositorio_url") or ""
                            ).strip(),
                            "habilidades_requeridas": [
                                str(skill).strip()
                                for skill in skills
                                if str(skill).strip()
                            ],
                        }
                        for field in (
                            "claim_timeout_hours",
                            "creator_review_timeout_hours",
                            "task_claim_timeout_hours",
                            "peer_review_timeout_hours",
                        ):
                            value = module.get(field, 72)
                            if isinstance(value, str) and value.isdigit():
                                value = int(value)
                            if (
                                not isinstance(value, (int, float))
                                or isinstance(value, bool)
                                or (isinstance(value, float) and not value.is_integer())
                                or not 1 <= int(value) <= 720
                            ):
                                errors.append(
                                    f"Módulo {index}: {field} debe estar entre 1 y 720 horas"
                                )
                                normalized_module[field] = 0
                            else:
                                normalized_module[field] = int(value)
                        if not normalized_module["titulo"]:
                            errors.append(f"Módulo {index}: falta el título")
                        if not normalized_module["descripcion"]:
                            errors.append(f"Módulo {index}: falta la descripción")
                        try:
                            normalized_module["repositorio_url"] = (
                                validate_github_code_url(
                                    normalized_module["repositorio_url"]
                                )
                            )
                        except ValueError:
                            errors.append(
                                f"Módulo {index}: indica el repositorio HTTPS de GitHub del proyecto"
                            )
                        if not normalized_module["habilidades_requeridas"]:
                            errors.append(f"Módulo {index}: faltan habilidades")
                        modules_to_save.append(normalized_module)
                    if not proj_titulo.strip() or not proj_desc.strip():
                        errors.append("Completa el nombre y descripción del proyecto.")
                    if not modules_to_save:
                        errors.append("Añade al menos un módulo.")
                    if errors:
                        st.warning(" ".join(errors))
                    else:
                        try:
                            supabase.rpc(
                                "create_project_with_modules",
                                {
                                    "p_titulo": proj_titulo.strip(),
                                    "p_descripcion": proj_desc.strip(),
                                    "p_modules": modules_to_save,
                                    "p_review_mode": review_mode,
                                },
                            ).execute()
                            st.success("Proyecto y módulos publicados.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"No se pudieron publicar los módulos: {e}")
                st.stop()

            if "project_task_drafts" not in st.session_state:
                st.session_state.project_task_drafts = [{
                    "titulo": "",
                    "habilidades_requeridas": "",
                    "instrucciones": "",
                    "objetivo": "",
                    "restricciones": "",
                    "entregables": "",
                    "recursos": "",
                    "criterios_aceptacion": "",
                    "modo_entrega": "Pull Request de GitHub",
                    "repositorio_url": "",
                    "duracion_estimada_horas": 4,
                    "dificultad": "Media",
                    "claim_timeout_hours": 72,
                    "peer_review_timeout_hours": 48,
                    "creator_review_timeout_hours": 72,
                    "review_mode": REVIEW_MODE_LABELS[review_mode],
                }]
                st.session_state.project_task_draft_version = 0
            for task_draft in st.session_state.project_task_drafts:
                task_draft.setdefault(
                    "review_mode", REVIEW_MODE_LABELS[review_mode]
                )

            if st.button(
                "Generar borrador con Google AI Studio",
                disabled=not proj_titulo.strip() or not proj_desc.strip(),
            ):
                try:
                    generated = generate_project_tasks(
                        proj_titulo.strip(),
                        proj_desc.strip(),
                    )
                    st.session_state.project_task_drafts = [
                        {
                            **task,
                            "habilidades_requeridas": ", ".join(
                                task["habilidades_requeridas"]
                            ),
                            "repositorio_url": "",
                            "claim_timeout_hours": 72,
                            "peer_review_timeout_hours": 48,
                            "creator_review_timeout_hours": 72,
                            "review_mode": REVIEW_MODE_LABELS[review_mode],
                        }
                        for task in generated
                    ]
                    st.session_state.project_task_draft_version += 1
                    st.success(
                        "Borrador generado. Revísalo y edítalo antes de guardar."
                    )
                    st.rerun()
                except Exception as e:
                    st.error(f"No se pudieron generar las tareas: {e}")

            st.markdown("#### Tareas del proyecto (editables)")
            st.caption(
                "Puedes editar las celdas y añadir o eliminar filas directamente "
                "en la tabla. Los plazos se expresan en horas y se aplican en "
                "cada etapa del ciclo de vida."
            )
            editor_key = (
                f"project_tasks_editor_"
                f"{st.session_state.project_task_draft_version}"
            )
            edited_tasks = st.data_editor(
                st.session_state.project_task_drafts,
                key=editor_key,
                num_rows="dynamic",
                use_container_width=True,
                hide_index=True,
                column_config={
                    "titulo": st.column_config.TextColumn("Título"),
                    "habilidades_requeridas": st.column_config.TextColumn(
                        "Habilidades (separadas por comas)"
                    ),
                    "instrucciones": st.column_config.TextColumn("Instrucciones"),
                    "objetivo": st.column_config.TextColumn("Objetivo"),
                    "restricciones": st.column_config.TextColumn("Restricciones"),
                    "entregables": st.column_config.TextColumn("Entregables"),
                    "recursos": st.column_config.TextColumn("Recursos"),
                    "criterios_aceptacion": st.column_config.TextColumn(
                        "Criterios de aceptación"
                    ),
                    "modo_entrega": st.column_config.TextColumn("Modo de entrega"),
                    "review_mode": st.column_config.SelectboxColumn(
                        "Flujo de revisión",
                        options=list(REVIEW_MODE_VALUES),
                        required=True,
                    ),
                    "repositorio_url": st.column_config.TextColumn(
                        "Repositorio destino (GitHub)"
                    ),
                    "duracion_estimada_horas": st.column_config.NumberColumn(
                        "Duración estimada (horas)",
                        min_value=1,
                        max_value=8,
                        step=1,
                        required=True,
                    ),
                    "dificultad": st.column_config.SelectboxColumn(
                        "Dificultad",
                        options=["Baja", "Media", "Alta"],
                        required=True,
                    ),
                    "claim_timeout_hours": st.column_config.NumberColumn(
                        "Plazo de ejecución (h)",
                        min_value=1,
                        max_value=720,
                        step=1,
                        required=True,
                    ),
                    "peer_review_timeout_hours": st.column_config.NumberColumn(
                        "Plazo de revisión entre pares (h)",
                        min_value=1,
                        max_value=720,
                        step=1,
                        required=True,
                    ),
                    "creator_review_timeout_hours": st.column_config.NumberColumn(
                        "Plazo de revisión del creador (h)",
                        min_value=1,
                        max_value=720,
                        step=1,
                        required=True,
                    ),
                },
            )

            if st.button("Guardar proyecto y tareas", type="primary"):
                if not proj_titulo.strip() or not proj_desc.strip():
                    st.warning("Completa el nombre y la descripción del proyecto.")
                elif not edited_tasks:
                    st.warning("Añade al menos una tarea.")
                else:
                    tasks_to_save = []
                    missing_fields = []
                    for index, task in enumerate(edited_tasks, start=1):
                        normalized = {
                            key: str(task.get(key) or "").strip()
                            for key in (
                                "titulo",
                                "instrucciones",
                                "objetivo",
                                "restricciones",
                                "entregables",
                                "recursos",
                                "criterios_aceptacion",
                                "modo_entrega",
                                "repositorio_url",
                                "dificultad",
                                "review_mode",
                                "claim_timeout_hours",
                                "peer_review_timeout_hours",
                                "creator_review_timeout_hours",
                            )
                        }
                        duration = task.get("duracion_estimada_horas")
                        if isinstance(duration, str) and duration.isdigit():
                            duration = int(duration)
                        duration_valid = (
                            isinstance(duration, (int, float))
                            and not isinstance(duration, bool)
                            and (
                                not isinstance(duration, float)
                                or duration.is_integer()
                            )
                        )
                        if not duration_valid:
                            missing_fields.append(
                                f"Tarea {index}: duración estimada inválida"
                            )
                            normalized["duracion_estimada_horas"] = 0
                        else:
                            normalized["duracion_estimada_horas"] = int(duration)
                            if not 1 <= normalized["duracion_estimada_horas"] <= 8:
                                missing_fields.append(
                                    f"Tarea {index}: duración entre 1 y 8 horas"
                                )
                        skills = task.get("habilidades_requeridas") or []
                        if isinstance(skills, str):
                            skills = skills.split(",")
                        normalized["habilidades_requeridas"] = [
                            str(skill).strip()
                            for skill in skills
                            if str(skill).strip()
                        ]
                        normalized["review_mode"] = REVIEW_MODE_VALUES.get(
                            normalized["review_mode"], ""
                        )
                        for field, value in normalized.items():
                            if not value:
                                missing_fields.append(f"Tarea {index}: {field}")
                        try:
                            normalized["repositorio_url"] = (
                                validate_github_code_url(
                                    normalized["repositorio_url"]
                                )
                            )
                        except ValueError:
                            missing_fields.append(
                                f"Tarea {index}: repositorio_url debe ser un enlace HTTPS de GitHub"
                            )
                        if not normalized["habilidades_requeridas"]:
                            missing_fields.append(
                                f"Tarea {index}: habilidades_requeridas"
                            )
                        for timeout_field in (
                            "claim_timeout_hours",
                            "peer_review_timeout_hours",
                            "creator_review_timeout_hours",
                        ):
                            timeout = task.get(timeout_field)
                            if isinstance(timeout, str) and timeout.isdigit():
                                timeout = int(timeout)
                            if (
                                not isinstance(timeout, (int, float))
                                or isinstance(timeout, bool)
                                or (isinstance(timeout, float) and not timeout.is_integer())
                                or not 1 <= int(timeout) <= 720
                            ):
                                missing_fields.append(
                                    f"Tarea {index}: {timeout_field} debe estar entre 1 y 720 horas"
                                )
                                normalized[timeout_field] = 0
                            else:
                                normalized[timeout_field] = int(timeout)
                        if normalized["dificultad"].casefold() not in {
                            "baja",
                            "media",
                            "alta",
                        }:
                            missing_fields.append(
                                f"Tarea {index}: dificultad debe ser "
                                "Baja, Media o Alta"
                            )
                        else:
                            normalized["dificultad"] = (
                                normalized["dificultad"].capitalize()
                            )
                        tasks_to_save.append(normalized)

                    if missing_fields:
                        st.warning(
                            "Completa los campos obligatorios: "
                            + ", ".join(missing_fields)
                        )
                    else:
                        try:
                            supabase.rpc(
                                "create_project_with_workflow",
                                {
                                    "p_titulo": proj_titulo.strip(),
                                    "p_descripcion": proj_desc.strip(),
                                    "p_tasks": tasks_to_save,
                                    "p_review_mode": review_mode,
                                },
                            ).execute()
                            st.success(
                                f"Proyecto '{proj_titulo.strip()}' y "
                                f"{len(tasks_to_save)} tareas creados."
                            )
                            st.session_state.project_task_drafts = [{
                                "titulo": "",
                                "habilidades_requeridas": "",
                                "instrucciones": "",
                                "objetivo": "",
                                "restricciones": "",
                                "entregables": "",
                                "recursos": "",
                                "criterios_aceptacion": "",
                                "modo_entrega": "Pull Request de GitHub",
                                "duracion_estimada_horas": 4,
                                "dificultad": "Media",
                                "review_mode": REVIEW_MODE_LABELS[review_mode],
                                "repositorio_url": "",
                                "claim_timeout_hours": 72,
                                "peer_review_timeout_hours": 48,
                                "creator_review_timeout_hours": 72,
                            }]
                            st.session_state.project_task_draft_version += 1
                            st.session_state.clear_project_form = True
                            st.rerun()
                        except Exception as e:
                            st.error(f"No se pudo guardar el proyecto: {e}")

    # --- OPCIÓN 2: COLABORAR ---
    elif opcion == "Colaborar":
        st.subheader("Tareas disponibles")
        with st.container(border=True):
            try:
                res_pendiente = (
                    supabase.table("tasks")
                    .select("*")
                    .eq("asignado_a", usuario_activo)
                    .eq("estado", "en_progreso")
                    .execute()
                )
            except Exception as e:
                st.error(f"No se pudieron cargar tus tareas: {e}")
            else:
                if res_pendiente.data:
                    tarea_actual = res_pendiente.data[0]
                    st.warning(
                        f"Ya tienes una tarea en progreso: "
                        f"**{tarea_actual['titulo']}**"
                    )
                    if tarea_actual.get("deadline_at"):
                        st.caption(
                            f"Plazo de esta asignación: "
                            f"{tarea_actual['deadline_at']}"
                        )
                    render_task_details(tarea_actual)
                    try:
                        latest_contribution = (
                            supabase.table("contributions")
                            .select("workflow_state,creator_feedback")
                            .eq("task_id", tarea_actual["id"])
                            .eq("usuario_id", usuario_activo)
                            .order("id", desc=True)
                            .limit(1)
                            .execute()
                        )
                        if (
                            latest_contribution.data
                            and latest_contribution.data[0]["workflow_state"]
                            == "changes_requested"
                        ):
                            st.warning(
                                latest_contribution.data[0].get(
                                    "creator_feedback"
                                )
                                or "Se solicitaron cambios en la última entrega."
                            )
                    except Exception as e:
                        st.error(
                            f"No se pudo cargar el feedback de la entrega: {e}"
                        )
                else:
                    try:
                        active_modules = (
                            supabase.table("project_modules")
                            .select("id,titulo")
                            .eq("asignado_a", usuario_activo)
                            .eq("estado", "en_progreso")
                            .execute()
                        )
                    except Exception as e:
                        st.error(f"No se pudo comprobar tu módulo asignado: {e}")
                    else:
                        if active_modules.data:
                            module_title = active_modules.data[0]["titulo"]
                            st.info(
                                f"Ya tienes asignado el módulo «{module_title}». "
                                "Termina de redactar sus tareas antes de aceptar "
                                "otra asignación."
                            )
                            if st.button(
                                "Continuar con mi módulo",
                                key="continue_assigned_module",
                            ):
                                st.session_state.opcion_actual = "Redactar tareas"
                                st.rerun()
                        else:
                            try:
                                compatible = (
                                    supabase.rpc("find_compatible_tasks")
                                    .execute()
                                    .data
                                    or []
                                )
                            except Exception as e:
                                st.error(
                                    f"No se pudieron buscar tareas compatibles: {e}"
                                )
                            else:
                                if not compatible:
                                    st.info(
                                        "No hay tareas pendientes que coincidan con "
                                        "tus habilidades. Añade habilidades en Mi Perfil "
                                        "o vuelve más tarde."
                                    )
                                for task in compatible:
                                    with st.container(border=True):
                                        st.markdown(f"### {task['titulo']}")
                                        render_task_details(task)
                                        if st.button(
                                            "Colaborar en esta tarea",
                                            key=f"claim_task_{task['id']}",
                                            type="primary",
                                        ):
                                            try:
                                                supabase.rpc(
                                                    "claim_task",
                                                    {"p_task_id": str(task["id"])},
                                                ).execute()
                                                st.success(
                                                    f"Se te asignó '{task['titulo']}'."
                                                )
                                                st.rerun()
                                            except Exception as e:
                                                st.error(
                                                    "No se pudo asignar la tarea. "
                                                    f"Puede que otro colaborador ya "
                                                    f"la haya aceptado: {e}"
                                                )

    # --- REDACTAR TAREAS PARA UN MÓDULO ---
    elif opcion == "Redactar tareas":
        st.subheader("Redactar tareas para un módulo")
        try:
            assigned_modules = (
                supabase.table("project_modules")
                .select(
                    "id,project_id,titulo,descripcion,repositorio_url,"
                    "deadline_at,estado,review_mode"
                )
                .eq("asignado_a", usuario_activo)
                .eq("estado", "en_progreso")
                .execute()
            )
        except Exception as e:
            st.error(f"No se pudo cargar tu módulo: {e}")
            assigned_modules = None
        if assigned_modules and assigned_modules.data:
            module = assigned_modules.data[0]
            st.markdown(f"### {module['titulo']}")
            st.write(module.get("descripcion") or "—")
            st.caption(f"Plazo de redacción: {module.get('deadline_at') or '—'}")
            try:
                last_proposal = (
                    supabase.table("module_task_proposals")
                    .select("feedback,estado")
                    .eq("module_id", module["id"])
                    .eq("proposer_id", usuario_activo)
                    .order("created_at", desc=True)
                    .limit(1)
                    .execute()
                )
                if (
                    last_proposal.data
                    and last_proposal.data[0]["estado"] == "cambios_solicitados"
                ):
                    st.warning(
                        last_proposal.data[0].get("feedback")
                        or "El creador solicitó cambios."
                    )
            except Exception as e:
                st.error(f"No se pudo cargar la respuesta del creador: {e}")
            draft_key = f"module_task_drafts_{module['id']}"
            version_key = f"module_task_draft_version_{module['id']}"
            if draft_key not in st.session_state:
                st.session_state[draft_key] = [{
                    "titulo": "",
                    "habilidades_requeridas": "",
                    "instrucciones": "",
                    "objetivo": "",
                    "restricciones": "",
                    "entregables": "",
                    "recursos": "",
                    "criterios_aceptacion": "",
                    "modo_entrega": "Pull Request de GitHub",
                    "repositorio_url": module["repositorio_url"],
                    "duracion_estimada_horas": 4,
                    "dificultad": "Media",
                    "review_mode": REVIEW_MODE_LABELS[
                        module.get("review_mode", "direct")
                    ],
                }]
                st.session_state[version_key] = 0
            for task_draft in st.session_state[draft_key]:
                task_draft.setdefault(
                    "review_mode",
                    REVIEW_MODE_LABELS[module.get("review_mode", "direct")],
                )
            proposed_tasks = st.data_editor(
                st.session_state[draft_key],
                key=f"module_task_editor_{module['id']}_{st.session_state[version_key]}",
                num_rows="dynamic",
                use_container_width=True,
                hide_index=True,
                column_config={
                    "titulo": st.column_config.TextColumn("Título"),
                    "habilidades_requeridas": st.column_config.TextColumn(
                        "Habilidades separadas por comas"
                    ),
                    "instrucciones": st.column_config.TextColumn("Instrucciones"),
                    "objetivo": st.column_config.TextColumn("Objetivo"),
                    "restricciones": st.column_config.TextColumn("Restricciones"),
                    "entregables": st.column_config.TextColumn("Entregables"),
                    "recursos": st.column_config.TextColumn("Recursos"),
                    "criterios_aceptacion": st.column_config.TextColumn(
                        "Criterios de aceptación"
                    ),
                    "modo_entrega": st.column_config.TextColumn("Modo de entrega"),
                    "review_mode": st.column_config.SelectboxColumn(
                        "Flujo de revisión",
                        options=list(REVIEW_MODE_VALUES),
                        required=True,
                    ),
                    "repositorio_url": st.column_config.TextColumn(
                        "Repositorio destino (definido por creador)",
                        disabled=True,
                    ),
                    "duracion_estimada_horas": st.column_config.NumberColumn(
                        "Estimación (h)", min_value=1, max_value=8, step=1
                    ),
                    "dificultad": st.column_config.SelectboxColumn(
                        "Dificultad", options=["Baja", "Media", "Alta"]
                    ),
                },
            )
            if st.button(
                "Enviar propuesta al creador",
                type="primary",
                key=f"submit_module_proposal_{module['id']}",
            ):
                tasks_to_propose = []
                errors = []
                for index, row in enumerate(proposed_tasks, start=1):
                    task_fields = (
                        "titulo",
                        "instrucciones",
                        "objetivo",
                        "restricciones",
                        "entregables",
                        "recursos",
                        "criterios_aceptacion",
                        "modo_entrega",
                        "repositorio_url",
                        "dificultad",
                        "review_mode",
                    )
                    normalized_task = {
                        field: str(row.get(field) or "").strip()
                        for field in task_fields
                    }
                    normalized_task["repositorio_url"] = module["repositorio_url"]
                    normalized_task["review_mode"] = REVIEW_MODE_VALUES.get(
                        normalized_task["review_mode"], ""
                    )
                    for field, value in normalized_task.items():
                        if not value:
                            errors.append(f"Tarea {index}: falta {field}")
                    raw_skills = row.get("habilidades_requeridas") or ""
                    if isinstance(raw_skills, str):
                        raw_skills = raw_skills.split(",")
                    normalized_task["habilidades_requeridas"] = [
                        str(skill).strip()
                        for skill in raw_skills
                        if str(skill).strip()
                    ]
                    if not normalized_task["habilidades_requeridas"]:
                        errors.append(f"Tarea {index}: añade habilidades")
                    duration = row.get("duracion_estimada_horas")
                    if isinstance(duration, str) and duration.isdigit():
                        duration = int(duration)
                    if (
                        not isinstance(duration, (int, float))
                        or isinstance(duration, bool)
                        or (isinstance(duration, float) and not duration.is_integer())
                        or not 1 <= int(duration) <= 8
                    ):
                        errors.append(
                            f"Tarea {index}: la estimación debe ser de 1 a 8 horas"
                        )
                    else:
                        normalized_task["duracion_estimada_horas"] = int(duration)
                    if normalized_task["dificultad"] not in {
                        "Baja",
                        "Media",
                        "Alta",
                    }:
                        errors.append(f"Tarea {index}: dificultad no válida")
                    tasks_to_propose.append(normalized_task)
                if not tasks_to_propose:
                    errors.append("Añade al menos una tarea.")
                if errors:
                    st.warning(" ".join(errors))
                else:
                    try:
                        supabase.rpc(
                            "submit_module_task_proposal",
                            {
                                "p_module_id": module["id"],
                                "p_tasks": tasks_to_propose,
                            },
                        ).execute()
                        st.success("Propuesta enviada al creador.")
                        st.session_state[draft_key] = [{
                            "titulo": "",
                            "habilidades_requeridas": "",
                            "instrucciones": "",
                            "objetivo": "",
                            "restricciones": "",
                            "entregables": "",
                            "recursos": "",
                            "criterios_aceptacion": "",
                            "modo_entrega": "Pull Request de GitHub",
                            "repositorio_url": module["repositorio_url"],
                            "duracion_estimada_horas": 4,
                            "dificultad": "Media",
                            "review_mode": REVIEW_MODE_LABELS[
                                module.get("review_mode", "direct")
                            ],
                        }]
                        st.session_state[version_key] += 1
                        st.rerun()
                    except Exception as e:
                        st.error(f"No se pudo enviar la propuesta: {e}")
        else:
            try:
                own_proposals = (
                    supabase.table("module_task_proposals")
                    .select("id,module_id,estado,feedback,created_at")
                    .eq("proposer_id", usuario_activo)
                    .order("created_at", desc=True)
                    .limit(10)
                    .execute()
                )
                if own_proposals.data:
                    st.subheader("Tus propuestas recientes")
                    proposal_module_ids = {
                        proposal["module_id"] for proposal in own_proposals.data
                    }
                    module_titles = {}
                    for module_id in proposal_module_ids:
                        result = (
                            supabase.table("project_modules")
                            .select("id,titulo")
                            .eq("id", module_id)
                            .execute()
                        )
                        if result.data:
                            module_titles[module_id] = result.data[0]["titulo"]
                    for proposal in own_proposals.data:
                        st.write(
                            f"**{module_titles.get(proposal['module_id'], 'Módulo')}** · "
                            f"{proposal['estado']}"
                        )
                        if proposal.get("feedback"):
                            st.warning(proposal["feedback"])
            except Exception as e:
                st.error(f"No se pudo cargar el estado de tus propuestas: {e}")
            try:
                compatible_modules = (
                    supabase.rpc("find_compatible_modules").execute().data or []
                )
            except Exception as e:
                st.error(f"No se pudieron buscar módulos compatibles: {e}")
                compatible_modules = []
            if not compatible_modules:
                st.info(
                    "No hay módulos disponibles que coincidan con tus habilidades."
                )
            for module in compatible_modules:
                with st.container(border=True):
                    st.markdown(f"### {module['titulo']}")
                    st.caption(f"Proyecto: {module['project_id']}")
                    st.write(module.get("descripcion") or "—")
                    st.write(
                        f"Habilidades requeridas: "
                        f"{', '.join(module.get('habilidades_requeridas') or [])}"
                    )
                    if st.button(
                        "Redactar tareas",
                        key=f"claim_module_{module['id']}",
                        type="primary",
                    ):
                        try:
                            supabase.rpc(
                                "claim_project_module",
                                {"p_module_id": module["id"]},
                            ).execute()
                            st.success("El módulo se te ha asignado.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"No se pudo asignar el módulo: {e}")

    # --- OPCIÓN 3: ENTREGAR TAREA ---
    elif opcion == "Entregar Tarea":
        st.subheader("Entregar tarea")
        with st.container(border=True):
            try:
                res_tarea = (
                    supabase.table("tasks")
                    .select(
                        "id,titulo,instrucciones,objetivo,recursos,"
                        "restricciones,entregables,criterios_aceptacion,modo_entrega,"
                        "duracion_estimada_horas,dificultad,project_id,deadline_at,"
                        "repositorio_url,habilidades_requeridas,review_mode,"
                        "claim_timeout_hours,peer_review_timeout_hours,"
                        "creator_review_timeout_hours,module_id"
                    )
                    .eq("asignado_a", usuario_activo)
                    .eq("estado", "en_progreso")
                    .execute()
                )
            except Exception as e:
                st.error(f"No se pudo cargar tu tarea: {e}")
            else:
                if not res_tarea.data:
                    st.info("No tienes tareas en progreso para entregar.")
                else:
                    tarea = res_tarea.data[0]
                    st.markdown(f"### {tarea['titulo']}")
                    render_task_details(tarea)
                    task_review_mode = tarea.get("review_mode")
                    if task_review_mode == "layered":
                        st.caption(
                            "La entrega pasa a dos revisores; al ser aceptada, "
                            "el creador registra y fusiona la PR final."
                        )
                        github_url = st.text_input(
                            "Enlace HTTPS al código en GitHub",
                            help="Puede ser el repositorio, un commit o un archivo.",
                        )
                        submit_label = "Enviar a revisión"
                    else:
                        github_url = st.text_input(
                            "Enlace a la Pull Request de GitHub"
                        )
                        submit_label = "Enviar Pull Request"
                    if task_review_mode not in {"direct", "layered"}:
                        st.error("La tarea no tiene un flujo de revisión válido.")
                    if st.button(
                        submit_label,
                        type="primary",
                        disabled=task_review_mode not in {"direct", "layered"},
                    ):
                        try:
                            if task_review_mode == "layered":
                                code_url = validate_github_code_url(github_url)
                                supabase.rpc(
                                    "submit_layered_task_code",
                                    {
                                        "p_task_id": str(tarea["id"]),
                                        "p_code_url": code_url,
                                    },
                                ).execute()
                                st.success(
                                    "Entrega enviada. Dos colaboradores han "
                                    "recibido una revisión."
                                )
                            else:
                                owner, repository, pr_number = (
                                    parse_github_pull_request(github_url)
                                )
                                target_owner, target_repository = (
                                    parse_github_repository_url(
                                        tarea["repositorio_url"]
                                    )
                                )
                                if (
                                    owner.casefold() != target_owner.casefold()
                                    or repository.casefold()
                                    != target_repository.casefold()
                                ):
                                    raise ValueError(
                                        "La Pull Request debe pertenecer al repositorio destino de la tarea."
                                    )
                                supabase.rpc(
                                    "submit_task_pr",
                                    {
                                        "p_task_id": str(tarea["id"]),
                                        "p_pr_url": github_url.strip(),
                                        "p_github_owner": owner,
                                        "p_github_repo": repository,
                                        "p_github_pr_number": pr_number,
                                    },
                                ).execute()
                                try:
                                    check_result = supabase.functions.invoke(
                                        "check-pull-request",
                                        {"body": {"task_id": str(tarea["id"])}},
                                    )
                                    check_data = (
                                        check_result.get("data", check_result)
                                        if isinstance(check_result, dict)
                                        else {}
                                    )
                                    if check_data.get("status") == "merged":
                                        st.success(
                                            "GitHub confirma el merge; la tarea "
                                            "se completó."
                                        )
                                    elif check_data.get("status") == "closed":
                                        st.warning(
                                            "La PR se cerró sin merge; la tarea "
                                            "volvió a estar disponible."
                                        )
                                    else:
                                        st.success(
                                            "Pull Request registrada. GitHub "
                                            "notificará el merge automáticamente."
                                        )
                                except Exception as e:
                                    st.warning(
                                        "La Pull Request se registró, pero no se "
                                        "pudo consultar su estado inicial. El "
                                        f"webhook detectará cambios futuros: {e}"
                                    )
                            st.rerun()
                        except ValueError as e:
                            st.error(str(e))
                        except Exception as e:
                            st.error(f"No se pudo enviar la entrega: {e}")

    # --- REVISIONES ENTRE COLABORADORES ---
    elif opcion == "Revisar tareas":
        try:
            reviews = (
                supabase.table("task_reviews")
                .select(
                    "id,task_id,contribution_id,deadline_at,decision"
                )
                .eq("reviewer_id", usuario_activo)
                .eq("decision", "pending")
                .order("deadline_at")
                .execute()
            )
            if not reviews.data:
                st.info("No tienes revisiones pendientes.")
            else:
                for review in reviews.data:
                    task_response = (
                        supabase.table("tasks")
                        .select(
                            "id,titulo,instrucciones,objetivo,"
                            "restricciones,entregables,criterios_aceptacion,recursos,"
                            "habilidades_requeridas,modo_entrega,review_mode,"
                            "duracion_estimada_horas,dificultad,project_id,"
                            "repositorio_url,claim_timeout_hours,"
                            "peer_review_timeout_hours,creator_review_timeout_hours"
                        )
                        .eq("id", review["task_id"])
                        .execute()
                    )
                    contribution_response = (
                        supabase.table("contributions")
                        .select("code_url,workflow_state")
                        .eq("id", review["contribution_id"])
                        .execute()
                    )
                    if not task_response.data or not contribution_response.data:
                        st.warning(
                            "Una revisión ya no está disponible; actualiza "
                            "la pantalla."
                        )
                        continue
                    task = task_response.data[0]
                    contribution = contribution_response.data[0]
                    with st.container(border=True):
                        st.markdown(f"### {task['titulo']}")
                        st.caption(f"ID de tarea: {task['id']}")
                        st.caption(f"Plazo: {review['deadline_at']}")
                        render_task_details(task)
                        st.link_button(
                            "Abrir entrega en GitHub",
                            contribution["code_url"],
                        )
                        with st.form(f"review_form_{review['id']}"):
                            review_choice = st.selectbox(
                                "Decisión",
                                [
                                    "Aceptar",
                                    "Solicitar cambios",
                                    "Editar y aceptar",
                                ],
                                key=f"review_choice_{review['id']}",
                            )
                            feedback = st.text_area(
                                "Motivo o notas para el colaborador",
                                key=f"review_feedback_{review['id']}",
                            )
                            revised_url = st.text_input(
                                "Enlace al código actualizado (si editaste)",
                                key=f"review_code_{review['id']}",
                            )
                            send_review = st.form_submit_button(
                                "Enviar revisión",
                                type="primary",
                            )
                        if send_review:
                            decision = {
                                "Aceptar": "accepted",
                                "Solicitar cambios": "changes_requested",
                                "Editar y aceptar": "edited",
                            }[review_choice]
                            try:
                                supabase.rpc(
                                    "review_layered_task",
                                    {
                                        "p_contribution_id": str(
                                            review["contribution_id"]
                                        ),
                                        "p_decision": decision,
                                        "p_feedback": feedback.strip(),
                                        "p_revised_code_url": (
                                            validate_github_code_url(revised_url)
                                            if decision == "edited"
                                            else None
                                        ),
                                    },
                                ).execute()
                                st.success("Revisión guardada.")
                                st.rerun()
                            except ValueError as e:
                                st.error(str(e))
                            except Exception as e:
                                st.error(f"No se pudo guardar la revisión: {e}")
        except Exception as e:
            st.error(f"No se pudieron cargar las revisiones: {e}")

    # --- REVISIÓN FINAL DEL CREADOR ---
    elif opcion == "Revisión del creador":
        st.subheader("Revisión del creador")
        try:
            pending = (
                supabase.table("contributions")
                .select(
                    "id,task_id,code_url,github_pr_url,workflow_state,"
                    "creator_feedback,usuario_id"
                )
                .in_("workflow_state", ["awaiting_creator", "awaiting_merge"])
                .order("id")
                .execute()
            )
            creator_items = []
            for contribution in pending.data or []:
                task_response = (
                    supabase.table("tasks")
                    .select(
                        "id,titulo,project_id,instrucciones,objetivo,"
                        "restricciones,entregables,criterios_aceptacion,"
                        "deadline_at,repositorio_url,review_mode"
                    )
                    .eq("id", contribution["task_id"])
                    .execute()
                )
                if not task_response.data:
                    continue
                task = task_response.data[0]
                project_response = (
                    supabase.table("projects")
                    .select("owner_id,titulo,review_mode")
                    .eq("id", task["project_id"])
                    .execute()
                )
                if (
                    project_response.data
                    and project_response.data[0]["owner_id"] == usuario_activo
                    and task["review_mode"] == "layered"
                ):
                    creator_items.append(
                        (contribution, task, project_response.data[0])
                    )
            if not creator_items:
                st.info("No hay entregas pendientes de tu decisión.")
            for contribution, task, project in creator_items:
                with st.container(border=True):
                    st.markdown(f"### {task['titulo']}")
                    st.caption(
                        f"{project['titulo']} · tarea {task['id']} · "
                        f"colaborador {contribution['usuario_id']}"
                    )
                    st.write(
                        f"**Criterios:** "
                        f"{task.get('criterios_aceptacion') or '—'}"
                    )
                    st.write(
                        f"**Restricciones:** "
                        f"{task.get('restricciones') or '—'}"
                    )
                    st.write(
                        f"**Entregables:** {task.get('entregables') or '—'}"
                    )
                    st.link_button(
                        "Abrir código revisado",
                        contribution.get("code_url")
                        or contribution.get("github_pr_url"),
                    )
                    if contribution["workflow_state"] == "awaiting_creator":
                        st.caption(f"Plazo de revisión: {task.get('deadline_at') or '—'}")
                        creator_feedback = st.text_area(
                            "Motivo si devuelves esta entrega",
                            key=f"creator_feedback_{contribution['id']}",
                        )
                        final_pr_url = st.text_input(
                            "Pull Request final al repositorio del proyecto",
                            key=f"creator_pr_{contribution['id']}",
                            help="Registra la PR creada antes de fusionarla en GitHub.",
                        )
                        approve_col, reject_col = st.columns(2)
                        with approve_col:
                            if st.button(
                                "Aprobar y registrar PR",
                                type="primary",
                                key=f"creator_approve_{contribution['id']}",
                            ):
                                try:
                                    owner, repository, pr_number = (
                                        parse_github_pull_request(final_pr_url)
                                    )
                                    target_owner, target_repository = (
                                        parse_github_repository_url(
                                            task["repositorio_url"]
                                        )
                                    )
                                    if (
                                        owner.casefold()
                                        != target_owner.casefold()
                                        or repository.casefold()
                                        != target_repository.casefold()
                                    ):
                                        raise ValueError(
                                            "La PR final debe abrirse en el repositorio destino definido por el creador."
                                        )
                                    supabase.rpc(
                                        "approve_layered_task_with_pr",
                                        {
                                            "p_contribution_id": str(
                                                contribution["id"]
                                            ),
                                            "p_pr_url": final_pr_url.strip(),
                                            "p_github_owner": owner,
                                            "p_github_repo": repository,
                                            "p_github_pr_number": pr_number,
                                        },
                                    ).execute()
                                    st.success(
                                        "PR registrada. La tarea y la reputación "
                                        "se completarán al llegar el webhook de GitHub."
                                    )
                                    st.rerun()
                                except ValueError as e:
                                    st.error(str(e))
                                except Exception as e:
                                    st.error(
                                        "No se pudo aprobar o registrar la PR: "
                                        f"{e}"
                                    )
                        with reject_col:
                            if st.button(
                                "Devolver al colaborador",
                                key=f"creator_reject_{contribution['id']}",
                            ):
                                try:
                                    supabase.rpc(
                                        "creator_decide_layered_task",
                                        {
                                            "p_contribution_id": str(
                                                contribution["id"]
                                            ),
                                            "p_decision": "changes_requested",
                                            "p_feedback": creator_feedback.strip(),
                                        },
                                    ).execute()
                                    st.success(
                                        "La entrega volvió al colaborador con tus comentarios."
                                    )
                                    st.rerun()
                                except Exception as e:
                                    st.error(
                                        f"No se pudo devolver la entrega: {e}"
                                    )
                    else:
                        st.info(
                            "Esperando que la Pull Request final se fusione. "
                            "El webhook de GitHub marcará la tarea como completada."
                        )
                        if contribution.get("github_pr_url"):
                            st.link_button(
                                "Abrir Pull Request final",
                                contribution["github_pr_url"],
                            )
                        retry_pr_url = st.text_input(
                            "Reintentar registro de la PR final",
                            key=f"retry_creator_pr_{contribution['id']}",
                        )
                        if st.button(
                            "Registrar PR final",
                            key=f"retry_register_pr_{contribution['id']}",
                        ):
                            try:
                                owner, repository, pr_number = (
                                    parse_github_pull_request(retry_pr_url)
                                )
                                target_owner, target_repository = (
                                    parse_github_repository_url(
                                        task["repositorio_url"]
                                    )
                                )
                                if (
                                    owner.casefold() != target_owner.casefold()
                                    or repository.casefold()
                                    != target_repository.casefold()
                                ):
                                    raise ValueError(
                                        "La PR debe pertenecer al repositorio destino de la tarea."
                                    )
                                supabase.rpc(
                                    "register_layered_final_pr",
                                    {
                                        "p_contribution_id": str(
                                            contribution["id"]
                                        ),
                                        "p_pr_url": retry_pr_url.strip(),
                                        "p_github_owner": owner,
                                        "p_github_repo": repository,
                                        "p_github_pr_number": pr_number,
                                    },
                                ).execute()
                                st.success("PR final registrada.")
                                st.rerun()
                            except ValueError as e:
                                st.error(str(e))
                            except Exception as e:
                                st.error(f"No se pudo registrar la PR: {e}")
            st.divider()
            st.subheader("Propuestas de tareas para módulos")
            try:
                proposals = (
                    supabase.table("module_task_proposals")
                    .select("id,module_id,proposer_id,tasks,created_at")
                    .eq("estado", "pendiente_revision")
                    .order("created_at")
                    .execute()
                )
                owner_proposals = []
                for proposal in proposals.data or []:
                    module_response = (
                        supabase.table("project_modules")
                        .select("id,project_id,titulo")
                        .eq("id", proposal["module_id"])
                        .execute()
                    )
                    if not module_response.data:
                        continue
                    module = module_response.data[0]
                    project_response = (
                        supabase.table("projects")
                        .select("owner_id,titulo")
                        .eq("id", module["project_id"])
                        .execute()
                    )
                    if (
                        project_response.data
                        and project_response.data[0]["owner_id"] == usuario_activo
                    ):
                        owner_proposals.append(
                            (proposal, module, project_response.data[0])
                        )
                if not owner_proposals:
                    st.info("No tienes propuestas de módulos pendientes.")
                for proposal, module, project in owner_proposals:
                    with st.container(border=True):
                        st.markdown(f"### {module['titulo']}")
                        st.caption(
                            f"{project['titulo']} · propuesta "
                            f"{proposal['id']} · autor {proposal['proposer_id']}"
                        )
                        for task_index, proposed_task in enumerate(
                            proposal["tasks"], start=1
                        ):
                            with st.expander(
                                f"{task_index}. {proposed_task.get('titulo') or 'Sin título'}"
                            ):
                                for field, label in (
                                    ("habilidades_requeridas", "Habilidades"),
                                    ("instrucciones", "Instrucciones"),
                                    ("objetivo", "Objetivo"),
                                    ("restricciones", "Restricciones"),
                                    ("entregables", "Entregables"),
                                    ("recursos", "Recursos"),
                                    ("criterios_aceptacion", "Criterios de aceptación"),
                                    ("modo_entrega", "Modo de entrega"),
                                    ("repositorio_url", "Repositorio"),
                                    ("duracion_estimada_horas", "Estimación (horas)"),
                                    ("dificultad", "Dificultad"),
                                ):
                                    value = proposed_task.get(field)
                                    if isinstance(value, list):
                                        value = ", ".join(map(str, value))
                                    st.write(f"**{label}:** {value or '—'}")
                        proposal_feedback = st.text_area(
                            "Cambios solicitados (si rechazas)",
                            key=f"module_proposal_feedback_{proposal['id']}",
                        )
                        accept_col, return_col = st.columns(2)
                        with accept_col:
                            if st.button(
                                "Aprobar y publicar tareas",
                                type="primary",
                                key=f"accept_module_proposal_{proposal['id']}",
                            ):
                                try:
                                    supabase.rpc(
                                        "decide_module_task_proposal",
                                        {
                                            "p_proposal_id": proposal["id"],
                                            "p_decision": "accepted",
                                            "p_feedback": "",
                                        },
                                    ).execute()
                                    st.success(
                                        "Tareas creadas y añadidas al proyecto."
                                    )
                                    st.rerun()
                                except Exception as e:
                                    st.error(
                                        f"No se pudo aprobar la propuesta: {e}"
                                    )
                        with return_col:
                            if st.button(
                                "Solicitar cambios",
                                key=f"reject_module_proposal_{proposal['id']}",
                            ):
                                try:
                                    supabase.rpc(
                                        "decide_module_task_proposal",
                                        {
                                            "p_proposal_id": proposal["id"],
                                            "p_decision": "changes_requested",
                                            "p_feedback": proposal_feedback.strip(),
                                        },
                                    ).execute()
                                    st.success(
                                        "La propuesta volvió a su autor para cambios."
                                    )
                                    st.rerun()
                                except Exception as e:
                                    st.error(
                                        f"No se pudo devolver la propuesta: {e}"
                                    )
            except Exception as e:
                st.error(f"No se pudieron cargar propuestas de módulos: {e}")
        except Exception as e:
            st.error(f"No se pudo cargar la revisión del creador: {e}")

    # --- ESTADO DE ENTREGAS ---
    elif opcion == "Mis Entregas":
        st.subheader("Estado de mis entregas")
        try:
            res_contribs = (
                supabase.table("contributions")
                .select(
                    "id,task_id,github_pr_url,code_url,estado,"
                    "workflow_state,creator_feedback"
                )
                .eq("usuario_id", usuario_activo)
                .order("id", desc=True)
                .execute()
            )
            if not res_contribs.data:
                st.info("Todavía no has enviado ninguna entrega.")
            else:
                status_labels = {
                    "peer_review": "En revisión por colaboradores",
                    "changes_requested": "Cambios solicitados; puedes volver a enviar",
                    "awaiting_creator": "Esperando decisión del creador",
                    "awaiting_merge": "Esperando merge de la Pull Request",
                    "completed": "Completada",
                }
                for contribution in res_contribs.data:
                    with st.container(border=True):
                        st.markdown(f"### Tarea #{contribution['task_id']}")
                        st.caption(
                            f"Estado: "
                            f"{status_labels.get(contribution['workflow_state'], contribution['estado'])}"
                        )
                        code_url = (
                            contribution.get("code_url")
                            or contribution.get("github_pr_url")
                        )
                        if code_url:
                            st.link_button("Abrir entrega", code_url)
                        if contribution.get("creator_feedback"):
                            st.warning(contribution["creator_feedback"])
        except Exception as e:
            st.error(f"No se pudieron cargar tus entregas: {e}")
