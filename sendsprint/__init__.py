"""SendSprint — autonomous sprint-to-PR delivery agent.

The agent (Claude, driving this package) reads a sprint from Jira / Azure
DevOps / GitHub Issues, hands each task to simplicio-cli for the code edit,
captures evidence, and opens a draft PR for review. simplicio-cli is the
executor; SendSprint owns the flow start to finish.
"""

__version__ = "1.2.3"
__all__ = ["__version__"]
