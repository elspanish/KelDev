import json
import logging
import os
import re
import time
from urllib.parse import urlparse


logger = logging.getLogger(__name__)

GEMINI_MAX_ATTEMPTS = 3
GEMINI_RETRYABLE_ERROR_CODES = {408, 429, 500, 502, 503, 504}
RETIRED_GEMINI_FALLBACK_MODEL = "gemini-2.5-flash-lite"
DEFAULT_GEMINI_FALLBACK_MODEL = "gemini-3.5-flash-lite"

TASK_FIELDS = (
    "titulo",
    "habilidades_requeridas",
    "instrucciones",
    "objetivo",
    "restricciones",
    "entregables",
    "recursos",
    "criterios_aceptacion",
    "modo_entrega",
    "duracion_estimada_horas",
    "dificultad",
)
TASK_DIFFICULTIES = {"fácil", "medio", "difícil"}


def parse_github_pull_request(url):
    parsed = urlparse(url.strip())
    parts = [part for part in parsed.path.split("/") if part]
    if (
        parsed.scheme != "https"
        or parsed.hostname != "github.com"
        or len(parts) < 4
        or parts[2] != "pull"
        or not re.fullmatch(r"\d+", parts[3])
    ):
        raise ValueError(
            "Introduce un enlace de Pull Request de GitHub "
            "(https://github.com/propietario/repositorio/pull/123)."
        )

    owner, repository = parts[0], parts[1]
    if owner in {".", ".."} or repository in {".", ".."}:
        raise ValueError("El enlace de GitHub no es válido.")

    return owner, repository.removesuffix(".git"), int(parts[3])


def validate_github_code_url(url):
    parsed = urlparse(url.strip())
    parts = [part for part in parsed.path.split("/") if part]
    if (
        parsed.scheme != "https"
        or parsed.hostname != "github.com"
        or len(parts) < 2
        or parts[0] in {".", ".."}
        or parts[1] in {".", ".."}
    ):
        raise ValueError(
            "Introduce un enlace HTTPS válido a un repositorio o archivo de GitHub."
        )
    return url.strip()


def parse_github_repository_url(url):
    validate_github_code_url(url)
    parts = [part for part in urlparse(url.strip()).path.split("/") if part]
    return parts[0], parts[1].removesuffix(".git")


def _clean_task(task):
    if not isinstance(task, dict):
        raise ValueError("Cada tarea generada debe ser un objeto.")
    cleaned = {}
    for field in TASK_FIELDS:
        value = task.get(field, "")
        if field == "habilidades_requeridas":
            if isinstance(value, str):
                value = value.split(",")
            if not isinstance(value, list):
                raise ValueError(
                    "Las habilidades requeridas deben ser una lista."
                )
            cleaned[field] = [
                str(skill).strip()
                for skill in value
                if str(skill).strip()
            ]
        elif field == "duracion_estimada_horas":
            if isinstance(value, bool):
                raise ValueError(
                    "La duración estimada debe ser un número entero de horas."
                )
            if isinstance(value, int):
                cleaned[field] = value
            elif isinstance(value, float) and value.is_integer():
                cleaned[field] = int(value)
            elif isinstance(value, str) and value.isdigit():
                cleaned[field] = int(value)
            else:
                raise ValueError(
                    "La duración estimada debe ser un número entero de horas."
                )
        else:
            cleaned[field] = str(value or "").strip()
    repository_url = str(task.get("repositorio_url") or "").strip()
    cleaned["repositorio_url"] = (
        validate_github_code_url(repository_url) if repository_url else ""
    )
    missing = [
        field for field in TASK_FIELDS
        if not cleaned[field]
    ]
    if missing:
        raise ValueError(
            "El modelo dejó campos obligatorios vacíos: "
            + ", ".join(missing)
        )
    if not cleaned["habilidades_requeridas"]:
        raise ValueError(
            "El modelo debe asignar al menos una habilidad requerida por tarea."
        )
    if cleaned["dificultad"].casefold() not in TASK_DIFFICULTIES:
        raise ValueError(
            "La dificultad debe ser Fácil, Medio o Difícil."
        )
    cleaned["dificultad"] = cleaned["dificultad"].title()
    if not 1 <= cleaned["duracion_estimada_horas"] <= 8:
        raise ValueError(
            "La duración estimada debe ser de 1 a 8 horas para una persona."
        )
    return cleaned


