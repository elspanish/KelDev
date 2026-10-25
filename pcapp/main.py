import logging
import os
import sys

import streamlit as st
from dotenv import load_dotenv
from supabase import create_client
from browser_storage import (
    build_browser_storage_payload,
    persistent_browser_storage,
)
from integrations import (
    generate_project_tasks,
    parse_github_pull_request,
    parse_github_repository_url,
    validate_github_code_url,
)
from profile_export import build_profile_pdf
from skills import prepare_skill_options

TASK_DIFFICULTIES = ("Easy", "Medium", "Hard")
DIFFICULTY_TO_DATABASE = {
    "Easy": "Fácil",
    "Medium": "Medio",
    "Hard": "Difícil",
}
DIFFICULTY_FROM_DATABASE = {
    value: label for label, value in DIFFICULTY_TO_DATABASE.items()
}
DIFFICULTY_REWARDS = {"Easy": 50, "Medium": 80, "Hard": 140}
TASK_STATUS_LABELS = {
    "pendiente": "Available",
    "en_progreso": "In progress",
    "en_revision": "In review",
    "completada": "Completed",
    "completado": "Completed",
    "pendiente_revision": "Pending review",
    "cambios_solicitados": "Changes requested",
    "aceptada": "Accepted",
    "rechazada": "Rejected",
    "completed": "Completed",
    "changes_requested": "Changes requested",
    "rejected": "Rejected",
}
MODULE_WORKFLOWS_UI_ENABLED = False
logger = logging.getLogger(__name__)


def task_status_label(status):
    if not status:
        return "No status"
    return TASK_STATUS_LABELS.get(str(status), str(status))


def delivery_method_label(delivery_method):
    if delivery_method == "Pull Request de GitHub":
        return "Direct GitHub pull request"
    return delivery_method


def report_problem(context, error=None):
    if sys.exc_info()[0] is not None:
        logger.exception(
            "A platform operation could not be completed: %s", context
        )
    else:
        logger.warning("A platform operation could not be completed: %s", context)
    st.info(
        "We could not complete this action. Check your details and try again. "
        "If the problem continues, contact support."
    )
    if error is not None:
        st.error(f"Error details: {error}")


