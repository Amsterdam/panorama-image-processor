#!/usr/bin/env bash

set -u # crash on missing env
set -e # stop on any error

# Clear any cached results
find . -name "*.pyc" -exec rm -f {} \;

echo "Running style checks"
flake8

echo "Running unit tests"
pytest tests/

echo "Running coverage tests"
export COVERAGE_FILE=/tmp/.coverage
pytest --cov=panorama_image_processor --cov-report html --cov-fail-under=10 tests/
