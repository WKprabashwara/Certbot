"""Parse command line and call the appropriate functions.

.. todo:: Sanity check all input.  Be sure to avoid shell code etc...

"""
import argparse
import logging
import os
import pkg_resources
import sys

import confargparse
import zope.component
import zope.interface.exceptions
import zope.interface.verify

import letsencrypt

from letsencrypt.client import account
from letsencrypt.client import configuration
from letsencrypt.client import client
from letsencrypt.client import errors
from letsencrypt.client import interfaces
from letsencrypt.client import log
from letsencrypt.client.display import util as display_util
from letsencrypt.client.display import ops as display_ops


SETUPTOOLS_AUTHENTICATORS_ENTRY_POINT = "letsencrypt.authenticators"
"""Setuptools entry point group name for Authenticator plugins."""


def init_auths(config):
    """Find (setuptools entry points) and initialize Authenticators."""
    # TODO: handle collisions in authenticator names. Or is this
    # already handled for us by pkg_resources?
    auths = {}
    for entrypoint in pkg_resources.iter_entry_points(
            SETUPTOOLS_AUTHENTICATORS_ENTRY_POINT):
        auth_cls = entrypoint.load()
        auth = auth_cls(config)
        try:
            zope.interface.verify.verifyObject(interfaces.IAuthenticator, auth)
        except zope.interface.exceptions.BrokenImplementation:
            logging.debug(
                "%r object does not provide IAuthenticator, skipping",
                entrypoint.name)
        else:
            auths[entrypoint.name] = auth
    return auths


def create_parser():
    """Create parser."""
    parser = confargparse.ConfArgParser(
        description="letsencrypt client %s" % letsencrypt.__version__)

    add = parser.add_argument
    config_help = lambda name: interfaces.IConfig[name].__doc__

    add("-d", "--domains", metavar="DOMAIN", nargs="+")
    add("-s", "--server",
        default="www.letsencrypt-demo.org/acme/new-reg",
        help=config_help("server"))

    # TODO: we should generate the list of choices from the set of
    # available authenticators, but that is tricky due to the
    # dependency between init_auths and config. Hardcoding it for now.
    add("-a", "--authenticator", dest="authenticator",
        help=config_help("authenticator"))

    add("-k", "--authkey", type=read_file,
        help="Path to the authorized key file")
    add("-m", "--email", type=str,
        help="Email address used for account registration.")
    add("-B", "--rsa-key-size", type=int, default=2048, metavar="N",
        help=config_help("rsa_key_size"))

    add("-R", "--revoke", action="store_true",
        help="Revoke a certificate from a menu.")
    add("--revoke-certificate", dest="rev_cert", type=read_file,
        help="Revoke a specific certificate.")
    add("--revoke-key", dest="rev_key", type=read_file,
        help="Revoke all certs generated by the provided authorized key.")

    add("-b", "--rollback", type=int, default=0, metavar="N",
        help="Revert configuration N number of checkpoints.")
    add("-v", "--view-config-changes", action="store_true",
        help="View checkpoints and associated configuration changes.")

    # TODO: resolve - assumes binary logic while client.py assumes ternary.
    add("-r", "--redirect", action="store_true",
        help="Automatically redirect all HTTP traffic to HTTPS for the newly "
             "authenticated vhost.")

    add("--no-confirm", dest="no_confirm", action="store_true",
        help="Turn off confirmation screens, currently used for --revoke")

    add("-e", "--agree-tos", dest="tos", action="store_true",
        help="Skip the end user license agreement screen.")
    add("-t", "--text", dest="use_curses", action="store_false",
        help="Use the text output instead of the curses UI.")

    add("--config-dir", default="/etc/letsencrypt",
        help=config_help("config_dir"))
    add("--work-dir", default="/var/lib/letsencrypt",
        help=config_help("work_dir"))
    add("--backup-dir", default="/var/lib/letsencrypt/backups",
        help=config_help("backup_dir"))
    add("--key-dir", default="/etc/letsencrypt/keys",
        help=config_help("key_dir"))
    add("--cert-dir", default="/etc/letsencrypt/certs",
        help=config_help("cert_dir"))

    add("--le-vhost-ext", default="-le-ssl.conf",
        help=config_help("le_vhost_ext"))
    add("--cert-path", default="/etc/letsencrypt/certs/cert-letsencrypt.pem",
        help=config_help("cert_path"))
    add("--chain-path", default="/etc/letsencrypt/certs/chain-letsencrypt.pem",
        help=config_help("chain_path"))

    add("--apache-server-root", default="/etc/apache2",
        help=config_help("apache_server_root"))
    add("--apache-mod-ssl-conf", default="/etc/letsencrypt/options-ssl.conf",
        help=config_help("apache_mod_ssl_conf"))
    add("--apache-ctl", default="apache2ctl", help=config_help("apache_ctl"))
    add("--apache-enmod", default="a2enmod", help=config_help("apache_enmod"))
    add("--apache-init-script", default="/etc/init.d/apache2",
        help=config_help("apache_init_script"))

    add("--nginx-server-root", default="/etc/nginx",
        help=config_help("nginx_server_root"))
    add("--nginx-mod-ssl-conf",
        default="/etc/letsencrypt/options-ssl-nginx.conf",
        help=config_help("nginx_mod_ssl_conf"))
    add("--nginx-ctl", default="nginx", help=config_help("nginx_ctl"))

    return parser


