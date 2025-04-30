#!/bin/bash
# start.sh - Explicit startup script for gunicorn

# Activate virtual environment if using one
# source venv/bin/activate

# Run gunicorn from the Python environment
python -m gunicorn app:app