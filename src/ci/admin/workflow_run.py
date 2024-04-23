
import sys
import subprocess
from pathlib import Path
from typing import NamedTuple, TextIO
from datetime import datetime
from functools import partial

from cli_helper.log import log
from .fzf import fzf_filter
from .data_object import DataObject, parse
from .gh_api import gh_api

###############################################################################
# GitHub Workflow Run data object (parsed from query result)
###############################################################################
class WorkflowRun(NamedTuple):
  repo: str
  head_repo: str
  id: int
  created_at: datetime
  updated_at: datetime
  event: str
  status: str
  outcome: str
  name: str

  Current = ""
  DatetimeFields = [3, 4]
  SelectQuery = """\
def symbol:
  sub(""; "")? // "NULL" |
  sub("skipped"; "SKIP") |
  sub("success"; "GOOD") |
  sub("startup_failure"; "FAIL") |
  sub("cancelled"; "FAIL") |
  sub("failure"; "FAIL");

[ .workflow_runs[]
  | [
      .repository.full_name,
      .head_repository.full_name,
      .id,
      .created_at,
      .updated_at,
      .event,
      .status,
      (.conclusion | symbol),
      .name
    ] 
  ]
"""

  def __str__(self) -> str:
    return DataObject.str(self)

  @property
  def incomplete(self) -> bool:
    return self.status in [
      "in_progress",
      "queued",
      "requested",
      "waiting",
      "pending",
    ]

  ###############################################################################
  #
  ###############################################################################
  def cancel(self, noop: bool = False) -> None:
    url = f"/repos/{self.repo}/actions/runs/{self.id}/cancel"
    gh_api(url, method="POST", noop=noop)

  ###############################################################################
  # Query the list of workflow runs from a repository.
  # If no filter is specified, present the user with `fzf` to select targets.
  # Otherwise, run in unattended mode with the provided filter.
  # By default, the function will query GitHub and parse the result with jq.
  # Optionally, the list of runs can be read from a pregenerated file (or stdin),
  # or it can be passed explicitly with the `runs` parameter.
  ###############################################################################
  @classmethod
  def select(
    cls,
    repo: str,
    filter: str | None = None,
    input: str | None = None,
    runs: list["WorkflowRun"] | None = None,
    prompt: str | None = None,
    noninteractive: bool = False,
    skip_last: bool = False
  ) -> list["WorkflowRun"]:
    def _read_and_parse_runs(input_stream: TextIO) -> list[WorkflowRun]:
      return [
        run
        for line in input_stream.readlines()
        for sline in [line.decode().strip()]
        if sline
        for run in [parse(cls, sline)]
        if run and run.id != cls.Current
      ]
    if runs:
      target_runs = runs
    elif input == "-":
      target_runs = _read_and_parse_runs(sys.stdin)
    elif input:
      input_file = Path(input)
      with input_file.open("r") as istream:
        target_runs = _read_and_parse_runs(istream)
    else:
      run_entries = gh_api(
        url=f"/repos/{repo}/actions/runs",
        jq_filter=WorkflowRun.SelectQuery,
        default=[])
      target_runs = [
        DataObject.build(cls, *entry) for entry in run_entries if entry[2] != cls.Current
      ]
    if prompt is None:
      prompt = "available runs"
    
    if not target_runs:
      log.warning("[{}] no workflow runs detected", repo)
      return []

    sorted_runs = partial(sorted, key=lambda r: r.created_at)
    fzf = fzf_filter(
      filter=filter,
      inputs=sorted_runs(target_runs),
      prompt=prompt,
      noninteractive=noninteractive,
    )
    result = sorted_runs(_read_and_parse_runs(fzf.stdout))
    if skip_last and result:
      log.warning("[{}] skipping most recent run: {}", repo, result[-1])
      result = result[:-1]
    return result

  ###############################################################################
  # Delete all (or a filtered subset) of the workflow runs from a repository,
  ###############################################################################
  @classmethod
  def delete(
    cls,
    repo: str,
    filter: str | None = None,
    noop: bool = False,
    input: str | None = None,
    runs: list["WorkflowRun"] | None = None,
    prompt: str | None = None,
    keep_last: bool = False,
  ) -> list["WorkflowRun"]:
    def _delete_run(run: WorkflowRun):
      if run.outcome == "NULL":
        run.cancel(noop=noop)
      delete_cmd = [
        "gh",
        "api",
        "-X",
        "DELETE",
        f"/repos/{repo}/actions/runs/{run.id}",
      ]
      log.command(delete_cmd, check=True)
      if not noop:
        subprocess.run(delete_cmd, check=True)

    deleted = []
    if prompt is None:
      prompt = "runs to delete"

    for run in cls.select(repo, filter, input, runs, prompt=prompt, skip_last=keep_last):
      _delete_run(run)
      deleted.append(run)
    if noop:
      log.warning("[{}] {} runs selected but not actually deleted", repo, len(deleted))
    else:
      log.warning("[{}] {} runs DELETED", repo, len(deleted))
    return deleted

  ###############################################################################
  # Combine the result arrays of an action which deletes/keeps workflow runs
  ###############################################################################
  @classmethod
  def action_result(cls,
    removed: list["WorkflowRun"], preserved: list["WorkflowRun"]
  ) -> list[tuple[bool, "WorkflowRun"]]:
    result = [*((True, run) for run in removed), *((False, run) for run in preserved)]
    return sorted(result, key=lambda v: v[1].created_at)
