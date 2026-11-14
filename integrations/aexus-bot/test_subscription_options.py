"""Cross-platform subscription hints use real schemas; no credentials, network or models."""
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
import yaml
from xhs_local.configuration.models import SourceConfig, SourcesConfig, TargetConfig
from xhs_local.pipeline.agents import AgentsTarget
from xhs_local.plugins.registry import validate_options
from xhs_local.plugins.contracts import PluginTarget
from xhs_local.plugins.sources.telegram.plugin import TelegramSourcePlugin
from xhs_local.website import WebsiteSubscriptions


class SubscriptionOptionsTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.original = SourcesConfig(version=1, sources=tuple(
            SourceConfig(id=plugin, plugin=plugin, poll_seconds=300,
                         options={"fixture_auth_reference": plugin},
                         targets=(TargetConfig(id=plugin+"-old", locator="fixture_author", name=plugin,
                                               options={"prefetch_documents": True} if plugin == "telegram" else {}),))
            for plugin in ["telegram", "x", "youtube"]))
        self.scheduler = NS(snapshot=NS(sources=self.original), collector=NS(set_sources=lambda _: None))
        parent = self

        class Manager(WebsiteSubscriptions):
            async def _apply(self, current, sources):
                root = Path(__file__).resolve().parents[2]
                for source in sources.sources:
                    schema = yaml.safe_load((root/"src/xhs_local/plugins/sources"/source.plugin/"manifest.yaml").read_text())["target_options"]
                    for target in source.targets:
                        validate_options(dict(target.options), schema, label="target")
                        if source.plugin == "telegram":
                            TelegramSourcePlugin.validate_target(PluginTarget(
                                id=target.id, locator=target.locator, name=target.name,
                                options=target.options))
                parent.scheduler.snapshot = NS(sources=sources)

        self.manager = Manager(self.scheduler, None)

    def target(self, plugin, suffix="old", **kwargs):
        return AgentsTarget(sourceId="ns_"+plugin+"_"+suffix, targetId=plugin+"-"+suffix,
                            plugin=plugin, locator="https://www.youtube.com/@fixture_author" if plugin == "youtube" else "fixture_author", name=plugin,
                            enabled=True, pollSeconds=300, collectFiles=True, **kwargs)

    async def test_file_storage_hint_does_not_inject_telegram_options_into_other_platforms(self):
        targets = [self.target(plugin, suffix) for plugin in ["telegram", "x", "youtube"] for suffix in ["old", "new"]]
        await self.manager.apply_agents_targets(targets)
        for source in self.scheduler.snapshot.sources.sources:
            self.assertEqual(source.options, {"fixture_auth_reference": source.plugin})
            self.assertEqual(len(source.targets), 2)
            for target in source.targets:
                if source.plugin == "telegram":
                    self.assertTrue(target.options["collect_documents"])
                else:
                    self.assertEqual(target.options, {})
        telegram = self.scheduler.snapshot.sources.sources[0]
        self.assertTrue(telegram.targets[0].options["prefetch_documents"])

    async def test_empty_snapshot_disables_targets_and_reactivation_keeps_native_identity(self):
        await self.manager.apply_agents_targets([])
        self.assertTrue(all(not source.enabled for source in self.scheduler.snapshot.sources.sources))
        await self.manager.apply_agents_targets([self.target("youtube")])
        youtube = next(source for source in self.scheduler.snapshot.sources.sources if source.plugin == "youtube")
        self.assertTrue(youtube.enabled)
        self.assertEqual(youtube.targets[0].id, "youtube-old")
        self.assertEqual(youtube.options, {"fixture_auth_reference": "youtube"})

    async def test_telegram_core_homepage_and_preview_links_reach_the_native_plugin_as_handles(self):
        for locator in ["@FixtureChannel", "https://t.me/FixtureChannel",
                        "https://t.me/s/FixtureChannel?utm_source=fixture",
                        "https://telegram.me/FixtureChannel/123"]:
            await self.manager.apply_agents_targets([
                self.target("telegram", "new").model_copy(update={"locator": locator})])
            telegram = self.scheduler.snapshot.sources.sources[0]
            target = next(t for t in telegram.targets if t.id == "telegram-new")
            self.assertEqual(target.locator, "FixtureChannel")


if __name__ == "__main__":
    unittest.main(verbosity=2)
