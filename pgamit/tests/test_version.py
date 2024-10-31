# Author: Shane Grigsby (espg) <refuge@rocktalus.com>
# Created: October 2024

from importlib.metadata import version, PackageNotFoundError
import pytest
import pgamit

assert importlib.metadata.version("pgamit") == pgamit.__version__
