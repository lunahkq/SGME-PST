#!/bin/bash
# Script to clean the log file runserver_silent.log
# Must be run from the Linux/ directory

# Navigate to project root
cd "$(dirname "$0")/.."

# Clear the log file
> runserver_silent.log

echo "Log file runserver_silent.log has been cleaned."
