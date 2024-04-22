from typing import Generator
from .workflow_run import WorkflowRun

###############################################################################
# Perform cleanup procedures on a closed Pull Request
###############################################################################
def pr_runs(
  repo: str,
  pr_no: int,
  result: str | None = None,
  category: str | None = None,
  **select_args,
) -> Generator[WorkflowRun, None, None]:
  filter = (
    f"{result+' ' if result else ''}'PR '#{pr_no} '[{category if category is not None else ''}"
  )
  select_args.setdefault("prompt", f"runs for PR #{pr_no}")
  return WorkflowRun.select(repo, filter, **select_args)