def main():  # pylint: disable=too-many-branches, too-many-statements
    """Command line argument parsing and main script execution."""
    # note: arg parser internally handles --help (and exits afterwards)
    args = create_parser().parse_args()
    config = configuration.NamespaceConfig(args)

    # note: check is done after arg parsing as --help should work w/o root also.
    if not os.geteuid() == 0:
        sys.exit(
            "{0}Root is required to run letsencrypt.  Please use sudo.{0}"
            .format(os.linesep))

    # Set up logging
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    if args.use_curses:
        logger.addHandler(log.DialogHandler())
        displayer = display_util.NcursesDisplay()
    else:
        displayer = display_util.FileDisplay(sys.stdout)

    zope.component.provideUtility(displayer)

    if args.view_config_changes:
        client.view_config_changes(config)
        sys.exit()

    if args.revoke or args.rev_cert is not None or args.rev_key is not None:
        # This depends on the renewal config and cannot be completed yet.
        zope.component.getUtility(interfaces.IDisplay).notification(
            "Revocation is not available with the new Boulder server yet.")

        # client.revoke(config, args.no_confirm, args.rev_cert, args.rev_key)
        sys.exit()

    if args.rollback > 0:
        client.rollback(args.rollback, config)
        sys.exit()

    # Prepare for init of Client
    if args.email is None:
        acc = client.determine_account(config)
    else:
        try:
            # The way to get the default would be args.email = ""
            # First try existing account
            acc = account.Account.from_existing_account(config, args.email)
        except errors.LetsEncryptClientError:
            try:
                # Try to make an account based on the email address
                acc = account.Account.from_email(config, args.email)
            except errors.LetsEncryptClientError:
                sys.exit(1)

    if acc is None:
        sys.exit(0)

    all_auths = init_auths(config)
    logging.debug('Initialized authenticators: %s', all_auths.keys())
    try:
        auth = client.determine_authenticator(all_auths, config)
        logging.debug("Selected authenticator: %s", auth)
    except errors.LetsEncryptClientError as err:
        logging.critical(str(err))
        sys.exit(1)

    if auth is None:
        sys.exit(0)

    # Use the same object if possible
    if interfaces.IInstaller.providedBy(auth):  # pylint: disable=no-member
        installer = auth
    else:
        # This is simple and avoids confusion right now.
        installer = None

    if args.domains is None:
        doms = display_ops.choose_names(installer)
    else:
        doms = args.domains

    if not doms:
        sys.exit(0)

    acme = client.Client(config, acc, auth, installer)

    # Validate the key and csr
    client.validate_key_csr(acc.key)

    # This more closely mimics the capabilities of the CLI
    # It should be possible for reconfig only, install-only, no-install
    # I am not sure the best way to handle all of the unimplemented abilities,
    # but this code should be safe on all environments.
    cert_file = None
    if auth is not None:
        if acc.regr is None:
            try:
                acme.register()
            except errors.LetsEncryptClientError:
                sys.exit(0)
        cert_file, chain_file = acme.obtain_certificate(doms)
    if installer is not None and cert_file is not None:
        acme.deploy_certificate(doms, acc.key, cert_file, chain_file)
    if installer is not None:
        acme.enhance_config(doms, args.redirect)


def read_file(filename):
    """Returns the given file's contents with universal new line support.

    :param str filename: Filename

    :returns: A tuple of filename and its contents
    :rtype: tuple

    :raises argparse.ArgumentTypeError: File does not exist or is not readable.

    """
    try:
        return filename, open(filename, "rU").read()
    except IOError as exc:
        raise argparse.ArgumentTypeError(exc.strerror)


if __name__ == "__main__":
    main()
