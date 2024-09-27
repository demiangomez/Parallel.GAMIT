#!/bin/bash

pip uninstall pgamit -y
rm -rf dist
python setup.py sdist
pip install dist/*.tar.gz --user
