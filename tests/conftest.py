import os
import sys

# Make the in-repo package importable without an install step.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
