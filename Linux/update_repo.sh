#!/bin/bash
# Script to update the repository
# Must be run from the Linux/ directory

cd "$(dirname "$0")/.."

echo "Updating repository..."
git pull

echo "Update complete."
