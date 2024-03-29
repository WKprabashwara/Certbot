"""Null plugin."""
import logging

from certbot import interfaces
from certbot.plugins import common

logger = logging.getLogger(__name__)


class Installer(common.Plugin, interfaces.Installer):
    """Null installer."""

    description = "Null Installer"
    hidden = True

    @classmethod
    def add_parser_arguments(cls, add):
        pass

    # pylint: disable=missing-function-docstring

    def prepare(self):
        pass  # pragma: no cover

    def more_info(self):
        return "Installer that doesn't do anything (for testing)."

    def get_all_names(self):
        return []

    def deploy_cert(self, domain, cert_path, key_path,
                    chain_path=None, fullchain_path=None):
        pass  # pragma: no cover

    def enhance(self, domain, enhancement, options=None):
        pass  # pragma: no cover

    def supported_enhancements(self):
        return []

    def save(self, title=None, temporary=False):
        pass  # pragma: no cover

    def rollback_checkpoints(self, rollback=1):
        pass  # pragma: no cover

    def recovery_routine(self):
        pass  # pragma: no cover

    def config_test(self):
        pass  # pragma: no cover

    def restart(self):
        pass  # pragma: no cover
