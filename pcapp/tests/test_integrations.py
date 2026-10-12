import json
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from integrations import (
    _clean_task,
    build_project_task_prompt,
    generate_project_tasks,
    parse_github_pull_request,
    parse_github_repository_url,
    validate_github_code_url,
)


def _valid_generated_tasks_json():
    return json.dumps({
        "tasks": [{
            "titulo": "Crear formulario",
            "habilidades_requeridas": ["Streamlit"],
            "instrucciones": "Crear y validar el formulario.",
            "objetivo": "Formulario funcional.",
            "restricciones": "No usar datos externos.",
            "entregables": "Formulario y pruebas.",
            "recursos": "Documentación de Streamlit.",
            "criterios_aceptacion": "Campos validados.",
            "modo_entrega": "Pull Request de GitHub.",
            "duracion_estimada_horas": 3,
            "dificultad": "Baja",
        }],
    })


class GitHubPullRequestUrlTests(unittest.TestCase):
    def test_parses_pull_request_url(self):
        self.assertEqual(
            parse_github_pull_request(
                "https://github.com/example/project/pull/42"
            ),
            ("example", "project", 42),
        )

    def test_parses_url_with_suffix_and_git_repo(self):
        self.assertEqual(
            parse_github_pull_request(
                "https://github.com/example/project.git/pull/42/files"
            ),
            ("example", "project", 42),
        )

    def test_rejects_non_github_or_non_pull_request_urls(self):
        for url in (
            "https://gitlab.com/example/project/pull/42",
            "https://github.com/example/project/issues/42",
            "http://github.com/example/project/pull/42",
        ):
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    parse_github_pull_request(url)

    def test_accepts_repository_or_file_links_for_layered_review(self):
        self.assertEqual(
            validate_github_code_url(
                " https://github.com/example/project/tree/main/src/app.py "
            ),
            "https://github.com/example/project/tree/main/src/app.py",
        )

    def test_rejects_non_github_code_links(self):
        for url in (
            "http://github.com/example/project",
            "https://gitlab.com/example/project",
            "https://github.com/example",
        ):
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    validate_github_code_url(url)

    def test_parses_destination_repository_url(self):
        self.assertEqual(
            parse_github_repository_url(
                "https://github.com/Example/Project.git"
            ),
            ("Example", "Project"),
        )


