"""Run pipeline placeholder
Simple script to run the example workflow using a dynamic import so it works even when the package layout
is not installed as a proper Python package.
"""

import importlib.util
from pathlib import Path

# Resolve the workflow_graph module path relative to this file
base_dir = Path(__file__).resolve().parents[1]
module_path = base_dir / "pipeline" / "agents" / "orchestrator" / "workflow_graph.py"

spec = importlib.util.spec_from_file_location("workflow_graph", str(module_path))
workflow_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(workflow_mod)

if __name__ == "__main__":
    workflow_mod.run_workflow()
