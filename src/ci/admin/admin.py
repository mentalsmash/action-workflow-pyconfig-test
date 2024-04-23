import os
import sys
import argparse
from datetime import timedelta
from pathlib import Path
import shlex
import subprocess

from .globals import ScriptNoninteractiveRequired, script_noninteractive, RepoDir, ScriptsDir
from .output import tabulate_columns, output, TabulateOutput
from .workflow_run import WorkflowRun
from .package import Package
from .package_version import PackageVersion
from .pr_closed import pr_closed
from .pr_runs import pr_runs
from .nightly_cleanup import nightly_cleanup
from cli_helper.log import log

class Admin:
  ###############################################################################
  # Helper to run a command from an action/workflow
  ###############################################################################
  @classmethod
  def run(cls, args: str, image: str | None = None, cwd: str | None = None, token: str | None = None, capture_output: bool=False) -> str | None:
    cwd = Path(cwd) if cwd else Path.cwd()
    args = [
      shlex.quote(arg)
      for arg in args.strip().splitlines() if arg
      for arg in [arg.strip()] if arg
    ]
    if not token:
      token = os.environ.get("GH_TOKEN", "")
      if not token:
        log.warning("no GH_TOKEN found")
    cmd_prefix = []
    admin_script = ScriptsDir / "ci-admin"
    if image:
      cmd_prefix = [
        "docker", "run", "--rm",
        "-v", f"{RepoDir}:/action",
        "-v", f"{cwd}:/workspace",
        "-e", f"GH_TOKEN={token}",
        "-w", "/workspace",
        image,
      ]
      admin_script = f"/action/{admin_script.relative_to(RepoDir)}"

    cmd = [*cmd_prefix, admin_script, *args]
    log.command(cmd)
    result = subprocess.run(cmd, check=True, **({
      "stdout": subprocess.PIPE
    } if capture_output else {}))
    if result.stdout and capture_output:
      return result.stdout.decode().strip()
    return None


  ###############################################################################
  # Script main()
  ###############################################################################
  @classmethod
  def main(cls) -> None:
    parser = cls.define_parser()
    args = parser.parse_args()

    if args.raw:
      global TabulateEnabled
      TabulateEnabled = False

    if args.interactive:
      if ScriptNoninteractiveRequired:
        raise RuntimeError("interactive requires a terminal")
      script_noninteractive(False)

    if args.current:
      WorkflowRun.Current = args.current

    if not args.action:
      log.error("no action specified")
      parser.print_help()
      sys.exit(1)

    try:
      if args.action == "pr-closed":
        cls.pr_closed(
          repo=args.repository,
          pr_no=args.number,
          merged=args.merged,
          noop=args.noop,
        )
      elif args.action == "pr-runs":
        cls.pr_runs(repo=args.repository, pr_no=args.number)
      elif args.action == "select-runs":
        cls.select_runs(repo=args.repository, filter=args.filter, input=args.input)
      elif args.action == "delete-runs":
        cls.delete_runs(
          repo=args.repository,
          filter=args.filter,
          noop=args.noop,
          input=args.input)
      elif args.action == "select-packages":
        cls.select_packages(org=args.org, filter=args.filter)
      elif args.action == "select-versions":
        cls.select_versions(package=args.package, org=args.org, filter=args.filter)
      elif args.action == "delete-versions":
        cls.delete_versions(
          package=args.package,
          org=args.org,
          filter=args.filter,
          noop=args.noop,
          if_package_exists=args.if_package_exists)
      elif args.action == "prune-versions":
        if args.prunable == "-":
          def _input():
            return sys.stdin.readlines()
        else:
          def _input():
            return Path(args.prunable).read_text().splitlines()
        
        def _prunable():
         for line in [
            line
            for line in _input()
            for line in [line.strip()]
            if line
          ]:
           yield line
        
        def _prune(filter: str) -> None:
          # cls.delete_versions(org=org,)
          for version in PackageVersion.delete(
            package=args.package,
            org=args.org,
            filter=filter,
            noop=args.noop,
          ):
            output(str(version))

        max_arg_len = 131072

        tabulate_columns(*PackageVersion._fields)
        prunable = _prunable()
        batch = ""
        next_line = next(prunable, None)
        while next_line is not None:
          line_token = "".join(("'", next_line))
          if len(batch) + len(next_line) > max_arg_len:
            _prune(batch)
            batch = ""
          batch = (
            " | ".join((batch, line_token))
            if batch else line_token
          )
          next_line = next(prunable, None)
        if batch:
          _prune(batch)

      elif args.action == "prune-versions-untagged":
        cls.prune_versions_untagged(
          package=args.package,
          org=args.org,
          prunable=prunable,
          noop=args.noop)
      elif args.action == "nightly-cleanup":
        cls.nightly_cleanup(repo=args.repository, noop=args.noop)
      else:
        raise RuntimeError("action not implemented", args.action)
    finally:
      if TabulateOutput:
        TabulateOutput.stdin.close()


  ###############################################################################
  # Command-line arguments parser
  ###############################################################################
  @classmethod
  def define_parser(cls) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser("ci-admin")
    parser.set_defaults(action=None)

    parser.add_argument(
      "-n",
      "--noop",
      help="Don't make any changes if possible.",
      default=False,
      action="store_true",
    )

    parser.add_argument(
      "-R",
      "--raw",
      help="Don't process output (e.g. tabulate)",
      default=False,
      action="store_true",
    )

    parser.add_argument(
      "-i",
      "--interactive",
      help="Run in interactive mode.",
      default=False,
      action="store_true",
    )

    parser.add_argument("-c", "--current", help="Calling workflow id.", default=None)

    subparsers = parser.add_subparsers(dest="action")

    parser_pr_closed = subparsers.add_parser(
      "pr-closed", help="Clean up workflow runs for a closed PR."
    )
    parser_pr_closed.add_argument(
      "-r",
      "--repository",
      help="Target GitHub repository (owner/repo).",
      required=True,
    )
    parser_pr_closed.add_argument("-N", "--number", help="PR number.", required=True, type=int)
    parser_pr_closed.add_argument(
      "-m", "--merged", help="The PR was merged.", default=False, action="store_true"
    )

    parser_pr_ls_runs = subparsers.add_parser("pr-runs", help="List existing workflow runs for a PR.")
    parser_pr_ls_runs.add_argument(
      "-r",
      "--repository",
      help="Target GitHub repository (owner/repo).",
      required=True,
    )
    parser_pr_ls_runs.add_argument("-N", "--number", help="PR number.", required=True, type=int)

    parser_ls_runs = subparsers.add_parser(
      "select-runs",
      help="List all workflow runs, or only a subset matching an fzf filter.",
    )
    parser_ls_runs.add_argument(
      "-r",
      "--repository",
      help="Target GitHub repository (owner/repo).",
      required=True,
    )
    parser_ls_runs.add_argument(
      "-f",
      "--filter",
      help="Custom zfz filter to run in unattended mode.",
      default=None,
    )
    parser_ls_runs.add_argument(
      "-i",
      "--input",
      help="Read entries from the specified file instead of querying GitHub. "
      "Use - to read from stdin",
      default=None,
    )

    parser_delete_runs = subparsers.add_parser(
      "delete-runs",
      help="Delete all workflow runs, or a subset matching an fzf filter.",
    )
    parser_delete_runs.add_argument(
      "-r",
      "--repository",
      help="Target GitHub repository (owner/repo).",
      required=True,
    )
    parser_delete_runs.add_argument(
      "-f",
      "--filter",
      help="Custom zfz filter to run in unattended mode.",
      default=None,
    )
    parser_delete_runs.add_argument(
      "-i",
      "--input",
      help="Read entries from the specified file instead of querying GitHub. "
      "Use - to read from stdin",
      default=None,
    )

    parser_ls_pkgs = subparsers.add_parser(
      "select-packages",
      help="List packages for an organization (or the current user).",
    )
    parser_ls_pkgs.add_argument("-o", "--org", help="Target GitHub organization.", default=None)
    parser_ls_pkgs.add_argument(
      "-f",
      "--filter",
      help="Custom zfz filter to run in unattended mode.",
      default=None,
    )

    parser_ls_versions = subparsers.add_parser(
      "select-versions",
      help="List versions for a package owned by an organization (or the current user).",
    )
    parser_ls_versions.add_argument("-p", "--package", help="Target package.", required=True)
    parser_ls_versions.add_argument("-o", "--org", help="Target GitHub organization.", default=None)
    parser_ls_versions.add_argument(
      "-f",
      "--filter",
      help="Custom zfz filter to run in unattended mode.",
      default=None,
    )

    parser_delete_versions = subparsers.add_parser(
      "delete-versions",
      help="Delete all versions of a package, or only a subset matching an fzf filter.",
    )
    parser_delete_versions.add_argument("-p", "--package", help="Target package.", required=True)
    parser_delete_versions.add_argument(
      "-o", "--org", help="Target GitHub organization.", default=None
    )
    parser_delete_versions.add_argument(
      "-f",
      "--filter",
      help="Custom zfz filter to run in unattended mode.",
      default=None,
    )
    parser_delete_versions.add_argument(
      "--if-package-exists",
      help="Don't return an error if the package doesn't exist",
      default=False,
      action="store_true")

    parser_prune_versions = subparsers.add_parser(
      "prune-versions",
      help="Delete all untagged versions of a package older than certain amount of days.",
    )
    parser_prune_versions.add_argument("-p", "--package", help="Target package.", required=True)
    parser_prune_versions.add_argument(
      "-o", "--org", help="Target GitHub organization.", default=None
    )
    # parser_prune_versions.add_argument(
    #   "-a",
    #   "--max-age",
    #   help='Maximum number of days since the last update to consider the image "prunable" (floating point number).',
    #   default=None,
    #   type=float,
    # )
    parser_prune_versions.add_argument("-P", "--prunable",
      help="List of prunable versions or - to read it from stdin",
      required=True)

    parser_nightly_cleanup = subparsers.add_parser(
      "nightly-cleanup", help="Clean up workflow runs for nightly releases"
    )
    parser_nightly_cleanup.add_argument(
      "-r",
      "--repository",
      help="Target GitHub repository (owner/repo).",
      required=True,
    )

    return parser


  @classmethod
  def pr_closed(cls, repo, pr_no, merged, noop) -> None:
    result = pr_closed(
      repo=repo,
      pr_no=pr_no,
      merged=merged,
      noop=noop,
    )
    tabulate_columns("action", *WorkflowRun._fields)
    for removed, run in result:
      output("DEL" if removed else "KEEP", str(run))

  @classmethod
  def pr_runs(cls, repo, pr_no, noop) -> None:
    tabulate_columns(*WorkflowRun._fields)
    for run in pr_runs(repo=repo, pr_no=pr_no):
      output(str(run))

  @classmethod
  def select_runs(cls, repo, filter, input) -> None:
    tabulate_columns(*WorkflowRun._fields)
    for run in WorkflowRun.select(repo=repo, filter=filter, input=input):
      output(str(run))

  @classmethod
  def delete_runs(cls, repo, filter, input, noop) -> None:
    tabulate_columns(*WorkflowRun._fields)
    for run in WorkflowRun.delete(
      repo=repo,
      filter=filter,
      noop=noop,
      input=input,
    ):
      output(str(run))

  @classmethod
  def select_packages(cls, org, filter) -> None:
    tabulate_columns(*Package._fields)
    for pkg in Package.select(org=org, filter=filter):
      output(str(pkg))

  @classmethod
  def select_versions(cls, org, package, filter) -> None:
    tabulate_columns(*PackageVersion._fields)
    for version in PackageVersion.select(package=package, org=org, filter=filter):
      output(str(version))

  @classmethod
  def delete_versions(cls, org, package, filter, noop, if_package_exists) -> None:
    tabulate_columns(*PackageVersion._fields)
    for run in PackageVersion.delete(
      package=package,
      org=org,
      filter=filter,
      noop=noop,
      if_package_exists=if_package_exists
    ):
      output(str(run))

  @classmethod
  def prune_versions_untagged(cls, org, package, max_age, noop) -> None:
    max_age = timedelta(days=max_age) if max_age else None
    tabulate_columns(*PackageVersion._fields)
    for run in PackageVersion.prune_untagged(
      package=package,
      org=org,
      max_age=max_age,
      noop=noop,
    ):
      output(str(run))

  @classmethod
  def nightly_cleanup(cls, repo, noop) -> None:
    tabulate_columns("action", *WorkflowRun._fields)
    for removed, run in nightly_cleanup(repo=repo, noop=noop):
      output("DEL" if removed else "KEEP", str(run))

