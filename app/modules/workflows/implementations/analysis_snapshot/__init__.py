"""Analysis Snapshot workflow implementation.

Temporal Workflow for generating analysis snapshots.

Note: Activities are NOT imported here to avoid Temporal sandbox
restrictions. The sandbox validates workflow modules and any
transitive imports of I/O libraries (langchain, requests, etc.)
would cause sandbox violations.

Import workflow and activities directly where needed:
    from ...workflow import SnapshotWorkflow
    from ...activities import load_assistant, generate_profile, ...
"""