class GeneratedTaskValidationTests(unittest.TestCase):
    def test_normalizes_generated_task_skills(self):
        task = _clean_task({
            "titulo": "Crear API",
            "habilidades_requeridas": [" Python ", "", "SQL"],
            "instrucciones": "Implementar endpoints",
            "objetivo": "API funcional",
            "restricciones": "Mantener compatibilidad",
            "entregables": "Código y pruebas",
            "recursos": "Documentación",
            "criterios_aceptacion": "Pruebas correctas",
            "modo_entrega": "Pull Request",
            "duracion_estimada_horas": 4,
            "dificultad": "Media",
        })
        self.assertEqual(task["habilidades_requeridas"], ["Python", "SQL"])

    def test_rejects_task_without_title(self):
        with self.assertRaises(ValueError):
            _clean_task({"habilidades_requeridas": []})

    def test_rejects_missing_task_fields_and_invalid_difficulty(self):
        task = {
            "titulo": "Crear API",
            "habilidades_requeridas": ["Python"],
            "instrucciones": "Implementar endpoints",
            "objetivo": "API funcional",
            "restricciones": "Mantener compatibilidad",
            "entregables": "Código y pruebas",
            "recursos": "Documentación",
            "criterios_aceptacion": "Pruebas correctas",
            "modo_entrega": "Pull Request",
            "duracion_estimada_horas": 9,
            "dificultad": "Extrema",
        }
        with self.assertRaisesRegex(ValueError, "Baja, Media o Alta"):
            _clean_task(task)

    def test_rejects_duration_longer_than_one_person_day(self):
        task = {
            "titulo": "Crear API",
            "habilidades_requeridas": ["Python"],
            "instrucciones": "Implementar endpoints",
            "objetivo": "API funcional",
            "restricciones": "Mantener compatibilidad",
            "entregables": "Código y pruebas",
            "recursos": "Documentación",
            "criterios_aceptacion": "Pruebas correctas",
            "modo_entrega": "Pull Request",
            "duracion_estimada_horas": 9,
            "dificultad": "Media",
        }
        with self.assertRaisesRegex(ValueError, "1 a 8 horas"):
            _clean_task(task)

    def test_prompt_bounds_single_person_estimates_and_uses_project_inputs(self):
        prompt = build_project_task_prompt(
            "Gestor de tareas",
            "Una aplicación web para organizar tareas personales.",
        )
        self.assertIn("Título del proyecto: Gestor de tareas", prompt)
        self.assertIn(
            "Descripción del proyecto: Una aplicación web para organizar "
            "tareas personales.",
            prompt,
        )
        self.assertIn("máximo de 8 horas", prompt)
        self.assertIn('"duracion_estimada_horas"', prompt)
        self.assertIn('"dificultad"', prompt)
        self.assertIn('"criterios_aceptacion"', prompt)
        self.assertIn('"restricciones"', prompt)
        self.assertIn('"entregables"', prompt)
        self.assertIn('"repositorio_url"', prompt)
        self.assertIn("no la pongas en modo_entrega", prompt)

    def test_generates_with_groq_before_google_ai_studio(self):
        with (
            patch.dict(
                "os.environ",
                {"GROQ_API_KEY": "groq-test-key"},
                clear=True,
            ),
            patch("groq.Groq") as groq_client,
        ):
            client = groq_client.return_value
            client.chat.completions.create.return_value.choices = [
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=_valid_generated_tasks_json()
                    )
                )
            ]

            tasks = generate_project_tasks("App", "Una aplicación Streamlit.")

        self.assertEqual(tasks[0]["titulo"], "Crear formulario")
        groq_client.assert_called_once_with(
            api_key="groq-test-key",
            timeout=30.0,
            max_retries=1,
        )
        call = client.chat.completions.create.call_args.kwargs
        self.assertEqual(call["model"], "llama-3.1-8b-instant")
        self.assertEqual(call["response_format"], {"type": "json_object"})
        self.assertIn("Título del proyecto: App", call["messages"][0]["content"])

    def test_falls_back_to_google_when_groq_request_fails(self):
        with (
            patch.dict(
                "os.environ",
                {
                    "GROQ_API_KEY": "groq-test-key",
                    "GEMINI_API_KEY": "gemini-test-key",
                },
                clear=True,
            ),
            patch("groq.Groq", side_effect=RuntimeError("Groq unavailable")),
            patch("google.genai.Client") as gemini_client,
        ):
            gemini_client.return_value.models.generate_content.return_value.text = (
                _valid_generated_tasks_json()
            )

            tasks = generate_project_tasks("App", "Una aplicación Streamlit.")

        self.assertEqual(tasks[0]["titulo"], "Crear formulario")
        gemini_client.assert_called_once_with(api_key="gemini-test-key")

    def test_falls_back_to_google_when_groq_returns_invalid_json(self):
        with (
            patch.dict(
                "os.environ",
                {
                    "GROQ_API_KEY": "groq-test-key",
                    "GEMINI_API_KEY": "gemini-test-key",
                },
                clear=True,
            ),
            patch("groq.Groq") as groq_client,
            patch("google.genai.Client") as gemini_client,
        ):
            groq_client.return_value.chat.completions.create.return_value.choices = [
                SimpleNamespace(
                    message=SimpleNamespace(content="not valid JSON")
                )
            ]
            gemini_client.return_value.models.generate_content.return_value.text = (
                _valid_generated_tasks_json()
            )

            tasks = generate_project_tasks("App", "Una aplicación Streamlit.")

        self.assertEqual(tasks[0]["titulo"], "Crear formulario")
        gemini_client.assert_called_once_with(api_key="gemini-test-key")

    def test_reports_errors_when_both_providers_fail(self):
        with (
            patch.dict(
                "os.environ",
                {
                    "GROQ_API_KEY": "groq-test-key",
                    "GEMINI_API_KEY": "gemini-test-key",
                },
                clear=True,
            ),
            patch("groq.Groq", side_effect=RuntimeError("Groq unavailable")),
            patch(
                "google.genai.Client",
                side_effect=RuntimeError("Google unavailable"),
            ),
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "Groq: Groq unavailable; Google AI Studio: Google unavailable",
            ):
                generate_project_tasks("App", "Una aplicación Streamlit.")

    @patch("google.genai.Client")
    @patch.dict(
        "os.environ",
        {"GROQ_API_KEY": "", "GEMINI_API_KEY": "test-key"},
    )
    def test_generates_and_validates_structured_gemini_tasks(self, client_class):
        client = client_class.return_value
        client.models.generate_content.return_value.text = (
            _valid_generated_tasks_json()
        )

        tasks = generate_project_tasks("App", "Una aplicación Streamlit.")

        self.assertEqual(tasks[0]["duracion_estimada_horas"], 3)
        self.assertEqual(tasks[0]["dificultad"], "Baja")
        call = client.models.generate_content.call_args.kwargs
        self.assertIn("Título del proyecto: App", call["contents"])
        self.assertEqual(
            call["config"].response_mime_type,
            "application/json",
        )

    @patch("google.genai.Client")
    @patch.dict(
        "os.environ",
        {"GROQ_API_KEY": "", "GEMINI_API_KEY": "test-key"},
    )
    def test_routes_repository_in_project_description_to_destination_field(
        self,
        client_class,
    ):
        client = client_class.return_value
        client.models.generate_content.return_value.text = json.dumps({
            "tasks": [{
                "titulo": "Crear formulario",
                "habilidades_requeridas": ["Streamlit"],
                "instrucciones": "Crear y validar el formulario.",
                "objetivo": "Formulario funcional.",
                "restricciones": "No usar datos externos.",
                "entregables": "Formulario y pruebas.",
                "recursos": "Documentación de Streamlit.",
                "criterios_aceptacion": "Campos validados.",
                "modo_entrega": (
                    "Pull Request en "
                    "https://github.com/example/project/pulls."
                ),
                "duracion_estimada_horas": 3,
                "dificultad": "Baja",
            }],
        })

        tasks = generate_project_tasks(
            "App",
            "Repositorio del proyecto: "
            "https://github.com/example/project/pulls",
        )

        self.assertEqual(
            tasks[0]["repositorio_url"],
            "https://github.com/example/project",
        )
        self.assertNotIn("github.com", tasks[0]["modo_entrega"])


if __name__ == "__main__":
    unittest.main()
