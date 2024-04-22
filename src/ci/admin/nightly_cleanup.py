from .workflow_run import WorkflowRun
from .log import log
from .globals import script_noninteractive

###############################################################################
# Nightly Release - periodic cleanup
###############################################################################
def nightly_cleanup(repo: str, noop: bool = False) -> None:
  preserved = []
  removed = []

  def _pick_preserved(runs: list[WorkflowRun]) -> list[WorkflowRun]:
    latest = runs[-1]
    result = [latest]
    if latest.outcome != "GOOD":
      latest_ok = next((run for run in reversed(runs) if run.outcome == "GOOD"), None)
      if latest_ok:
        result.append(latest_ok)
    return result

  def _scan_runs(run_type: str, filter: str, remove_all: bool = False) -> list[WorkflowRun]:
    runs = WorkflowRun.select(repo, filter, noninteractive=True)
    if not runs:
      log.warning("[{}] no {} detected", repo, run_type)
    else:
      log.info("[{}] {} {} runs detected", repo, run_type, len(runs))
      for i, run in enumerate(runs):
        log.info("[{}] {}. {}", repo, i, run)
      if not remove_all:
        preserved.extend(_pick_preserved(runs))
    for run in runs:
      if run in preserved:
        continue
      if run.incomplete:
        log.warning("[{}] not removing incomplete run: {}", repo, run)
        continue
      removed.append(run)
    return runs

  _ = _scan_runs("nighlty releases", "'release !cleanup '[nightly, ")
  _ = _scan_runs(
    "nighlty release cleanup jobs",
    "'release 'cleanup '[nightly, ",
    remove_all=True,
  )

  if preserved:
    log.info("[{}] {} candidates for ARCHIVAL", repo, len(preserved))
    if not script_noninteractive():
      removed.extend(WorkflowRun.select(repo, runs=preserved, prompt="don't archive"))
  else:
    log.warning("[{}] no candidates for ARCHIVAL", repo)

  if removed:
    log.warning("[{}] {} candidates for DELETION", repo, len(removed))
    actually_removed = WorkflowRun.delete(repo, noop=noop, runs=removed)
  else:
    log.info("[{}] no candidates for DELETION", repo)
    actually_removed = []

  preserved.extend(run for run in removed if run not in actually_removed)

  if not actually_removed:
    log.info("[{}] no runs deleted", repo)
  else:
    log.warning("[{}] {} runs DELETED", repo, len(actually_removed))

  if not preserved:
    log.warning("[{}] no runs archived", repo)
  else:
    log.warning("[{}] {} runs ARCHIVED", repo, len(preserved))

  return WorkflowRun.action_result(removed, preserved)
