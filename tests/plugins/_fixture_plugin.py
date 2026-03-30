"""Minimal plugin fixture for PluginReloader tests."""
from packages.decorators import plugin
from packages.plugins import BasePlugin


@plugin(name="fixture-plugin", version="0.1.0", description="test fixture")
class FixturePlugin(BasePlugin):
    pass
