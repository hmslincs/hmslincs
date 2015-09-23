from django.utils.log import getLogger
import logging


LOG_WARN = 0
LOG_INFO = 1
LOG_DEBUG = 2

class SimpleLoggingMixin(object):

    def configure_logging(self, options):
        "Configure a standardized logging setup based on the verbosity option."
        self._verbosity = int(options['verbosity'])
        if not 0 <= self._verbosity <= 3:
            raise ValueError("Verbosity must be between 0 and 3")
        # Level 3 also sets the root logger to DEBUG.
        if self._verbosity == 3:
            getLogger().setLevel(logging.DEBUG)

    def warning(self, msg, *args):
        self._log(LOG_WARN, msg, *args)

    def info(self, msg, *args):
        self._log(LOG_INFO, msg, *args)

    def debug(self, msg, *args):
        self._log(LOG_DEBUG, msg, *args)

    def _log(self, level, msg, *args):
        if self._verbosity >= level:
            print msg % args
