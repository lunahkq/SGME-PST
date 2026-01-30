#!/usr/bin/env bash
cd "$(dirname "$0")"

./venv/bin/python runserver.py >> runserver_silent.log 2>&1 &

