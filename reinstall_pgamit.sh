#!/bin/bash

pip uninstall pgamit -y
python setup.py sdist
pip install dist/*.tar.gz --user