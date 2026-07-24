import importlib.util
from pathlib import Path
import tempfile
import unittest

from pipeline.jobs_doc import build_jobs_document, write_jobs_doc
from pipeline.sections import generate_job_openings, generate_material_requirements
from store.db import (
    connect,
    init_db,
    latest_material_requirements,
    upsert_material_requirements,
)


SITE_BUILD_PATH = Path(__file__).resolve().parents[1] / "site" / "build.py"
SPEC = importlib.util.spec_from_file_location("softrobotics_site_build", SITE_BUILD_PATH)
site_build = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(site_build)


SITE_CONFIG = {"site": {"name": "SoftRobotics Intelligence", "tagline": "t", "description": "d", "url": "https://x/"}}


class FakeSearchClient:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def search_json(self, **kwargs):
        self.calls.append(kwargs)
        return self.payload, {"input_tokens": 7}


class SectionsTests(unittest.TestCase):
    def _config(self, enabled=True):
        return {
            "site": {"tagline": "materials scientists"},
            "sections": {
                "material_requirements": {
                    "enabled": enabled,
                    "model": "test-model",
                    "prompt": "prompts/material_requirements.md",
                    "max_searches": 3,
                },
                "job_openings": {
                    "enabled": enabled,
                    "model": "test-model",
                    "prompt": "prompts/jobs.md",
                    "max_searches": 3,
                },
            },
        }

    def test_disabled_section_returns_none(self):
        self.assertIsNone(generate_material_requirements(self._config(enabled=False)))

    def test_no_client_returns_none(self):
        # model_client=None and no API key => build returns None => section skipped
        self.assertIsNone(generate_job_openings(self._config(), model_client=None))
        # (build_anthropic_client returns None without a key; this stays None offline)

    def test_material_requirements_uses_injected_client_and_tracks_usage(self):
        payload = {"materials": [{"application": "Hand actuator", "material_class": "DEA",
                                  "key_properties": "high strain", "open_challenge": "durability",
                                  "source_url": "https://x/1"}]}
        client = FakeSearchClient(payload)
        token_usage = {}
        result = generate_material_requirements(self._config(), model_client=client, token_usage=token_usage)
        self.assertEqual(result, payload)
        self.assertEqual(client.calls[0]["model"], "test-model")
        self.assertEqual(client.calls[0]["max_searches"], 3)
        self.assertEqual(token_usage["anthropic_material_requirements"]["input_tokens"], 7)

    def test_section_swallows_client_errors(self):
        class Boom:
            def search_json(self, **kwargs):
                raise RuntimeError("search down")

        self.assertIsNone(generate_job_openings(self._config(), model_client=Boom()))


class SectionStoreTests(unittest.TestCase):
    def test_upsert_and_latest_material_requirements(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "tracker.db"
            with connect(db_path) as db:
                init_db(db)
                upsert_material_requirements(db, week_start="2026-06-22", week_end="2026-06-28",
                                             payload={"materials": [{"application": "Skin"}]})
                mats = latest_material_requirements(db)

        self.assertEqual(mats["week_start"], "2026-06-22")
        self.assertEqual(mats["payload"]["materials"][0]["application"], "Skin")


class JobsDocTests(unittest.TestCase):
    PAYLOAD = {"jobs": [{"title": "Materials Engineer, Soft Actuators", "company": "Figure AI",
                         "location": "Sunnyvale, CA", "description": "Polymer actuators",
                         "url": "https://x/job"}]}

    def test_build_jobs_document_contains_role(self):
        doc = build_jobs_document(self.PAYLOAD, week_start="2026-06-22", week_end="2026-06-28")
        if doc is None:
            self.skipTest("python-docx not installed")
        text = "\n".join(p.text for p in doc.paragraphs)
        self.assertIn("Open Positions", text)
        self.assertIn("Materials Engineer, Soft Actuators", text)
        self.assertIn("Figure AI", text)
        self.assertIn("https://x/job", text)

    def test_write_jobs_doc_creates_dated_file(self):
        doc = build_jobs_document(self.PAYLOAD, week_start="2026-06-22", week_end="2026-06-28")
        if doc is None:
            self.skipTest("python-docx not installed")
        with tempfile.TemporaryDirectory() as tmpdir:
            path = write_jobs_doc(self.PAYLOAD, week_start="2026-06-22", week_end="2026-06-28", output_dir=tmpdir)
            self.assertIsNotNone(path)
            self.assertTrue(path.exists())
            self.assertEqual(path.name, "SoftRobotics_Jobs_2026-06-28.docx")


class SectionPageRenderTests(unittest.TestCase):
    def test_render_materials_table(self):
        section = {"week_start": "2026-06-22", "week_end": "2026-06-28",
                   "payload": {"materials": [{"application": "Hand actuator", "material_class": "DEA",
                                              "key_properties": "high strain", "open_challenge": "durability",
                                              "source_url": "https://x/1"}]}}
        html = site_build.render_materials(SITE_CONFIG, section)
        self.assertIn("Material Requirements", html)
        self.assertIn("Hand actuator", html)
        self.assertIn("durability", html)
        self.assertIn("https://x/1", html)

    def test_render_materials_empty(self):
        html = site_build.render_materials(SITE_CONFIG, None)
        self.assertIn("No material requirements", html)


if __name__ == "__main__":
    unittest.main()
