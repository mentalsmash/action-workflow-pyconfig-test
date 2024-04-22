
from .workflow_run import WorkflowRun
from .log import log
from .globals import script_noninteractive
from .pr_runs import pr_runs

###############################################################################
# Perform cleanup procedures after on a closed Pull Request
###############################################################################
def pr_closed(
  repo: str, pr_no: int, merged: bool, noop: bool = False
) -> list[tuple[bool, WorkflowRun]]:
  all_runs = pr_runs(repo, pr_no, noninteractive=True)

  if not all_runs:
    log.warning("[{}][PR #{}] PR was closed without any workflow run", repo, pr_no)
    return []

  log.info("[{}][PR #{}] {} runs detected", repo, pr_no, len(all_runs))
  for i, run in enumerate(all_runs):
    log.info(" {}. {}", i + 1, run)

  if not merged:
    log.warning(
      "[{}][PR #{}] deleting all {} runs for unmerged PR",
      pr_no,
      repo,
      len(all_runs),
    )
    removed = WorkflowRun.delete(repo, noop=noop, runs=all_runs)
    preserved = [run for run in all_runs if run not in removed]
    return WorkflowRun.action_result(removed, preserved)

  log.activity("[{}][PR #{}] listing failed and skipped runs", repo, pr_no)
  removed = list(pr_runs(repo, pr_no, "'FAIL | 'SKIP | 'NULL", runs=all_runs, noninteractive=True))
  if not removed:
    log.info("[{}][PR #{}] no failed nor skipped runs", repo, pr_no)
  else:
    log.info("[{}][PR #{}] {} failed or skipped runs", repo, pr_no, len(removed))

  preserved = []

  log.activity("[{}][PR #{}] listing good 'basic validation' runs", repo, pr_no)
  basic_validation_runs = list(
    pr_runs(repo, pr_no, "'GOOD", "updated", runs=all_runs, noninteractive=True)
  )
  if not basic_validation_runs:
    log.warning("[{}][PR #{}] no good 'basic validation' run", repo, pr_no)
  else:
    basic_validation_delete = basic_validation_runs[:-1]
    log.info(
      "[{}][PR #{}] {} good 'basic validation' runs to delete",
      repo,
      pr_no,
      len(basic_validation_delete),
    )
    for i, run in enumerate(basic_validation_delete):
      log.info(" {}. {}", i, run)
    removed.extend(basic_validation_delete)
    basic_validation_run = basic_validation_runs[-1]
    log.info("[{}][PR #{}] 'basic validation' run: {}", repo, pr_no, basic_validation_run)
    preserved.append(basic_validation_run)

  log.activity("[{}][PR #{}] listing good 'full validation' runs", repo, pr_no)
  full_validation_runs = list(
    pr_runs(
      repo,
      pr_no,
      "'GOOD",
      "reviewed, 'approved",
      runs=all_runs,
      noninteractive=True,
    )
  )
  if not full_validation_runs:
    log.error("[{}][PR #{}] no good 'full validation' run!", repo, pr_no)
    raise RuntimeError(f"no good 'full validation' run for PR #{pr_no} of {repo}")
  else:
    full_validation_delete = full_validation_runs[:-1]
    log.info(
      "[{}][PR #{}] {} good 'full validation' runs to delete",
      repo,
      pr_no,
      len(full_validation_delete),
    )
    for i, run in enumerate(full_validation_delete):
      log.info(" {}. {}", i, run)
    removed.extend(full_validation_delete)
    full_validation_run = full_validation_runs[-1]
    log.info("[{}][PR #{}] 'full validation' run: {}", repo, pr_no, full_validation_run)
    preserved.append(full_validation_run)

  if preserved:
    log.info("[{}][PR #{}] {} candidates for ARCHIVAL", repo, pr_no, len(preserved))
    if not script_noninteractive():
      removed.extend(WorkflowRun.select(repo, runs=preserved, prompt="don't archive"))
  else:
    log.warning("[{}][PR #{}] no runs selected for ARCHIVAL", repo, pr_no)

  if removed:
    log.info("[{}][PR #{}] {} candidates for DELETION", repo, pr_no, len(removed))
    actually_removed = WorkflowRun.delete(repo, noop=noop, runs=removed)
  else:
    actually_removed = []
    log.info("[{}][PR #{}] no runs selected for DELETION", repo, pr_no)

  preserved.extend(run for run in removed if run not in actually_removed)

  if not actually_removed:
    log.info("[{}][PR #{}] no runs deleted", repo, pr_no)
  else:
    log.warning("[{}][PR #{}] {} runs DELETED", repo, pr_no, len(actually_removed))

  if not preserved:
    log.warning("[{}][PR #{}] no runs archived", repo, pr_no)
  else:
    log.warning("[{}][PR #{}] {} runs ARCHIVED", repo, pr_no, len(preserved))

  return WorkflowRun.action_result(actually_removed, preserved)
