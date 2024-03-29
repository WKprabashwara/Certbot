"""Shim around `~certbot_dns_route53._internal.dns_route53` for backwards compatibility."""
import warnings

from certbot_dns_route53._internal import dns_route53


class Authenticator(dns_route53.Authenticator):
    """Shim around `~certbot_dns_route53._internal.dns_route53.Authenticator`
       for backwards compatibility."""

    hidden = True

    def __init__(self, *args, **kwargs):
        warnings.warn("The 'authenticator' module was renamed 'dns_route53'",
                      DeprecationWarning)
        super().__init__(*args, **kwargs)
