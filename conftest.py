import os
# Isolated test-only auth bypass; do not use this environment variable in deployments.
os.environ["AETHER_ENV"]="test"
