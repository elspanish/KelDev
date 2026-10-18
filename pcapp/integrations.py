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
TASK_DIFFICULTIES = {
    "easy": "Fácil",
    "medium": "Medio",
    "hard": "Difícil",
    "fácil": "Fácil",
    "medio": "Medio",
    "difícil": "Difícil",
}


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
            "Enter a GitHub pull request URL "
            "(https://github.com/owner/repository/pull/123)."
        )

    owner, repository = parts[0], parts[1]
    if owner in {".", ".."} or repository in {".", ".."}:
        raise ValueError("The GitHub URL is invalid.")

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
            "Enter a valid HTTPS link to a GitHub repository or file."
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
                    "Required skills must be provided as a list."
                )
            cleaned[field] = [
                str(skill).strip()
                for skill in value
                if str(skill).strip()
            ]
        elif field == "duracion_estimada_horas":
            if isinstance(value, bool):
                raise ValueError(
                    "The estimated duration must be a whole number of hours."
                )
            if isinstance(value, int):
                cleaned[field] = value
            elif isinstance(value, float) and value.is_integer():
                cleaned[field] = int(value)
            elif isinstance(value, str) and value.isdigit():
                cleaned[field] = int(value)
            else:
                raise ValueError(
                    "The estimated duration must be a whole number of hours."
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
            "The model left required fields empty: "
            + ", ".join(missing)
        )
    if not cleaned["habilidades_requeridas"]:
        raise ValueError(
            "The model must assign at least one required skill to every task."
        )
    difficulty = TASK_DIFFICULTIES.get(cleaned["dificultad"].casefold())
    if difficulty is None:
        raise ValueError("Difficulty must be Easy, Medium, or Hard.")
    cleaned["dificultad"] = difficulty
    if not 1 <= cleaned["duracion_estimada_horas"] <= 8:
        raise ValueError(
            "The estimated duration must be 1 to 8 hours for one contributor."
        )
    return cleaned


def build_project_task_prompt(title, description):
    return f"""
Analyze the project title and description and break the work into independent,
concrete, verifiable software development tasks. Each task must be achievable
by one contributor with the listed required skills.

Keep every task small and actionable. Estimate individual effort in working
hours, limit each task to at most 8 hours, and split larger tasks into smaller
ones. Do not confuse working hours with calendar days. Assign a realistic
difficulty of Easy, Medium, or Hard. Order tasks by implementation dependency
and avoid duplicates. Write every title and user-facing description in natural,
professional technical English.

Return only valid JSON with this structure:
{{
  "tasks": [
    {{
      "titulo": "A short, action-oriented title",
      "habilidades_requeridas": ["Python"],
      "instrucciones": "Numbered, specific implementation steps and file paths",
      "objetivo": "The verifiable outcome",
      "restricciones": "Technical constraints that must be respected",
      "entregables": "Files, changes, or evidence to submit",
      "recursos": "Relevant documentation, tools, or dependencies",
      "criterios_aceptacion": "Observable acceptance criteria",
      "modo_entrega": "Direct GitHub pull request and required evidence; no URL",
      "repositorio_url": "Destination GitHub repository URL",
      "duracion_estimada_horas": 4,
      "dificultad": "Medium"
    }}
  ]
}}

Generate at least one task and populate every field. Required skills must be a
non-empty array of relevant names from the existing shared skill catalog. The
estimated duration must be a whole number of working hours from 1 to 8. Use
English for all generated text. Do not invent repository names, URLs, or project
facts. Use English for all generated text. If the description includes a GitHub
URL, copy its base repository URL (https://github.com/owner/repository) into
repositorio_url for every task and do not put that URL in modo_entrega. Use
modo_entrega only to describe the
changes, tests, and evidence to include in the pull request. If no repository
URL is provided, leave repositorio_url empty.

KelDev uses a direct pull request from the contributor to the task destination
repository. Do not design peer-review steps, creator approval, or a second pull
request opened by the creator. Do not add review workflow or review deadline
fields to the JSON; use only the structure shown above.

Project title: {title}
Project description: {description}
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
            "Task generation failed with both providers. "
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
        raise RuntimeError("GROQ_API_KEY is required to use Groq.")

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
            "Groq returned a response without content."
        ) from error
    if not isinstance(response_text, str) or not response_text.strip():
        raise RuntimeError("Groq returned an empty response.")
    return response_text


def _generate_with_gemini(prompt):
    api_key = _get_config_value("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is required to use Google AI Studio."
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
                            "Google AI Studio did not respond after all "
                            f"attempts for models {', '.join(models)}: "
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
                    f"Google AI Studio returned an empty response "
                    f"for model {model_name}."
                )
            return response.text


def _clean_generated_tasks(response_text, description):
    try:
        result = json.loads(response_text)
    except json.JSONDecodeError as error:
        raise ValueError("The model did not return valid JSON.") from error

    tasks = result.get("tasks") if isinstance(result, dict) else None
    if not isinstance(tasks, list) or not tasks:
        raise ValueError("The model did not return a task list.")
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
