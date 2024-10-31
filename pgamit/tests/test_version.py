# Author: Shane Grigsby (espg) <refuge@rocktalus.com>
# Created: October 2024

from importlib.metadata import version
import pgamit

assert version("pgamit") == pgamit.__version__
