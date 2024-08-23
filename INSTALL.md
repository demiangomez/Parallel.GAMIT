Installation
=================


Prerequisites
---------------

These are easiest to install dependencies for Parallel.GAMIT is using
[mamba](https://github.com/mamba-org/mamba); see
[here](https://mamba.readthedocs.io/en/latest/index.html) for instructions on
installing mamba.

Once mamba is installed, the environment can be built (and activated) within
the base directory of Parallel.GAMIT:

```
mamba env create -f environment.yml
conda activate pgamit
```

Alternatively, the `environment.yml` file contains all of the perquisites
(with minimum required version numbers), which can be installed manually
using pip.

