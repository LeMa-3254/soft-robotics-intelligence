import tempfile
from pathlib import Path
import importlib.util
import unittest

from models import Item
from store.db import (
    connect,
    included_items,
    included_items_between,
    init_db,
    latest_weekly_summary,
    log_run,
    upsert_items,
    upsert_weekly_summary,
    weekly_summaries,
)


SITE_BUILD_PATH = Path(__file__).resolve().parents[1] / "site" / "build.py"
SPEC = importlib.util.spec_from_file_location("polymind_site_build", SITE_BUILD_PATH)
site_build = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(site_build)


class StoreTests(unittest.TestCase):
    def test_init_upsert_and_query_included_items(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "tracker.db"
            item = Item.from_source(
                title="Machine learning for polymer design",
                url="https://example.test/paper",
                source_type="test",
                source_name="Example",
                tier="A",
            )
            item.status = "included"
            item.summary = "A useful test item."
            item.why_it_matters = "It proves the store path works."

            with connect(db_path) as db:
                init_db(db)
                upsert_items(db, [item])
                log_run(db, counts={"fetched": 1, "included": 1})
                rows = included_items(db)

            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["title"], "Machine learning for polymer design")

    def test_static_render_includes_item_and_rss_metadata(self):
        config = {
            "site": {
                "name": "Polymind",
                "description": "Daily feed plus weekly synthesis.",
                "url": "https://polymind.github.io/",
            }
        }
        item = {
            "id": "abc123",
            "title": "Soft robotic gripper with dielectric elastomer",
            "url": "https://example.test/paper",
            "source_name": "Example",
            "published_date": "2026-06-29",
            "fetched_date": "2026-06-29",
            "theme": "humanoid_robotics",
            "summary": "A useful test item.",
            "abstract": None,
            "why_it_matters": "It proves rendering works.",
        }

        html = site_build.render_index(config, [item])
        rss = site_build.render_rss(config, [item])

        self.assertIn("Soft robotic gripper with dielectric elastomer", html)
        self.assertIn("Humanoid Robotics", html)
        self.assertIn("https://polymind.github.io/", rss)

    def test_archive_render_includes_filters_and_items(self):
        config = {
            "site": {
                "name": "Polymind",
                "description": "Daily feed plus weekly synthesis.",
                "url": "https://polymind.github.io/",
            }
        }
        items = [
            {
                "id": "abc123",
                "title": "Machine learning for polymer design",
                "url": "https://example.test/paper",
                "source_name": "Example",
                "published_date": "2026-06-29",
                "fetched_date": "2026-06-29",
                "theme": "humanoid robotics",
                "summary": "A useful test item.",
                "abstract": None,
                "why_it_matters": "It proves rendering works.",
            }
        ]

        html = site_build.render_archive(config, items)

        self.assertIn('id="search"', html)
        self.assertIn('value="Example"', html)
        self.assertIn('value="Humanoid Robotics"', html)
        self.assertIn("Machine learning for polymer design", html)

    def test_archive_json_escapes_script_closing_sequences(self):
        rendered = site_build.json_for_script([{"title": "</script><p>bad</p>"}])

        self.assertIn("<\\/script>", rendered)
        self.assertNotIn("</script>", rendered)

    def test_markdown_heading_formats_theme_identifiers(self):
        html = site_build.markdown_to_html("### materials_informatics_property_prediction")

        self.assertIn("materials informatics property prediction", html)

    def test_within_days_windows_by_effective_date(self):
        from datetime import date, timedelta

        recent = {"published_date": (date.today() - timedelta(days=10)).isoformat(), "fetched_date": None}
        old = {"published_date": (date.today() - timedelta(days=200)).isoformat(), "fetched_date": None}
        undated = {"published_date": None, "fetched_date": None}

        self.assertTrue(site_build.within_days(recent, 30))
        self.assertFalse(site_build.within_days(old, 30))
        self.assertTrue(site_build.within_days(undated, 30))   # undated treated as current
        self.assertTrue(site_build.within_days(old, 0))        # window disabled

    def test_build_site_writes_archive_page(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "tracker.db"
            config_path = Path(tmpdir) / "targeting.yaml"
            output_dir = Path(tmpdir) / "public"
            config_path.write_text(
                "\n".join(
                    [
                        "site:",
                        "  name: Polymind",
                        "  description: Daily feed plus weekly synthesis.",
                        "  url: https://polymind.github.io/",
                    ]
                ),
                encoding="utf-8",
            )
            item = Item.from_source(
                title="Machine learning for polymer design",
                url="https://example.test/paper",
                source_type="test",
                source_name="Example",
                tier="A",
            )
            item.status = "included"

            with connect(db_path) as db:
                init_db(db)
                upsert_items(db, [item])

            site_build.build_site(config_path=str(config_path), db_path=str(db_path), output_dir=str(output_dir))

            self.assertTrue((output_dir / "archive.html").exists())
            self.assertTrue((output_dir / "index.json").exists())

    def test_weekly_summary_store_and_render(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "tracker.db"
            item = Item.from_source(
                title="Machine learning for polymer design",
                url="https://example.test/paper",
                source_type="test",
                source_name="Example",
                tier="A",
                published_date="2026-06-29",
            )
            item.status = "included"

            with connect(db_path) as db:
                init_db(db)
                upsert_items(db, [item])
                rows = included_items_between(db, start_date="2026-06-29", end_date="2026-07-05")
                upsert_weekly_summary(
                    db,
                    week_start="2026-06-29",
                    week_end="2026-07-05",
                    synthesis_md="## Weekly Synthesis\n\nA useful trend.",
                    item_ids=[row["id"] for row in rows],
                )
                latest = latest_weekly_summary(db)
                summaries = weekly_summaries(db)

        config = {
            "site": {
                "name": "Polymind",
                "description": "Daily feed plus weekly synthesis.",
                "url": "https://polymind.github.io/",
            }
        }

        self.assertEqual(len(rows), 1)
        self.assertEqual(latest["week_start"], "2026-06-29")
        self.assertIn("Weekly Synthesis", site_build.render_weekly(config, summaries))


if __name__ == "__main__":
    unittest.main()
