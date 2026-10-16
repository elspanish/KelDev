import unittest

from skills import prepare_skill_options


class PrepareSkillOptionsTests(unittest.TestCase):
    def test_includes_generated_skills_missing_from_catalog(self):
        options, defaults = prepare_skill_options(
            ["Python"],
            ["Gestión de paquetes"],
        )

        self.assertEqual(options, ["Python", "Gestión de paquetes"])
        self.assertEqual(defaults, ["Gestión de paquetes"])

    def test_uses_catalog_spelling_for_case_insensitive_matches(self):
        options, defaults = prepare_skill_options(
            ["Python"],
            [" python ", "PYTHON", "SQL"],
        )

        self.assertEqual(options, ["Python", "SQL"])
        self.assertEqual(defaults, ["Python", "SQL"])


if __name__ == "__main__":
    unittest.main()
