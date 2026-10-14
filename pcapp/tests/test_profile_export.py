import unittest
from datetime import datetime, timezone

from profile_export import build_profile_pdf


class ProfilePdfExportTests(unittest.TestCase):
    def test_builds_report_with_profile_skills_and_collaboration_history(self):
        pdf = build_profile_pdf(
            {
                "id": "user-123",
                "nombre": "Ana Desarrolladora",
                "email": "ana@example.com",
                "reputacion": 130,
                "tareas_completadas": 1,
                "habilidades": ["Python", "SQL"],
                "reputacion_habilidades": {"Python": 50, "SQL": 80},
            },
            [{
                "task": {"titulo": "Crear API", "dificultad": "Fácil"},
                "project": {"titulo": "Proyecto"},
                "estado": "aceptada",
                "estado_label": "Completada",
                "workflow_state": "completed",
                "created_at": "2026-10-14T10:00:00+00:00",
                "reputacion_detalle": {"Python": 50},
            }],
            datetime(2026, 10, 14, tzinfo=timezone.utc),
        )

        self.assertTrue(pdf.startswith(b"%PDF-"))
        self.assertTrue(pdf.rstrip().endswith(b"%%EOF"))
        self.assertIn(b"Plataforma Dev", pdf)

    def test_builds_report_when_profile_has_no_skills_or_contributions(self):
        pdf = build_profile_pdf(
            {
                "nombre": "Sin historial",
                "reputacion": 0,
                "tareas_completadas": 0,
                "habilidades": [],
                "reputacion_habilidades": {},
            },
            [],
            datetime(2026, 10, 14, tzinfo=timezone.utc),
        )

        self.assertTrue(pdf.startswith(b"%PDF-"))
        self.assertTrue(pdf.rstrip().endswith(b"%%EOF"))


if __name__ == "__main__":
    unittest.main()
