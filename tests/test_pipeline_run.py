import json
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
            duplicate = Item.from_source(
                title="Soft robotic actuator with elastomer (repost)", url="https://x/p2", source_type="t",
                source_name="E", tier="A", abstract="soft robot actuator using elastomer",
            )
            duplicate.status = "dropped_dup"
            with connect(db_path) as db:
                init_db(db)
                upsert_items(db, [robotics, offtopic, duplicate])

            pipeline_run.rescore_archive(config_path=str(config_path), db_path=str(db_path), weekly_synthesis=False)

            with connect(db_path) as db:
                statuses = dict(db.execute("SELECT title, status FROM items"))
            self.assertEqual(statuses["Soft robotic actuator with elastomer"], "included")
            self.assertEqual(statuses["Machine learning for steel welding"], "dropped_lowscore")
            # would score as included, but a duplicate must stay a duplicate
            self.assertEqual(statuses["Soft robotic actuator with elastomer (repost)"], "dropped_dup")

    def test_rescore_archive_reenriches_fallback_why_it_matters(self):
        from unittest.mock import patch

        from pipeline.enrich import FALLBACK_WHY_IT_MATTERS
        from store.db import init_db, upsert_items

        class FakeModelClient:
            def complete_json(self, **kwargs):
                return {
                    "relevance": 90, "quality": 80, "theme": "Actuators", "reason": "r",
                    "summary": "Model summary.", "why_it_matters": "Model why.",
                }, {}

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            config_path = root / "targeting.yaml"
            db_path = root / "tracker.db"
            config_path.write_text(
                "\n".join(
                    [
                        "site: {name: SoftRobotics Intelligence, description: d, url: https://x/}",
                        "targeting: {robotics_terms: [soft robot], exclude_terms: [], materials_boost_terms: []}",
                        "scoring: {model: m, min_score: 70}",
                        "enrich: {model: m, max_items_per_run: 1}",
                    ]
                ),
                encoding="utf-8",
            )
            stale = []
            for index in range(2):
                item = Item.from_source(
                    title=f"Soft robot gripper {index}", url=f"https://x/{index}", source_type="t",
                    source_name="E", tier="A", abstract="soft robot gripper",
                )
                item.status = "included"
                item.summary = item.abstract
                item.why_it_matters = FALLBACK_WHY_IT_MATTERS
                stale.append(item)
            written = Item.from_source(
                title="Soft robot skin", url="https://x/skin", source_type="t",
                source_name="E", tier="A", abstract="soft robot skin",
            )
            written.status = "included"
            written.summary = "Earlier summary."
            written.why_it_matters = "Earlier why."
            with connect(db_path) as db:
                init_db(db)
                upsert_items(db, [*stale, written])

            client = FakeModelClient()
            with patch("pipeline.score.build_anthropic_client", return_value=client), patch(
                "pipeline.enrich.build_anthropic_client", return_value=client
            ):
                pipeline_run.rescore_archive(config_path=str(config_path), db_path=str(db_path), weekly_synthesis=False)

            with connect(db_path) as db:
                why = dict(db.execute("SELECT title, why_it_matters FROM items"))
            # both stale items are backfilled despite max_items_per_run: 1
            self.assertEqual(why["Soft robot gripper 0"], "Model why.")
            self.assertEqual(why["Soft robot gripper 1"], "Model why.")
            self.assertEqual(why["Soft robot skin"], "Earlier why.")

    def test_resynthesize_archive_regenerates_every_stored_week(self):
        from unittest.mock import patch

        from store.db import init_db, upsert_items, upsert_weekly_summary

        class FakeModelClient:
            def complete_json(self, **kwargs):
                return {"synthesis_md": "## This week in brief\n\nModel narrative."}, {"output_tokens": 7}

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            config_path = root / "targeting.yaml"
            db_path = root / "tracker.db"
            config_path.write_text(
                "site: {name: SoftRobotics Intelligence, description: d, url: https://x/}\nsynth: {model: m}\n",
                encoding="utf-8",
            )
            weeks = [("2026-09-07", "2026-09-13"), ("2026-09-14", "2026-09-20")]
            items = []
            for index, (week_start, _week_end) in enumerate(weeks):
                item = Item.from_source(
                    title=f"Soft robot item {index}", url=f"https://x/{index}", source_type="t",
                    source_name="E", tier="A", abstract="soft robot", published_date=week_start,
                )
                item.status = "included"
                items.append(item)
            with connect(db_path) as db:
                init_db(db)
                upsert_items(db, items)
                for week_start, week_end in weeks:
                    upsert_weekly_summary(
                        db, week_start=week_start, week_end=week_end, synthesis_md="old fallback", item_ids=[],
                    )

            with patch("pipeline.synth.build_anthropic_client", return_value=FakeModelClient()):
                pipeline_run.resynthesize_archive(config_path=str(config_path), db_path=str(db_path))

            with connect(db_path) as db:
                summaries = list(db.execute("SELECT synthesis_md, item_ids FROM weekly_summaries"))
                run = db.execute("SELECT counts_json, token_usage_json FROM runs").fetchone()
            self.assertEqual(len(summaries), 2)
            for synthesis_md, item_ids in summaries:
                self.assertIn("Model narrative.", synthesis_md)
                self.assertEqual(len(json.loads(item_ids)), 1)
            self.assertIn('"resynthesized": 2', run["counts_json"])
            self.assertIn("anthropic_synthesis", run["token_usage_json"])


if __name__ == "__main__":
    unittest.main()