def render_module_task_proposals(user_id):
    st.divider()
    st.subheader("Module task proposals")
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
                and project_response.data[0]["owner_id"] == user_id
            ):
                owner_proposals.append(
                    (proposal, module, project_response.data[0])
                )
        if not owner_proposals:
            st.info("You have no pending module proposals.")
        for proposal, module, project in owner_proposals:
            with st.container(border=True):
                st.markdown(f"### {module['titulo']}")
                st.caption(
                    f"{project['titulo']} · proposal "
                    f"{proposal['id']} · submitted by {proposal['proposer_id']}"
                )
                for task_index, proposed_task in enumerate(
                    proposal["tasks"], start=1
                ):
                    with st.expander(
                        f"{task_index}. {proposed_task.get('titulo') or 'Untitled'}"
                    ):
                        for field, label in (
                            ("habilidades_requeridas", "Required skills"),
                            ("instrucciones", "Instructions"),
                            ("objetivo", "Goal"),
                            ("restricciones", "Constraints"),
                            ("entregables", "Deliverables"),
                            ("recursos", "Resources"),
                            ("criterios_aceptacion", "Acceptance criteria"),
                            ("modo_entrega", "Delivery method"),
                            ("repositorio_url", "Repository"),
                            ("duracion_estimada_horas", "Estimate (hours)"),
                            ("dificultad", "Difficulty"),
                        ):
                            value = proposed_task.get(field)
                            if isinstance(value, list):
                                value = ", ".join(map(str, value))
                            elif field == "dificultad":
                                value = DIFFICULTY_FROM_DATABASE.get(value, value)
                            st.write(f"**{label}:** {value or '—'}")
                proposal_feedback = st.text_area(
                    "Requested changes (if returning the proposal)",
                    key=f"module_proposal_feedback_{proposal['id']}",
                )
                accept_col, return_col = st.columns(2)
                with accept_col:
                    if st.button(
                        "Approve and publish tasks",
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
                            st.success("Tasks created and added to the project.")
                            invalidate_user_overview()
                            st.rerun()
                        except Exception:
                            report_problem("Approving a proposal")
                with return_col:
                    if st.button(
                        "Request changes",
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
                            st.success("The proposal was returned to its author.")
                            invalidate_user_overview()
                            st.rerun()
                        except Exception:
                            report_problem("Requesting proposal changes")
    except Exception:
        report_problem("Loading module proposals")


def invalidate_user_overview():
    st.session_state.pop("overview_user_id", None)


def profile_skill_names(value):
    if isinstance(value, dict):
        value = list(value)
    if not isinstance(value, list):
        return []
    return sorted(
        {str(skill).strip() for skill in value if str(skill).strip()},
        key=str.casefold,
    )


def is_anonymous_user(user=None):
    user = user or st.session_state.get("user")
    if user is None:
        return False
    anonymous_status = getattr(user, "is_anonymous", None)
    if anonymous_status is not None:
        return bool(anonymous_status)
    app_metadata = getattr(user, "app_metadata", None) or {}
    return app_metadata.get("provider") == "anonymous"


def ensure_anonymous_user():
    if st.session_state.get("user") is not None:
        return st.session_state.user
    try:
        response = supabase.auth.sign_in_anonymously()
        if response.user is None:
            raise RuntimeError("Supabase did not return an anonymous user.")
        st.session_state.user = response.user
        return response.user
    except Exception as error:
        report_problem("Starting an anonymous session", error)
        return None


def redirect_anonymous_user(action):
    if not is_anonymous_user():
        return
    st.session_state.account_prompt = (
        f"Create a permanent account or sign in before you can {action}."
    )
    st.session_state.opcion_actual = "Account"
    st.rerun()


def load_skill_catalog():
    response = (
        supabase.table("skill_catalog")
        .select("nombre")
        .order("nombre")
        .execute()
    )
    return [row["nombre"] for row in response.data or []]


def add_skills_to_catalog(skills):
    canonical_skills = []
    for skill in skills:
        name = str(skill).strip()
        if not name:
            continue
        response = supabase.rpc(
            "add_skill_to_catalog",
            {"p_nombre": name},
        ).execute()
        if not response.data:
            raise RuntimeError(
                f"Could not add skill “{name}” to the catalog."
            )
        canonical_name = str(response.data)
        if canonical_name.casefold() not in {
            existing.casefold() for existing in canonical_skills
        }:
            canonical_skills.append(canonical_name)
    return canonical_skills


def load_user_collaborations(user_id):
    contributions = []
    page_size = 500
    offset = 0
    while True:
        response = (
            supabase.table("contributions")
            .select(
                "id,task_id,estado,workflow_state,created_at,code_url,"
                "github_pr_url,reputacion_detalle,"
                "reputacion_detalle_completo"
            )
            .eq("usuario_id", user_id)
            .order("created_at", desc=True)
            .order("id", desc=True)
            .range(offset, offset + page_size - 1)
            .execute()
        )
        page = response.data or []
        contributions.extend(page)
        if len(page) < page_size:
            break
        offset += page_size

    task_ids = list({item["task_id"] for item in contributions})
    tasks = {}
    projects = {}
    if task_ids:
        for offset in range(0, len(task_ids), 200):
            task_response = (
                supabase.table("tasks")
                .select("id,titulo,dificultad,project_id")
                .in_("id", task_ids[offset : offset + 200])
                .execute()
            )
            tasks.update({
                task["id"]: task for task in task_response.data or []
            })
        project_ids = list({
            task["project_id"]
            for task in tasks.values()
            if task.get("project_id") is not None
        })
        if project_ids:
            for offset in range(0, len(project_ids), 200):
                project_response = (
                    supabase.table("projects")
                    .select("id,titulo")
                    .in_("id", project_ids[offset : offset + 200])
                    .execute()
                )
                projects.update({
                    project["id"]: project
                    for project in project_response.data or []
                })

    status_labels = {
        "completed": "Completed",
        "changes_requested": "Changes requested",
        "rejected": "Rejected",
    }
    for contribution in contributions:
        task = tasks.get(contribution["task_id"], {})
        contribution["task"] = task
        contribution["project"] = projects.get(task.get("project_id"), {})
        contribution["estado_label"] = status_labels.get(
            contribution.get("workflow_state"),
            task_status_label(contribution.get("estado")),
        )
    return contributions


def render_new_skill_action(selected_skills, catalog, key):
    known_names = {name.casefold() for name in catalog}
    new_skills = [
        skill
        for skill in selected_skills
        if str(skill).strip().casefold() not in known_names
    ]
    if new_skills and st.button(
        "Add to catalog: " + ", ".join(map(str, new_skills)),
        key=key,
    ):
        try:
            add_skills_to_catalog(new_skills)
            st.success("Skill added to the shared catalog.")
            st.rerun()
        except Exception as error:
            report_problem("Adding a skill to the catalog", error)


def load_user_overview(user_id):
    profile_response = (
        supabase.table("profiles")
        .select(
            "email,nombre,descripcion,habilidades,reputacion,"
            "reputacion_habilidades,tareas_completadas"
        )
        .eq("id", user_id)
        .execute()
    )
    if not profile_response.data:
        supabase.table("profiles").insert({
            "id": user_id,
            "email": st.session_state.user.email or "",
            "nombre": (
                getattr(st.session_state.user, "user_metadata", None) or {}
            ).get("nombre", ""),
        }).execute()
        profile_response = (
            supabase.table("profiles")
            .select(
                "email,nombre,descripcion,habilidades,reputacion,"
                "reputacion_habilidades,tareas_completadas"
            )
            .eq("id", user_id)
            .execute()
        )

    assigned_tasks = (
        supabase.table("tasks")
        .select("*")
        .eq("asignado_a", user_id)
        .execute()
        .data
        or []
    )
    assigned_modules = (
        supabase.table("project_modules")
        .select("id,project_id,titulo,estado,deadline_at")
        .eq("asignado_a", user_id)
        .execute()
        .data
        or []
    )
    projects = (
        supabase.table("projects")
        .select("id,titulo,descripcion,created_at")
        .eq("owner_id", user_id)
        .order("created_at", desc=True)
        .execute()
        .data
        or []
    )
    project_ids = [project["id"] for project in projects]
    tasks_by_project = {}
    modules_by_project = {}
    if project_ids:
        for task in (
            supabase.table("tasks")
            .select("project_id,estado")
            .in_("project_id", project_ids)
            .execute()
            .data
            or []
        ):
            tasks_by_project.setdefault(task["project_id"], []).append(
                task["estado"]
            )
        for module in (
            supabase.table("project_modules")
            .select("project_id,estado")
            .in_("project_id", project_ids)
            .execute()
            .data
            or []
        ):
            modules_by_project.setdefault(module["project_id"], []).append(
                module["estado"]
            )

    active_projects = [
        project
        for project in projects
        if any(
            state != "completada"
            for state in tasks_by_project.get(project["id"], [])
        )
        or any(
            state != "completado"
            for state in modules_by_project.get(project["id"], [])
        )
    ]
    return {
        "profile": profile_response.data[0] if profile_response.data else None,
        "assigned_tasks": assigned_tasks,
        "assigned_modules": assigned_modules,
        "projects": projects,
        "active_projects": active_projects,
    }


def render_task_details(task, user_skills=None):
    skills = task.get("habilidades_requeridas") or []
    if isinstance(skills, dict):
        skills = list(skills)
    elif not isinstance(skills, list):
        skills = [str(skills)] if skills else []

    details = (
        ("Required skills", ", ".join(str(skill) for skill in skills)),
        ("Instructions", task.get("instrucciones")),
        ("Goal", task.get("objetivo")),
        ("Constraints", task.get("restricciones")),
        ("Deliverables", task.get("entregables")),
        ("Resources", task.get("recursos")),
        ("Acceptance criteria", task.get("criterios_aceptacion")),
        (
            "Delivery method",
            delivery_method_label(task.get("modo_entrega")),
        ),
        ("Estimated effort", f"{task.get('duracion_estimada_horas') or '—'} hours"),
        (
            "Difficulty",
            DIFFICULTY_FROM_DATABASE.get(
                task.get("dificultad"), task.get("dificultad")
            ),
        ),
        (
            "Claim window",
            f"{task.get('claim_timeout_hours') or '—'} hours",
        ),
    )
    for label, value in details:
        st.write(f"**{label}:** {value or '—'}")

    if user_skills is not None:
        difficulty = DIFFICULTY_FROM_DATABASE.get(
            task.get("dificultad"), task.get("dificultad")
        )
        reward = DIFFICULTY_REWARDS.get(difficulty, 0)
        owned_skills = {str(skill).casefold() for skill in user_skills}
        matched_skills = [
            str(skill)
            for skill in skills
            if str(skill).casefold() in owned_skills
        ]
        st.write("**Reputation per skill:**")
        if matched_skills:
            st.write(
                " · ".join(f"{skill}: +{reward}" for skill in matched_skills)
            )
            st.info(
                f"Estimated reputation for this task: "
                f"{len(matched_skills) * reward} points."
            )
        else:
            st.caption("None of your skills match this task yet.")

    repository_url = task.get("repositorio_url")
    if repository_url:
        st.link_button("Open destination repository", repository_url)
    if task.get("deadline_at"):
        st.caption(f"Current deadline: {task['deadline_at']}")


# 1. Cargar variables de entorno y configuración
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
st.set_page_config(page_title="KelDev", layout="wide")
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

if not SUPABASE_URL or not SUPABASE_KEY:
    st.info(
        "Set SUPABASE_URL and SUPABASE_KEY in the app secrets to enable access."
    )
    st.stop()

if "supabase_client" not in st.session_state:
    try:
        st.session_state.supabase_client = get_supabase()
    except Exception:
        report_problem("Initializing Supabase")
        st.stop()
supabase = st.session_state.supabase_client

# 3. Estado de la sesión
if "_browser_storage_loaded" not in st.session_state:
    storage_payload = None
else:
    try:
        current_auth_session = supabase.auth.get_session()
    except Exception:
        report_problem("Reading the persistent session")
        storage_payload = None
    else:
        storage_payload = build_browser_storage_payload(
            st.session_state,
            current_auth_session,
        )
browser_storage_result = persistent_browser_storage(
    "plataforma-dev-browser-state",
    storage_payload,
)
if (
    isinstance(browser_storage_result, dict)
    and browser_storage_result.get("error")
):
    st.warning(
        "Could not read or save the session and drafts in this browser's local storage."
    )
if (
    not st.session_state.get("_browser_storage_loaded")
    and isinstance(browser_storage_result, dict)
):
    stored_payload = browser_storage_result.get("value") or {}
    if not isinstance(stored_payload, dict):
        stored_payload = {}
    stored_widgets = stored_payload.get("widgets") or {}
    if isinstance(stored_widgets, dict):
        for key, value in stored_widgets.items():
            if isinstance(key, str) and not key.startswith("_"):
                st.session_state[key] = value
    st.session_state["_browser_storage_loaded"] = True
    stored_auth = stored_payload.get("auth")
    if (
        isinstance(stored_auth, dict)
        and stored_auth.get("access_token")
        and stored_auth.get("refresh_token")
    ):
        try:
            supabase.auth.set_session(
                stored_auth["access_token"],
                stored_auth["refresh_token"],
            )
        except Exception:
            report_problem("Restoring the persistent session")

if "user" not in st.session_state:
    try:
        restored_session = supabase.auth.get_session()
        st.session_state.user = (
            restored_session.user if restored_session else None
        )
    except Exception:
        report_problem("Restoring the Supabase session")
        st.session_state.user = None

if st.session_state.user is None and st.query_params.get("code"):
    try:
        auth_response = supabase.auth.exchange_code_for_session(
            {"auth_code": st.query_params["code"]}
        )
        st.session_state.user = auth_response.user
        st.query_params.clear()
        st.rerun()
    except Exception:
        report_problem("Completing GitHub sign-in")

# ---------------------------------------------------------
# SCREEN 1: PUBLIC WORKSPACE AND ACCOUNT ACCESS
# ---------------------------------------------------------
if st.session_state.user is None:
    st.title("KelDev")
    st.caption("Collaborate, build projects, and grow your skills.")
    guest_pages = ("Explore", "Personalize", "Create Project", "Account")
    previous_guest_page = st.session_state.get("guest_page", "Explore")
    guest_page = st.radio(
        "Navigation",
        guest_pages,
        index=(
            guest_pages.index(previous_guest_page)
            if previous_guest_page in guest_pages
            else 0
        ),
        horizontal=True,
    )
    st.session_state.guest_page = guest_page

    if guest_page == "Explore":
        st.subheader("Explore the community")
        try:
            projects = (
                supabase.table("projects")
                .select("id,titulo,descripcion,created_at")
                .order("created_at", desc=True)
                .limit(50)
                .execute()
                .data
                or []
            )
            tasks = (
                supabase.table("tasks")
                .select(
                    "id,project_id,titulo,habilidades_requeridas,objetivo,"
                    "dificultad,estado"
                )
                .eq("estado", "pendiente")
                .order("created_at", desc=True)
                .limit(100)
                .execute()
                .data
                or []
            )
            catalog = load_skill_catalog()
        except Exception as error:
            report_problem("Loading public projects and tasks", error)
            projects, tasks, catalog = [], [], []

        selected_skills = st.session_state.get("guest_skill_preferences", [])
        if selected_skills:
            selected_names = {skill.casefold() for skill in selected_skills}
            tasks = [
                task for task in tasks
                if selected_names.intersection(
                    skill.casefold()
                    for skill in profile_skill_names(
                        task.get("habilidades_requeridas")
                    )
                )
            ]
        with st.expander("Personalize task matching"):
            with st.form("guest_task_preferences"):
                task_skills = st.multiselect(
                    "Skills to match",
                    options=catalog,
                    default=[
                        skill for skill in selected_skills
                        if skill in catalog
                    ],
                    help=(
                        "Saving these preferences creates a temporary "
                        "anonymous profile so they are available next time."
                    ),
                )
                save_task_preferences = st.form_submit_button(
                    "Save preferences and filter tasks"
                )
            if save_task_preferences:
                guest_user = ensure_anonymous_user()
                if guest_user is not None:
                    try:
                        update_response = (
                            supabase.table("profiles")
                            .update({"habilidades": task_skills})
                            .eq("id", guest_user.id)
                            .select("id")
                            .execute()
                        )
                        if not update_response.data:
                            raise RuntimeError(
                                "The anonymous profile could not be updated."
                            )
                        st.session_state.guest_skill_preferences = task_skills
                        st.session_state.pop("overview_user_id", None)
                        st.rerun()
                    except Exception as error:
                        report_problem("Saving task preferences", error)

        project_titles = {
            project["id"]: project["titulo"] for project in projects
        }
        st.markdown("### Available tasks")
        if not tasks:
            st.info("There are no available tasks matching these skills.")
        for task in tasks:
            with st.container(border=True):
                st.markdown(f"**{task['titulo']}**")
                st.caption(
                    f"{project_titles.get(task['project_id'], 'Project')} · "
                    f"{task.get('dificultad') or 'Difficulty not set'}"
                )
                st.write(task.get("objetivo") or "No goal provided.")
                st.write(
                    "Required skills: "
                    + ", ".join(
                        profile_skill_names(task.get("habilidades_requeridas"))
                    )
                )
                if st.button(
                    "Claim this task",
                    key=f"guest_claim_task_{task['id']}",
                    type="primary",
                ):
                    st.session_state.account_prompt = (
                        "Create a permanent account or sign in before you can "
                        "claim a task."
                    )
                    st.session_state.guest_page = "Account"
                    st.rerun()

        st.markdown("### Public projects")
        if not projects:
            st.info("No projects have been published yet.")
        for project in projects:
            with st.container(border=True):
                st.markdown(f"**{project['titulo']}**")
                st.write(project.get("descripcion") or "No description.")
                st.caption(f"Project {project['id']}")

    elif guest_page == "Personalize":
        st.subheader("Personalize your profile")
        st.info(
            "You can browse without an account. Saving your profile creates "
            "a temporary anonymous Supabase account and stores your skills "
            "and preferences with it."
        )
        try:
            catalog = load_skill_catalog()
        except Exception as error:
            report_problem("Loading the skill catalog", error)
            catalog = []
        with st.form("guest_profile_preferences"):
            guest_name = st.text_input(
                "Developer name",
                value=st.session_state.get("guest_profile_name", ""),
            )
            guest_description = st.text_area(
                "Profile description",
                value=st.session_state.get("guest_profile_description", ""),
            )
            guest_skills = st.multiselect(
                "Your skills and task preferences",
                options=catalog,
                default=[
                    skill for skill in st.session_state.get(
                        "guest_skill_preferences", []
                    )
                    if skill in catalog
                ],
            )
            save_guest_profile = st.form_submit_button(
                "Save profile and preferences",
                type="primary",
            )
        if save_guest_profile:
            guest_user = ensure_anonymous_user()
            if guest_user is not None:
                try:
                    update_response = (
                        supabase.table("profiles")
                        .update({
                            "nombre": guest_name.strip(),
                            "descripcion": guest_description.strip(),
                            "habilidades": guest_skills,
                        })
                        .eq("id", guest_user.id)
                        .select("id")
                        .execute()
                    )
                    if not update_response.data:
                        raise RuntimeError(
                            "The anonymous profile could not be updated."
                        )
                    st.session_state.guest_profile_name = guest_name.strip()
                    st.session_state.guest_profile_description = (
                        guest_description.strip()
                    )
                    st.session_state.guest_skill_preferences = guest_skills
                    st.session_state.opcion_actual = "My Profile"
                    st.rerun()
                except Exception as error:
                    report_problem("Saving profile preferences", error)

    elif guest_page == "Create Project":
        st.session_state.account_prompt = (
            "Create a permanent account or sign in before creating a project."
        )
        st.session_state.guest_page = "Account"
        st.rerun()

    else:
        st.subheader("Sign in or create an account")
        if prompt := st.session_state.pop("account_prompt", None):
            st.info(prompt)
        tab_login, tab_registro = st.tabs(["Sign in", "Create account"])
        with tab_login:
            with st.container(border=True):
                st.subheader("Welcome back")
                email = st.text_input("Email", key="login_email")
                password = st.text_input(
                    "Password", type="password", key="login_pass"
                )
                if st.button("Sign in", type="primary", width="stretch"):
                    try:
                        res = supabase.auth.sign_in_with_password(
                            {"email": email, "password": password}
                        )
                        st.session_state.user = res.user
                        st.success("You are signed in.")
                        st.rerun()
                    except Exception:
                        report_problem("Signing in")
        with tab_registro:
            with st.container(border=True):
                st.subheader("Join the community")
                reg_email = st.text_input("Email", key="reg_email")
                reg_password = st.text_input(
                    "Password", type="password", key="reg_pass"
                )
                reg_nombre = st.text_input("Developer name", key="reg_nombre")
                if st.button(
                    "Create account", type="primary", width="stretch"
                ):
                    try:
                        res = supabase.auth.sign_up(
                            {
                                "email": reg_email,
                                "password": reg_password,
                                "options": {
                                    "data": {"nombre": reg_nombre.strip()}
                                },
                            }
                        )
                        st.success(
                            "Account created. Check your inbox to confirm your "
                            "email before signing in. Your profile is created "
                            "automatically."
                        )
                    except Exception:
                        report_problem("Registering a user")

# ---------------------------------------------------------
# SCREEN 2: MAIN WORKSPACE
# ---------------------------------------------------------
else:
    usuario_activo = st.session_state.user.id
    if st.session_state.get("overview_user_id") != usuario_activo:
        try:
            st.session_state.user_overview = load_user_overview(usuario_activo)
        except Exception:
            report_problem("Loading account information")
            st.session_state.user_overview = {
                "assigned_tasks": [],
                "assigned_modules": [],
                "projects": [],
                "active_projects": [],
            }
        st.session_state.overview_user_id = usuario_activo

    perfil_actual = (
        (st.session_state.get("user_overview") or {}).get("profile") or {}
    )
    habilidades_actuales = profile_skill_names(
        perfil_actual.get("habilidades") or []
    )

    opciones = {
        "My Profile": "My Profile",
        "Account": "Account",
        "Create Project": "Create Project",
        "Find Work": "Find Work",
        "Submit Task": "Submit Task",
        "My Submissions": "My Submissions",
    }
    if MODULE_WORKFLOWS_UI_ENABLED:
        opciones["Draft Tasks"] = "Draft Tasks"
    if st.session_state.get("opcion_actual") not in opciones.values():
        st.session_state.opcion_actual = "My Profile"

    with st.sidebar:
        st.title("KelDev")
        st.caption("Build in the open, together.")
        st.divider()
        st.markdown("**Signed in as**")
        st.write(
            "Anonymous account"
            if is_anonymous_user()
            else st.session_state.user.email
        )
        st.divider()
        st.markdown("**Navigation**")
        for etiqueta, destino in opciones.items():
            if st.button(
                etiqueta,
                key=f"nav_{destino}",
                type=(
                    "primary"
                    if st.session_state.opcion_actual == destino
                    else "secondary"
                ),
                width="stretch",
            ):
                st.session_state.opcion_actual = destino
                st.rerun()
        st.divider()
        if st.button("Sign out", width="stretch"):
            try:
                supabase.auth.sign_out()
            except Exception:
                report_problem("Signing out")
            else:
                st.session_state.user = None
                st.session_state.pop("overview_user_id", None)
                st.session_state.pop("user_overview", None)
                st.rerun()

    opcion = st.session_state.opcion_actual
    st.title("Workspace")
    st.caption("Manage your projects and contributions in one place.")
    st.divider()

    if opcion == "Account":
        st.subheader("Account")
        if is_anonymous_user():
            if prompt := st.session_state.pop("account_prompt", None):
                st.warning(prompt)
            st.info(
                "Your temporary profile and preferences are stored with this "
                "anonymous account. Create a permanent account here to keep "
                "them under the same user ID."
            )
            with st.form("upgrade_anonymous_account"):
                account_email = st.text_input("Email", key="upgrade_email")
                account_password = st.text_input(
                    "Password",
                    type="password",
                    key="upgrade_password",
                )
                account_name = st.text_input(
                    "Developer name",
                    value=perfil_actual.get("nombre") or "",
                    key="upgrade_name",
                )
                complete_registration = st.form_submit_button(
                    "Create permanent account",
                    type="primary",
                )
            if complete_registration:
                if not account_name.strip():
                    st.warning("Developer name cannot be empty.")
                else:
                    try:
                        response = supabase.auth.update_user({
                            "email": account_email,
                            "password": account_password,
                            "data": {"nombre": account_name.strip()},
                        })
                        if response.user is None:
                            raise RuntimeError(
                                "Supabase did not return the updated account."
                            )
                        st.session_state.user = response.user
                        st.success(
                            "Account details updated. Confirm your email if "
                            "Supabase requires confirmation."
                        )
                        st.rerun()
                    except Exception:
                        report_problem("Completing account registration")
        else:
            st.success("You are using a permanent account.")
            st.write(st.session_state.user.email)

    # --- MY PROFILE ---
    elif opcion == "My Profile":
        try:
            perfil_res = (
                supabase.table("profiles")
                .select(
                    "email,nombre,descripcion,habilidades,reputacion,"
                    "reputacion_habilidades,tareas_completadas"
                )
                .eq("id", usuario_activo)
                .execute()
            )
        except Exception:
            report_problem("Loading the profile")
        else:
            if not perfil_res.data:
                st.info("Your profile is not available yet.")
            else:
                perfil = perfil_res.data[0]
                habilidades = profile_skill_names(
                    perfil.get("habilidades") or []
                )
                reputacion_habilidades = (
                    perfil.get("reputacion_habilidades") or {}
                )
                if not isinstance(reputacion_habilidades, dict):
                    reputacion_habilidades = {}
                try:
                    catalogo_habilidades = load_skill_catalog()
                except Exception as error:
                    report_problem("Loading the skill catalog", error)
                    catalogo_habilidades = None

                nombre = perfil.get("nombre") or "Developer"
                reputacion_total = int(perfil.get("reputacion") or 0)
                account_identity = (
                    perfil.get("email")
                    or st.session_state.user.email
                    or "Temporary anonymous profile"
                )
                with st.container(border=True):
                    st.markdown(f"### Hello, {nombre}")
                    st.caption(
                        f"Welcome to the community · "
                        f"{account_identity}"
                    )
                    metric_col, completed_col = st.columns(2)
                    with metric_col:
                        st.metric("Total reputation", reputacion_total)
                    with completed_col:
                        st.metric(
                            "Tasks completed",
                            int(perfil.get("tareas_completadas") or 0),
                        )

                st.divider()
                overview = st.session_state.get("user_overview") or {}
                st.subheader("Your assigned work")
                assigned_tasks = overview.get("assigned_tasks", [])
                if assigned_tasks:
                    for assigned_task in assigned_tasks:
                        with st.expander(
                            f"{assigned_task.get('titulo') or 'Task'} · "
                            f"{task_status_label(assigned_task.get('estado'))}"
                        ):
                            render_task_details(assigned_task, habilidades)
                else:
                    st.info("You have no assigned tasks.")

                assigned_modules = overview.get("assigned_modules", [])
                if assigned_modules:
                    st.markdown("**Assigned modules**")
                    for module in assigned_modules:
                        st.write(
                            f"**{module.get('titulo') or 'Module'}** · "
                            f"{task_status_label(module.get('estado'))} · "
                            f"deadline: {module.get('deadline_at') or '—'}"
                        )

                st.subheader("Your active projects")
                active_projects = overview.get("active_projects", [])
                if active_projects:
                    for project in active_projects:
                        st.write(
                            f"**{project['titulo']}** · "
                            f"{project.get('descripcion') or 'No description'}"
                        )
                else:
                    st.info("You have no projects with open tasks.")
                if st.button(
                    "Refresh account overview",
                    key="refresh_account_overview",
                ):
                    st.session_state.pop("overview_user_id", None)
                    st.rerun()

                st.divider()
                st.subheader("Your skills")
                habilidades_con_reputacion = sorted(
                    set(habilidades) | set(reputacion_habilidades),
                    key=str.casefold,
                )
                if habilidades_con_reputacion:
                    pares = sorted(
                        habilidades_con_reputacion,
                        key=str.casefold,
                    )
                    columnas = st.columns(min(3, len(pares)))
                    for indice, habilidad in enumerate(pares):
                        with columnas[indice % len(columnas)]:
                            with st.container(border=True):
                                st.markdown(f"**{habilidad}**")
                                st.metric(
                                    "Points",
                                    int(reputacion_habilidades.get(habilidad) or 0),
                                )
                                if habilidad not in habilidades:
                                    st.caption("Historical skill score")
                else:
                    with st.container(border=True):
                        st.info(
                            "You have not added any skills yet. Add skills to "
                            "find tasks that match your experience."
                        )

                col_editar, col_exportar = st.columns(2)
                with col_editar:
                    with st.expander("Edit profile"):
                        with st.form("form_editar_nombre"):
                            nombre_nuevo = st.text_input(
                                "Developer name",
                                value=perfil.get("nombre") or "",
                            )
                            descripcion_nueva = st.text_area(
                                "Profile description",
                                value=perfil.get("descripcion") or "",
                            )
                            guardar_nombre = st.form_submit_button(
                                "Save profile",
                                width="stretch",
                            )
                        if guardar_nombre:
                            if not nombre_nuevo.strip():
                                st.warning("Developer name cannot be empty.")
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
                                    st.success("Profile updated.")
                                    invalidate_user_overview()
                                    st.rerun()
                                except Exception:
                                    report_problem("Updating the profile")

                with col_exportar:
                    st.markdown("#### Export profile")
                    try:
                        colaboraciones = load_user_collaborations(usuario_activo)
                        perfil_pdf = {
                            **perfil,
                            "id": usuario_activo,
                            "reputacion": reputacion_total,
                        }
                        perfil_pdf_bytes = build_profile_pdf(
                            perfil_pdf,
                            colaboraciones,
                        )
                    except Exception as error:
                        report_problem("Generating the profile PDF", error)
                    else:
                        st.download_button(
                            "Download professional profile (PDF)",
                            data=perfil_pdf_bytes,
                            file_name="informe-profesional-keldev.pdf",
                            mime="application/pdf",
                            width="stretch",
                        )

                with st.expander("Edit skills"):
                    if catalogo_habilidades is None:
                        st.warning(
                            "Could not load the skill catalog."
                        )
                    else:
                        habilidades_seleccionadas = st.multiselect(
                            "Your skills",
                            options=catalogo_habilidades,
                            default=[
                                skill for skill in habilidades
                                if skill in catalogo_habilidades
                            ],
                            key="profile_skills_multiselect",
                            accept_new_options=True,
                            help=(
                                "Search the catalog or enter a new skill. New "
                                "skills are shared with the community."
                            ),
                        )
                        render_new_skill_action(
                            habilidades_seleccionadas,
                            catalogo_habilidades,
                            "add_profile_skills_to_catalog",
                        )
                        if st.button(
                            "Save profile skills",
                            key="save_profile_skills",
                            type="primary",
                        ):
                            try:
                                habilidades_canonicas = add_skills_to_catalog(
                                    habilidades_seleccionadas
                                )
                                (
                                    supabase.table("profiles")
                                    .update({
                                        "habilidades": habilidades_canonicas,
                                    })
                                    .eq("id", usuario_activo)
                                    .execute()
                                )
                                st.success("Skills updated.")
                                invalidate_user_overview()
                                st.rerun()
                            except Exception as error:
                                report_problem(
                                    "Updating profile skills", error
                                )

    # --- OPTION 1: CREATE A PROJECT AND TASKS ---
    elif opcion == "Create Project":
        try:
            catalogo_tareas = load_skill_catalog()
        except Exception as error:
            report_problem("Loading the skill catalog", error)
            catalogo_tareas = None
        st.subheader("Create a project")
        if MODULE_WORKFLOWS_UI_ENABLED:
            render_module_task_proposals(usuario_activo)
        with st.container(border=True):
            if st.session_state.pop("clear_project_form", False):
                st.session_state.project_title = ""
                st.session_state.project_description = ""
            st.write(
                "Describe the project and its tasks, or generate an editable "
                "draft with Groq (Google AI Studio is used as a fallback) "
                "before publishing."
            )
            proj_titulo = st.text_input(
                "Project name",
                key="project_title",
                placeholder=(
                    "Example: A web platform to coordinate volunteer "
                    "campaigns, assign tasks, and track progress"
                ),
            )
            proj_desc = st.text_area(
                "Project description",
                key="project_description",
                placeholder=(
                    "Explain the problem, who will use the project, its main "
                    "features, expected outcome, technologies, constraints, "
                    "and how to verify it works. Include the current project "
                    "structure if one exists. Add the base GitHub repository "
                    "URL (https://github.com/owner/repository) so AI can add "
                    "it to each task."
                ),
            )
            review_mode = "direct"
            if MODULE_WORKFLOWS_UI_ENABLED:
                creation_mode = st.radio(
                    "How would you like to define the work?",
                    [
                        "I will write the tasks",
                        "I will publish modules for task proposals",
                    ],
                    horizontal=True,
                )
            else:
                creation_mode = "I will write the tasks"
            if (
                MODULE_WORKFLOWS_UI_ENABLED
                and creation_mode == "I will publish modules for task proposals"
            ):
                st.caption(
                    "Each module is assigned to a contributor with matching "
                    "skills. The project owner reviews proposed tasks before "
                    "publishing them."
                )
                if "project_module_drafts" not in st.session_state:
                    st.session_state.project_module_drafts = [{
                        "titulo": "",
                        "descripcion": "",
                        "repositorio_url": "",
                        "habilidades_requeridas": "",
                        "claim_timeout_hours": 72,
                        "task_claim_timeout_hours": 72,
                    }]
                    st.session_state.project_module_draft_version = 0
                removed_module_review_field = False
                for module_draft in st.session_state.project_module_drafts:
                    removed_module_review_field |= (
                        module_draft.pop("peer_review_timeout_hours", None)
                        is not None
                    )
                if removed_module_review_field:
                    st.session_state.project_module_draft_version = (
                        st.session_state.get("project_module_draft_version", 0)
                        + 1
                    )
                module_drafts = st.data_editor(
                    st.session_state.project_module_drafts,
                    key=(
                        "project_modules_editor_"
                        f"{st.session_state.project_module_draft_version}"
                    ),
                    num_rows="dynamic",
                    width="stretch",
                    hide_index=True,
                    column_config={
                        "titulo": st.column_config.TextColumn(                        "Module"),
                        "descripcion": st.column_config.TextColumn(
                            "Module scope"
                        ),
                        "repositorio_url": st.column_config.TextColumn(
                            "GitHub destination repository"
                        ),
                        "habilidades_requeridas": st.column_config.TextColumn(
                            "Skills, separated by commas"
                        ),
                        "claim_timeout_hours": st.column_config.NumberColumn(
                            "Drafting window (hours)",
                            min_value=1,
                            max_value=720,
                            step=1,
                            required=True,
                        ),
                        "task_claim_timeout_hours": st.column_config.NumberColumn(
                            "Task completion window (hours)",
                            min_value=1,
                            max_value=720,
                            step=1,
                            required=True,
                        ),
                    },
                )
                if st.button("Publish project and modules", type="primary"):
                    redirect_anonymous_user("create and publish a project")
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
                            "task_claim_timeout_hours",
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
                                    f"Module {index}: {field} must be between 1 and 720 hours"
                                )
                                normalized_module[field] = 0
                            else:
                                normalized_module[field] = int(value)
                        normalized_module["creator_review_timeout_hours"] = 72
                        if not normalized_module["titulo"]:
                            errors.append(f"Module {index}: title is required")
                        if not normalized_module["descripcion"]:
                            errors.append(f"Module {index}: description is required")
                        try:
                            normalized_module["repositorio_url"] = (
                                validate_github_code_url(
                                    normalized_module["repositorio_url"]
                                )
                            )
                        except ValueError:
                            errors.append(
                                f"Module {index}: enter the project's HTTPS GitHub repository URL"
                            )
                        if not normalized_module["habilidades_requeridas"]:
                            errors.append(f"Module {index}: add at least one skill")
                        modules_to_save.append(normalized_module)
                    if not proj_titulo.strip() or not proj_desc.strip():
                        errors.append("Enter a project name and description.")
                    if not modules_to_save:
                        errors.append("Add at least one module.")
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
                            st.success("Project and modules published.")
                            invalidate_user_overview()
                            st.rerun()
                        except Exception as e:
                            report_problem("Publishing modules")
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
                    "modo_entrega": "Direct GitHub pull request with the required changes and tests.",
                    "repositorio_url": "",
                    "duracion_estimada_horas": 4,
                    "dificultad": "Medium",
                    "claim_timeout_hours": 72,
                }]
                st.session_state.project_task_draft_version = 0
            for task_draft in st.session_state.project_task_drafts:
                difficulty = task_draft.get("dificultad")
                if difficulty in DIFFICULTY_FROM_DATABASE:
                    task_draft["dificultad"] = DIFFICULTY_FROM_DATABASE[difficulty]
            removed_task_review_fields = False
            for task_draft in st.session_state.project_task_drafts:
                for field in (
                    "review_mode",
                    "peer_review_timeout_hours",
                    "creator_review_timeout_hours",
                ):
                    removed_task_review_fields |= (
                        task_draft.pop(field, None) is not None
                    )
            if removed_task_review_fields:
                st.session_state.project_task_draft_version = (
                    st.session_state.get("project_task_draft_version", 0) + 1
                )
            if "project_task_skill_drafts" not in st.session_state:
                st.session_state.project_task_skill_drafts = [
                    str(task.get("habilidades_requeridas") or "").split(",")
                    for task in st.session_state.project_task_drafts
                ]
            if "project_task_skill_draft_titles" not in st.session_state:
                st.session_state.project_task_skill_draft_titles = [
                    str(task.get("titulo") or "")
                    for task in st.session_state.project_task_drafts
                ]

            if st.button(
                "Generate task draft with AI",
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
                            "dificultad": DIFFICULTY_FROM_DATABASE.get(
                                task["dificultad"], task["dificultad"]
                            ),
                            "claim_timeout_hours": 72,
                        }
                        for task in generated
                    ]
                    st.session_state.project_task_skill_drafts = [
                        task["habilidades_requeridas"]
                        for task in generated
                    ]
                    st.session_state.project_task_skill_draft_titles = [
                        task["titulo"] for task in generated
                    ]
                    st.session_state.project_task_draft_version += 1
                    st.success("Draft generated. Review and edit it before saving.")
                    st.rerun()
                except Exception as e:
                    report_problem("Generating tasks")

            st.markdown("#### Project tasks (editable)")
            st.caption(
                "Edit cells and add or remove rows directly in the table. Task "
                "completion windows are measured in hours."
            )
            editor_key = (
                f"project_tasks_editor_"
                f"{st.session_state.project_task_draft_version}"
            )
            editor_drafts = [
                {
                    key: value
                    for key, value in task.items()
                    if key not in {
                        "habilidades_requeridas",
                        "review_mode",
                        "peer_review_timeout_hours",
                        "creator_review_timeout_hours",
                    }
                }
                for task in st.session_state.project_task_drafts
            ]
            edited_tasks = st.data_editor(
                editor_drafts,
                key=editor_key,
                num_rows="dynamic",
                width="stretch",
                hide_index=True,
                column_config={
                    "titulo": st.column_config.TextColumn("Title"),
                    "instrucciones": st.column_config.TextColumn("Instructions"),
                    "objetivo": st.column_config.TextColumn("Goal"),
                    "restricciones": st.column_config.TextColumn("Constraints"),
                    "entregables": st.column_config.TextColumn("Deliverables"),
                    "recursos": st.column_config.TextColumn("Resources"),
                    "criterios_aceptacion": st.column_config.TextColumn(
                        "Acceptance criteria"
                    ),
                    "modo_entrega": st.column_config.TextColumn("Delivery method"),
                    "repositorio_url": st.column_config.TextColumn(
                        "GitHub destination repository"
                    ),
                    "duracion_estimada_horas": st.column_config.NumberColumn(
                        "Estimated effort (hours)",
                        min_value=1,
                        max_value=8,
                        step=1,
                        required=True,
                    ),
                    "dificultad": st.column_config.SelectboxColumn(
                        "Difficulty",
                        options=list(TASK_DIFFICULTIES),
                        required=True,
                    ),
                    "claim_timeout_hours": st.column_config.NumberColumn(
                        "Claim window (hours)",
                        min_value=1,
                        max_value=720,
                        step=1,
                        required=True,
                    ),
                },
            )

            habilidades_por_tarea = []
            if catalogo_tareas is not None:
                st.markdown("#### Skills required for each task")
                title_occurrences = {}
                for index, task in enumerate(edited_tasks):
                    drafted_skills = st.session_state.get(
                        "project_task_skill_drafts", []
                    )
                    drafted_titles = st.session_state.get(
                        "project_task_skill_draft_titles", []
                    )
                    title = str(task.get("titulo") or "").strip()
                    title_identity = title.casefold() or f"tarea-{index + 1}"
                    occurrence = title_occurrences.get(title_identity, 0)
                    title_occurrences[title_identity] = occurrence + 1
                    initial_skills = (
                        drafted_skills[index]
                        if (
                            index < len(drafted_skills)
                            and index < len(drafted_titles)
                            and drafted_titles[index].strip().casefold()
                            == title.casefold()
                        )
                        else []
                    )
                    if isinstance(initial_skills, str):
                        initial_skills = initial_skills.split(",")
                    initial_skills = [
                        str(skill).strip()
                        for skill in initial_skills
                        if str(skill).strip()
                    ]
                    skill_options, selected_defaults = prepare_skill_options(
                        catalogo_tareas,
                        initial_skills,
                    )
                    with st.expander(
                        f"{index + 1}. {title or 'Task'}",
                        expanded=True,
                    ):
                        selected_skills = st.multiselect(
                            "Required skills",
                            options=skill_options,
                            default=selected_defaults,
                            key=(
                                "project_task_skills_"
                                f"{st.session_state.project_task_draft_version}_"
                                f"{title_identity}_{occurrence}"
                            ),
                            accept_new_options=True,
                            help=(
                                "Search for an existing skill or enter a new "
                                "one to add it to the shared catalog."
                            ),
                        )
                        render_new_skill_action(
                            selected_skills,
                            catalogo_tareas,
                            f"add_task_skills_to_catalog_{index}",
                        )
                        habilidades_por_tarea.append(selected_skills)
                        while len(drafted_skills) <= index:
                            drafted_skills.append([])
                        while len(drafted_titles) <= index:
                            drafted_titles.append("")
                        drafted_skills[index] = selected_skills
                        drafted_titles[index] = title

            if st.button("Save project and tasks", type="primary"):
                redirect_anonymous_user("create and publish a project")
                if not proj_titulo.strip() or not proj_desc.strip():
                    st.warning("Enter a project name and description.")
                elif not edited_tasks:
                    st.warning("Add at least one task.")
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
                                "claim_timeout_hours",
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
                                f"Task {index}: estimated effort must be a whole number"
                            )
                            normalized["duracion_estimada_horas"] = 0
                        else:
                            normalized["duracion_estimada_horas"] = int(duration)
                            if not 1 <= normalized["duracion_estimada_horas"] <= 8:
                                missing_fields.append(
                                    f"Task {index}: estimated effort must be between 1 and 8 hours"
                                )
                        normalized["habilidades_requeridas"] = [
                            str(skill).strip()
                            for skill in (
                                habilidades_por_tarea[index - 1]
                                if index - 1 < len(habilidades_por_tarea)
                                else []
                            )
                            if str(skill).strip()
                        ]
                        normalized["review_mode"] = "direct"
                        normalized["peer_review_timeout_hours"] = 48
                        normalized["creator_review_timeout_hours"] = 72
                        for field, value in normalized.items():
                            if not value:
                                missing_fields.append(f"Task {index}: {field}")
                        try:
                            normalized["repositorio_url"] = (
                                validate_github_code_url(
                                    normalized["repositorio_url"]
                                )
                            )
                        except ValueError:
                            missing_fields.append(
                                f"Task {index}: repository_url must be a valid HTTPS GitHub link"
                            )
                        if not normalized["habilidades_requeridas"]:
                            missing_fields.append(
                                f"Task {index}: add at least one required skill"
                            )
                        for timeout_field in ("claim_timeout_hours",):
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
                                    f"Task {index}: {timeout_field} must be between 1 and 720 hours"
                                )
                                normalized[timeout_field] = 0
                            else:
                                normalized[timeout_field] = int(timeout)
                        if normalized["dificultad"] not in TASK_DIFFICULTIES:
                            missing_fields.append(
                                f"Task {index}: difficulty must be Easy, Medium, or Hard"
                            )
                        else:
                            normalized["dificultad"] = DIFFICULTY_TO_DATABASE[
                                normalized["dificultad"]
                            ]
                        tasks_to_save.append(normalized)

                    if catalogo_tareas is None:
                        st.warning(
                            "Could not load the skill catalog. Please try again."
                        )
                    elif missing_fields:
                        st.warning(
                            "Complete the required fields: "
                            + ", ".join(missing_fields)
                        )
                    else:
                        try:
                            for task_to_save in tasks_to_save:
                                task_to_save["habilidades_requeridas"] = (
                                    add_skills_to_catalog(
                                        task_to_save["habilidades_requeridas"]
                                    )
                                )
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
                                f"Created project '{proj_titulo.strip()}' with "
                                f"{len(tasks_to_save)} tasks."
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
                                "modo_entrega": "Direct GitHub pull request with the required changes and tests.",
                                "duracion_estimada_horas": 4,
                                "dificultad": "Medium",
                                "repositorio_url": "",
                                "claim_timeout_hours": 72,
                            }]
                            st.session_state.project_task_skill_drafts = [[]]
                            st.session_state.project_task_skill_draft_titles = [""]
                            st.session_state.project_task_draft_version += 1
                            st.session_state.clear_project_form = True
                            invalidate_user_overview()
                            st.rerun()
                        except Exception as e:
                            report_problem("Saving the project", e)
    # --- OPTION 2: FIND WORK ---
    elif opcion == "Find Work":
        st.subheader("Available tasks")
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
                report_problem("Loading assigned tasks")
            else:
                if res_pendiente.data:
                    tarea_actual = res_pendiente.data[0]
                    st.warning(
                        f"You already have a task in progress: "
                        f"**{tarea_actual['titulo']}**"
                    )
                    if tarea_actual.get("deadline_at"):
                        st.caption(
                            f"Claim deadline: "
                            f"{tarea_actual['deadline_at']}"
                        )
                    render_task_details(tarea_actual, habilidades_actuales)
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
                                or "Changes were requested on your latest submission."
                            )
                    except Exception as e:
                        report_problem("Loading submission feedback")
                else:
                    try:
                        active_modules = None
                        if MODULE_WORKFLOWS_UI_ENABLED:
                            active_modules = (
                                supabase.table("project_modules")
                                .select("id,titulo")
                                .eq("asignado_a", usuario_activo)
                                .eq("estado", "en_progreso")
                                .execute()
                            )
                    except Exception as e:
                        report_problem("Loading assigned modules")
                    else:
                        if active_modules and active_modules.data:
                            module_title = active_modules.data[0]["titulo"]
                            st.info(
                                f"You are already assigned to module “{module_title}”. "
                                "Finish drafting its tasks before accepting another assignment."
                            )
                            if MODULE_WORKFLOWS_UI_ENABLED and st.button(
                                "Continue with my module",
                                key="continue_assigned_module",
                            ):
                                st.session_state.opcion_actual = "Draft Tasks"
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
                                report_problem("Finding compatible tasks")
                            else:
                                if not compatible:
                                    st.info(
                                        "No open tasks match your skills. Add skills "
                                        "to My Profile or check back later."
                                    )
                                for task in compatible:
                                    with st.container(border=True):
                                        st.markdown(f"### {task['titulo']}")
                                        render_task_details(task, habilidades_actuales)
                                        if st.button(
                                            "Claim this task",
                                            key=f"claim_task_{task['id']}",
                                            type="primary",
                                        ):
                                            redirect_anonymous_user(
                                                "claim a task"
                                            )
                                            try:
                                                supabase.rpc(
                                                    "claim_task",
                                                    {"p_task_id": str(task["id"])},
                                                ).execute()
                                                st.success(
                                                    f"You claimed '{task['titulo']}'."
                                                )
                                                invalidate_user_overview()
                                                st.rerun()
                                            except Exception as e:
                                                report_problem("Claiming a task")

    # --- DRAFT TASKS FOR A MODULE ---
    elif opcion == "Draft Tasks":
        st.subheader("Draft tasks for a module")
        try:
            assigned_modules = (
                supabase.table("project_modules")
                .select(
                    "id,project_id,titulo,descripcion,repositorio_url,"
                    "deadline_at,estado"
                )
                .eq("asignado_a", usuario_activo)
                .eq("estado", "en_progreso")
                .execute()
            )
        except Exception as e:
            report_problem("Loading the assigned module")
            assigned_modules = None
        if assigned_modules and assigned_modules.data:
            module = assigned_modules.data[0]
            st.markdown(f"### {module['titulo']}")
            st.write(module.get("descripcion") or "—")
            st.caption(f"Drafting deadline: {module.get('deadline_at') or '—'}")
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
                        or "The project owner requested changes."
                    )
            except Exception as e:
                report_problem("Loading project owner feedback")
            try:
                catalogo_modulo = load_skill_catalog()
            except Exception as error:
                report_problem("Loading the skill catalog", error)
                catalogo_modulo = None
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
                    "modo_entrega": "Direct GitHub pull request with the required changes and tests.",
                    "repositorio_url": module["repositorio_url"],
                    "duracion_estimada_horas": 4,
                    "dificultad": "Medium",
                }]
                st.session_state[version_key] = 0
            for task_draft in st.session_state[draft_key]:
                difficulty = task_draft.get("dificultad")
                if difficulty in DIFFICULTY_FROM_DATABASE:
                    task_draft["dificultad"] = DIFFICULTY_FROM_DATABASE[difficulty]
            removed_module_task_review_fields = False
            for task_draft in st.session_state[draft_key]:
                removed_module_task_review_fields |= (
                    task_draft.pop("review_mode", None) is not None
                )
            if removed_module_task_review_fields:
                st.session_state[version_key] = (
                    st.session_state.get(version_key, 0) + 1
                )
            skills_draft_key = f"module_task_skills_{module['id']}"
            if skills_draft_key not in st.session_state:
                st.session_state[skills_draft_key] = [
                    str(task.get("habilidades_requeridas") or "").split(",")
                    for task in st.session_state[draft_key]
                ]
            task_editor_rows = [
                {
                    field: value
                    for field, value in task.items()
                    if field not in {"habilidades_requeridas", "review_mode"}
                }
                for task in st.session_state[draft_key]
            ]
            proposed_tasks = st.data_editor(
                task_editor_rows,
                key=f"module_task_editor_{module['id']}_{st.session_state[version_key]}",
                num_rows="dynamic",
                width="stretch",
                hide_index=True,
                column_config={
                    "titulo": st.column_config.TextColumn("Title"),
                    "instrucciones": st.column_config.TextColumn("Instructions"),
                    "objetivo": st.column_config.TextColumn("Goal"),
                    "restricciones": st.column_config.TextColumn("Constraints"),
                    "entregables": st.column_config.TextColumn("Deliverables"),
                    "recursos": st.column_config.TextColumn("Resources"),
                    "criterios_aceptacion": st.column_config.TextColumn(
                        "Acceptance criteria"
                    ),
                    "modo_entrega": st.column_config.TextColumn("Delivery method"),
                    "repositorio_url": st.column_config.TextColumn(
                        "Destination repository (set by project owner)",
                        disabled=True,
                    ),
                    "duracion_estimada_horas": st.column_config.NumberColumn(
                        "Estimated effort (hours)", min_value=1, max_value=8, step=1
                    ),
                    "dificultad": st.column_config.SelectboxColumn(
                        "Difficulty", options=list(TASK_DIFFICULTIES)
                    ),
                },
            )
            skills_by_proposed_task = []
            if catalogo_modulo is not None:
                st.markdown("#### Skills required for each task")
                for index, task in enumerate(proposed_tasks):
                    initial_skills = (
                        st.session_state[skills_draft_key][index]
                        if index < len(st.session_state[skills_draft_key])
                        else []
                    )
                    if isinstance(initial_skills, str):
                        initial_skills = initial_skills.split(",")
                    initial_skills = [
                        str(skill).strip()
                        for skill in initial_skills
                        if str(skill).strip()
                    ]
                    with st.expander(
                        f"{index + 1}. {task.get('titulo') or 'Task'}",
                        expanded=True,
                    ):
                        selected_skills = st.multiselect(
                            "Required skills",
                            options=catalogo_modulo,
                            default=initial_skills,
                            key=f"{skills_draft_key}_{st.session_state[version_key]}_{index}",
                            accept_new_options=True,
                            help=(
                                "Search for a skill or enter a new one to add "
                                "it to the shared catalog."
                            ),
                        )
                        render_new_skill_action(
                            selected_skills,
                            catalogo_modulo,
                            f"add_module_task_skills_{module['id']}_{index}",
                        )
                        skills_by_proposed_task.append(selected_skills)
            if st.button(
                "Send proposal to the project owner",
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
                    )
                    normalized_task = {
                        field: str(row.get(field) or "").strip()
                        for field in task_fields
                    }
                    normalized_task["repositorio_url"] = module["repositorio_url"]
                    normalized_task["review_mode"] = "direct"
                    for field, value in normalized_task.items():
                        if not value:
                            errors.append(f"Task {index}: {field} is required")
                    normalized_task["habilidades_requeridas"] = [
                        str(skill).strip()
                        for skill in (
                            skills_by_proposed_task[index - 1]
                            if index - 1 < len(skills_by_proposed_task)
                            else []
                        )
                        if str(skill).strip()
                    ]
                    if not normalized_task["habilidades_requeridas"]:
                        errors.append(f"Task {index}: add at least one skill")
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
                            f"Task {index}: estimated effort must be between 1 and 8 hours"
                        )
                    else:
                        normalized_task["duracion_estimada_horas"] = int(duration)
                    if normalized_task["dificultad"] not in TASK_DIFFICULTIES:
                        errors.append(f"Task {index}: invalid difficulty")
                    else:
                        normalized_task["dificultad"] = DIFFICULTY_TO_DATABASE[
                            normalized_task["dificultad"]
                        ]
                    tasks_to_propose.append(normalized_task)
                if not tasks_to_propose:
                    errors.append("Add at least one task.")
                if catalogo_modulo is None:
                    st.warning(
                        "Could not load the skill catalog. Please try again."
                    )
                elif errors:
                    st.warning(" ".join(errors))
                else:
                    try:
                        for proposed_task in tasks_to_propose:
                            proposed_task["habilidades_requeridas"] = (
                                add_skills_to_catalog(
                                    proposed_task["habilidades_requeridas"]
                                )
                            )
                        supabase.rpc(
                            "submit_module_task_proposal",
                            {
                                "p_module_id": module["id"],
                                "p_tasks": tasks_to_propose,
                            },
                        ).execute()
                        st.success("Proposal sent to the project owner.")
                        st.session_state[draft_key] = [{
                            "titulo": "",
                            "habilidades_requeridas": "",
                            "instrucciones": "",
                            "objetivo": "",
                            "restricciones": "",
                            "entregables": "",
                            "recursos": "",
                            "criterios_aceptacion": "",
                            "modo_entrega": "Direct GitHub pull request with the required changes and tests.",
                            "repositorio_url": module["repositorio_url"],
                            "duracion_estimada_horas": 4,
                            "dificultad": "Medium",
                        }]
                        st.session_state[skills_draft_key] = [[]]
                        st.session_state[version_key] += 1
                        invalidate_user_overview()
                        st.rerun()
                    except Exception as e:
                        report_problem("Sending the proposal")
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
                    st.subheader("Your recent proposals")
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
                            f"**{module_titles.get(proposal['module_id'], 'Module')}** · "
                            f"{task_status_label(proposal['estado'])}"
                        )
                        if proposal.get("feedback"):
                            st.warning(proposal["feedback"])
            except Exception as e:
                report_problem("Loading proposals")
            try:
                compatible_modules = (
                    supabase.rpc("find_compatible_modules").execute().data or []
                )
            except Exception as e:
                report_problem("Finding compatible modules")
                compatible_modules = []
            if not compatible_modules:
                st.info(
                    "No available modules match your skills."
                )
            for module in compatible_modules:
                with st.container(border=True):
                    st.markdown(f"### {module['titulo']}")
                    st.caption(f"Project ID: {module['project_id']}")
                    st.write(module.get("descripcion") or "—")
                    st.write(
                        f"Required skills: "
                        f"{', '.join(module.get('habilidades_requeridas') or [])}"
                    )
                    if st.button(
                        "Draft tasks",
                        key=f"claim_module_{module['id']}",
                        type="primary",
                    ):
                        redirect_anonymous_user(
                            "claim a project module"
                        )
                        try:
                            supabase.rpc(
                                "claim_project_module",
                                {"p_module_id": module["id"]},
                            ).execute()
                            st.success("The module is assigned to you.")
                            invalidate_user_overview()
                            st.rerun()
                        except Exception as e:
                            report_problem("Claiming a module")

    # --- OPTION 3: SUBMIT A TASK ---
    elif opcion == "Submit Task":
        st.subheader("Submit a task")
        with st.container(border=True):
            try:
                res_tarea = (
                    supabase.table("tasks")
                    .select(
                        "id,titulo,instrucciones,objetivo,recursos,"
                        "restricciones,entregables,criterios_aceptacion,modo_entrega,"
                        "duracion_estimada_horas,dificultad,project_id,deadline_at,"
                        "repositorio_url,habilidades_requeridas,module_id"
                    )
                    .eq("asignado_a", usuario_activo)
                    .eq("estado", "en_progreso")
                    .execute()
                )
            except Exception as e:
                report_problem("Loading the assigned task")
            else:
                if not res_tarea.data:
                    st.info("You have no in-progress tasks to submit.")
                else:
                    tarea = res_tarea.data[0]
                    st.markdown(f"### {tarea['titulo']}")
                    render_task_details(tarea, habilidades_actuales)
                    github_url = st.text_input(
                        "GitHub pull request URL"
                    )
                    if st.button(
                        "Submit pull request",
                        type="primary",
                    ):
                        try:
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
                                    "The pull request must target the task's destination repository."
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
                                        "GitHub confirmed the merge. The task "
                                        "is complete."
                                    )
                                elif check_data.get("status") == "closed":
                                    st.warning(
                                        "The pull request was closed without a merge. "
                                        "The task is available again."
                                    )
                                else:
                                    st.success(
                                        "Pull request registered. GitHub will "
                                        "notify KelDev when it is merged."
                                    )
                            except Exception as e:
                                report_problem(
                                    "Consulta inicial del estado en GitHub"
                                )
                                st.warning(
                                    "The pull request was registered, but its "
                                    "initial status could not be checked. The "
                                    "webhook will detect future changes."
                                )
                            invalidate_user_overview()
                            st.rerun()
                        except ValueError as e:
                            st.warning(str(e))
                        except Exception as e:
                            report_problem("Submitting the task")

    # --- SUBMISSION STATUS ---
    elif opcion == "My Submissions":
        st.subheader("My submissions")
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
                st.info("You have not submitted any work yet.")
            else:
                status_labels = {
                    "changes_requested": "Changes requested — you can resubmit",
                    "completed": "Completed",
                }
                for contribution in res_contribs.data:
                    with st.container(border=True):
                        st.markdown(f"### Task #{contribution['task_id']}")
                        st.caption(
                            f"Status: "
                            f"{status_labels.get(contribution['workflow_state'], task_status_label(contribution['estado']))}"
                        )
                        code_url = (
                            contribution.get("code_url")
                            or contribution.get("github_pr_url")
                        )
                        if code_url:
                            st.link_button("Open submission", code_url)
                        if contribution.get("creator_feedback"):
                            st.warning(contribution["creator_feedback"])
        except Exception as e:
            report_problem("Loading submissions")