def build_project_task_prompt(title, description):
    return f"""
Analiza el título y la descripción del proyecto y divídelo en tareas de
desarrollo de software independientes, concretas y verificables. Cada tarea
debe poder completarla una sola persona con las habilidades requeridas.

Mantén cada tarea en un tamaño asequible: estima esfuerzo individual en horas,
limita cada tarea a un máximo de 8 horas de trabajo y divídela en tareas más
pequeñas si supera ese límite. No confundas horas de trabajo con días
calendario. Asigna una dificultad realista: Fácil, Medio o Difícil; evita que una
tarea sea amplia o dependa de varias personas. Ordena las tareas en el orden
lógico de implementación y evita duplicidades.

Devuelve exclusivamente JSON válido con esta estructura:
{{
  "tasks": [
    {{
      "titulo": "Título breve y concreto",
      "habilidades_requeridas": ["Python"],
      "instrucciones": "Pasos concretos y acotados para implementar la tarea",
      "objetivo": "Resultado verificable esperado",
      "restricciones": "Límites técnicos o condiciones que deben respetarse",
      "entregables": "Archivos, cambios o evidencias que se deben entregar",
      "recursos": "Documentación, herramientas o dependencias útiles",
      "criterios_aceptacion": "Condiciones observables para aceptar el trabajo",
      "modo_entrega": "Pull Request a GitHub; indicar qué debe incluir, sin URL",
      "repositorio_url": "URL del repositorio destino de GitHub",
      "duracion_estimada_horas": 4,
      "dificultad": "Medio"
    }}
  ]
}}

Genera al menos una tarea y completa todos los campos de cada una. Las
habilidades deben ser una lista no vacía. La duración estimada debe ser un
número entero de horas de trabajo para una persona, entre 1 y 8. Usa español.
No inventes nombres de repositorios, URLs ni información que no aparezca en el
proyecto. Si la descripción incluye una URL de GitHub, copia la URL base del
repositorio (https://github.com/propietario/repositorio) en repositorio_url
para todas las tareas y no la pongas en modo_entrega. Usa modo_entrega solo
para explicar qué cambios, pruebas y evidencias debe incluir la Pull Request.
Si la descripción no incluye un repositorio, deja repositorio_url vacío.

En KelDev, cada entrega se envía como una Pull Request directa del colaborador
al repositorio destino de la tarea. No diseñes pasos de revisión entre pares,
aprobación final del creador ni una segunda Pull Request creada por el creador.
No incluyas en el JSON campos de flujo de revisión ni plazos de revisión; usa
únicamente la estructura indicada arriba.

Título del proyecto: {title}
Descripción del proyecto: {description}
""".strip()


def generate_project_tasks(title, description):
    prompt = build_project_task_prompt(title, description)
    groq_error = None
    try:
        response_text = _generate_with_groq(prompt)
        return _clean_generated_tasks(response_text, description)
    except Exception as error:
        groq_error = error
        logger.warning(
            "Groq task generation failed; falling back to Google AI Studio: %s",
            groq_error,
        )

    try:
        response_text = _generate_with_gemini(prompt)
        return _clean_generated_tasks(response_text, description)
    except Exception as gemini_error:
        raise RuntimeError(
            "No se pudieron generar las tareas con ninguno de los proveedores. "
            f"Groq: {groq_error}; Google AI Studio: {gemini_error}"
        ) from gemini_error


def _get_config_value(name, default=None):
    value = os.getenv(name)
    if value:
        return value

    import streamlit as st
    from streamlit.errors import StreamlitSecretNotFoundError

    try:
        value = st.secrets.get(name)
    except StreamlitSecretNotFoundError:
        return default
    return str(value) if value else default


def _generate_with_groq(prompt):
    api_key = _get_config_value("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Falta configurar GROQ_API_KEY para usar Groq."
        )

    from groq import Groq

    client = Groq(api_key=api_key, timeout=30.0, max_retries=1)
    response = client.chat.completions.create(
        model=_get_config_value("GROQ_MODEL", "llama-3.1-8b-instant"),
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )
    try:
        response_text = response.choices[0].message.content
    except (AttributeError, IndexError, TypeError) as error:
        raise RuntimeError(
            "Groq devolvió una respuesta sin contenido."
        ) from error
    if not isinstance(response_text, str) or not response_text.strip():
        raise RuntimeError("Groq devolvió una respuesta vacía.")
    return response_text


