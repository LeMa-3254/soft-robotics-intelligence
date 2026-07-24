from pathlib import Path
import tempfile
import unittest

from models import Item
import pipeline.run as pipeline_run
from store.db import connect


class PipelineRunTests(unittest.TestCase):
    def test_pipeline_dry_run_writes_items_run_log_and_weekly_summary(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            config_path = root / "targeting.yaml"
            db_path = root / "tracker.db"
            week_start, _week_end = pipeline_run.last_complete_week_bounds()
            config_path.write_text(
                "\n".join(
                    [
                        "site:",
                        "  name: Polymind",
                        "  description: Daily feed plus weekly synthesis.",
                        "  url: https://polymind.github.io/",
                        "targeting:",
                        "  robotics_terms: [soft robot, humanoid, robot]",
                        "  exclude_terms: []",
                        "  materials_boost_terms: [elastomer]",
                        "sources: {}",
                        "scoring:",
                        "  min_score: 70",
                        "dedup:",
                        "  window_days: 30",
                        "  similarity_threshold: 0.92",
                        "  on_duplicate: drop",
                        "enrich:",
                        "  max_items_per_run: 5",
                        "synth: {}",
                    ]
                ),
                encoding="utf-8",
            )

            def fake_ingest(_config):
                item = Item.from_source(
                    title="Soft robot with self-healing elastomer skin",
                    url="https://example.test/paper",
                    source_type="test",
                    source_name="Example",
                    tier="A",
                    published_date=week_start,
                    abstract="A soft robotic actuator using a self-healing elastomer.",
                )
                return [item], []

            original_ingest = pipeline_run.ingest_enabled_sources
            pipeline_run.ingest_enabled_sources = fake_ingest
            try:
                exit_code = pipeline_run.run_pipeline(
                    config_path=str(config_path),
                    db_path=str(db_path),
                    weekly_synthesis=True,
                )
            finally:
                pipeline_run.ingest_enabled_sources = original_ingest

            self.assertEqual(exit_code, 0)
            with connect(db_path) as db:
                item_count = db.execute("SELECT COUNT(*) FROM items WHERE status = 'included'").fetchone()[0]
                run_count = db.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
                weekly_count = db.execute("SELECT COUNT(*) FROM weekly_summaries").fetchone()[0]

        self.assertEqual(item_count, 1)
        self.assertEqual(run_count, 1)
        self.assertEqual(weekly_count, 1)

    def test_is_fresh_drops_old_keeps_recent_and_undated(self):
        from datetime import date, timedelta

        config = {"meta": {"max_age_days": 30}}
        recent = Item.from_source(
            title="t", url="https://x/r", source_type="t", source_name="E", tier="A",
            published_date=(date.today() - timedelta(days=5)).isoformat(),
        )
        old = Item.from_source(
            title="t", url="https://x/o", source_type="t", source_name="E", tier="A",
            published_date=(date.today() - timedelta(days=400)).isoformat(),
        )
        undated = Item.from_source(
            title="t", url="https://x/u", source_type="t", source_name="E", tier="A",
        )

        self.assertTrue(pipeline_run.is_fresh(recent, config))
        self.assertFalse(pipeline_run.is_fresh(old, config))
        self.assertTrue(pipeline_run.is_fresh(undated, config))
        # window disabled when max_age_days is unset/zero
        self.assertTrue(pipeline_run.is_fresh(old, {"meta": {}}))

    def test_rescore_archive_drops_items_failing_current_gate(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            config_path = root / "targeting.yaml"
            db_path = root / "tracker.db"
            config_path.write_text(
                "\n".join(
                    [
                        "site: {name: SoftRobotics Intelligence, description: d, url: https://x/}",
                        "targeting:",
                        "  robotics_terms: [soft robot, humanoid, robot]",
                        "  exclude_terms: []",
                        "  materials_boost_terms: [elastomer]",
                        "scoring: {min_score: 70}",
                        "synth: {}",
                    ]
                ),
                encoding="utf-8",
            )
            from store.db import init_db, upsert_items

            robotics = Item.from_source(
                title="Soft robotic actuator with elastomer", url="https://x/p", source_type="t",
                source_name="E", tier="A", abstract="soft robot actuator using elastomer",
            )
            robotics.status = "included"
            offtopic = Item.from_source(
                title="Machine learning for steel welding", url="https://x/s", source_type="t",
                source_name="E", tier="A", abstract="stainless steel weld optimization",
            )
            offtopic.status = "included"
            with connect(db_path) as db:
                init_db(db)
                upsert_items(db, [robotics, offtopic])

            pipeline_run.rescore_archive(config_path=str(config_path), db_path=str(db_path), weekly_synthesis=False)

            with connect(db_path) as db:
                statuses = dict(db.execute("SELECT title, status FROM items"))
            self.assertEqual(statuses["Soft robotic actuator with elastomer"], "included")
            self.assertEqual(statuses["Machine learning for steel welding"], "dropped_lowscore")


if __name__ == "__main__":
    unittest.main()
