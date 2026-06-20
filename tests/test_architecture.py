import unittest
from pathlib import Path

import main


ROOT = Path(__file__).resolve().parents[1]


class ArchitectureTests(unittest.TestCase):
    def test_application_startup_does_not_mutate_schema(self):
        source = (ROOT / "main.py").read_text(encoding="utf-8-sig")
        self.assertNotIn("Base.metadata.create_all", source)
        self.assertNotIn("ALTER TABLE", source.upper())

    def test_main_is_reduced_to_composition_and_domain_services(self):
        line_count = len(
            (ROOT / "main.py").read_text(encoding="utf-8-sig").splitlines()
        )
        self.assertLess(line_count, 4000)

    def test_web_process_does_not_start_academic_scheduler(self):
        source = (ROOT / "main.py").read_text(encoding="utf-8-sig")
        self.assertNotIn("start_academic_automations", source)
        self.assertNotIn("add_event_handler", source)

        procfile = (ROOT / "Procfile").read_text(encoding="utf-8-sig")
        self.assertIn("worker: python worker.py", procfile)

    def test_modular_routers_keep_critical_endpoints(self):
        routes = {
            (method, route.path)
            for route in main.app.routes
            for method in getattr(route, "methods", set())
        }
        expected = {
            ("POST", "/login"),
            ("POST", "/chat"),
            ("GET", "/ops/health"),
            ("GET", "/dashboard"),
            ("POST", "/meta-webhook"),
        }
        self.assertTrue(expected.issubset(routes))


if __name__ == "__main__":
    unittest.main()
