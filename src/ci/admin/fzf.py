import subprocess

from .globals import script_noninteractive
from cli_helper.log import log

###############################################################################
# Filter a list using fzf
###############################################################################
def fzf_filter(
  filter: str | None = None,
  inputs: list | None = None,
  keep_stdin_open: bool = False,
  prompt: str | None = None,
  noninteractive: bool = False,
) -> subprocess.Popen:
  noninteractive = noninteractive or script_noninteractive()
  if noninteractive:
    filter_arg = "--filter"
  else:
    filter_arg = "--query"

  if filter is None:
    filter = ""

  if prompt is None:
    prompt = ""
  # if prompt[-2:] != "> ":
  prompt += " (TAB: select, ESC: none)> "

  fzf_cmd = [
    "fzf",
    "-0",
    "--tac",
    "--no-sort",
    "--multi",
    "--prompt",
    prompt,
    filter_arg,
    filter,
  ]
  log.command(fzf_cmd)
  fzf = subprocess.Popen(fzf_cmd, stdout=subprocess.PIPE, stdin=subprocess.PIPE)
  if inputs:
    for run in inputs:
      line = str(run).strip()
      fzf.stdin.write(line.encode())
      fzf.stdin.write("\n".encode())
    if not keep_stdin_open:
      fzf.stdin.close()
  return fzf