def _generate_with_gemini(prompt):
    api_key = _get_config_value("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Falta configurar GEMINI_API_KEY para Google AI Studio."
        )

    from google import genai
    from google.genai.errors import APIError
    from google.genai import types

    client = genai.Client(api_key=api_key)
    model = _get_config_value("GEMINI_MODEL", "gemini-2.5-flash")
    fallback_model = _get_config_value(
        "GEMINI_FALLBACK_MODEL",
        DEFAULT_GEMINI_FALLBACK_MODEL,
    )
    if fallback_model == RETIRED_GEMINI_FALLBACK_MODEL:
        logger.warning(
            "%s is retired; using %s instead.",
            RETIRED_GEMINI_FALLBACK_MODEL,
            DEFAULT_GEMINI_FALLBACK_MODEL,
        )
        fallback_model = DEFAULT_GEMINI_FALLBACK_MODEL
    models = list(dict.fromkeys((model, fallback_model)))
    for model_index, model_name in enumerate(models):
        for attempt in range(GEMINI_MAX_ATTEMPTS):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json"
                    ),
                )
            except APIError as error:
                if error.code == 404 and model_index < len(models) - 1:
                    logger.warning(
                        "Google AI Studio could not find model %s; "
                        "switching to fallback model %s.",
                        model_name,
                        models[model_index + 1],
                    )
                    break
                if error.code not in GEMINI_RETRYABLE_ERROR_CODES:
                    raise
                if attempt == GEMINI_MAX_ATTEMPTS - 1:
                    if model_index == len(models) - 1:
                        raise RuntimeError(
                            "Google AI Studio no respondió tras agotar los "
                            f"intentos de los modelos {', '.join(models)}: "
                            f"{error}"
                        ) from error
                    logger.warning(
                        "Google AI Studio kept returning transient HTTP %s "
                        "for %s; switching to fallback model %s.",
                        error.code,
                        model_name,
                        models[model_index + 1],
                    )
                    break
                delay = 2**attempt
                logger.warning(
                    "Google AI Studio returned transient HTTP %s for %s; "
                    "retrying in %s seconds (attempt %s/%s).",
                    error.code,
                    model_name,
                    delay,
                    attempt + 2,
                    GEMINI_MAX_ATTEMPTS,
                )
                time.sleep(delay)
                continue

            if not response.text:
                raise RuntimeError(
                    f"Google AI Studio devolvió una respuesta vacía "
                    f"con el modelo {model_name}."
                )
            return response.text


def _clean_generated_tasks(response_text, description):
    try:
        result = json.loads(response_text)
    except json.JSONDecodeError as error:
        raise ValueError("El modelo no devolvió un JSON válido.") from error

    tasks = result.get("tasks") if isinstance(result, dict) else None
    if not isinstance(tasks, list) or not tasks:
        raise ValueError("El modelo no devolvió una lista de tareas.")
    cleaned_tasks = [_clean_task(task) for task in tasks]
    repository_url = _github_repository_from_description(description)
    if repository_url:
        for task in cleaned_tasks:
            task["repositorio_url"] = repository_url
            task["modo_entrega"] = re.sub(
                r"\s+([.,;:])",
                r"\1",
                _remove_github_urls(task["modo_entrega"]),
            ).strip(" \t\r\n,;:.!:-")
            if not task["modo_entrega"]:
                task["modo_entrega"] = (
                    "Pull Request de GitHub con los cambios y pruebas "
                    "correspondientes."
                )
    return cleaned_tasks


def _github_repository_from_description(description):
    urls = re.findall(
        r"https://github\.com/[^\s<>\"']+",
        description,
        flags=re.IGNORECASE,
    )
    for url in urls:
        candidate = url.rstrip(".,;:!?)")
        try:
            owner, repository = parse_github_repository_url(candidate)
        except ValueError:
            continue
        return f"https://github.com/{owner}/{repository}"
    return ""


def _remove_github_urls(value):
    return re.sub(
        r"https://github\.com/[^\s<>\"']+",
        "",
        value,
        flags=re.IGNORECASE,
    )
