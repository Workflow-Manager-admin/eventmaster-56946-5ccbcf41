#!/bin/bash
cd /home/kavia/workspace/code-generation/eventmaster-56946-5ccbcf41/event_manager_backend_workspace/event_manager_backend
source venv/bin/activate
flake8 .
LINT_EXIT_CODE=$?
if [ $LINT_EXIT_CODE -ne 0 ]; then
  exit 1
fi

