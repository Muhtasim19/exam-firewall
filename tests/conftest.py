import sys
import os
import logging

# Pre-initialise the root logger with a StreamHandler so that when firewall.py
# runs its module-level ``logging.basicConfig(filename=…)`` call, it becomes a
# no-op (basicConfig is idempotent once handlers exist).  This prevents the
# test runner from trying to create /var/log/exam-firewall.log.
logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

# Ensure the project root is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
