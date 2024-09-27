#!/bin/bash

pip uninstall pgamit -y
rm -rf dist
python3 setup.py sdist
pip install dist/*.tar.gz --user
