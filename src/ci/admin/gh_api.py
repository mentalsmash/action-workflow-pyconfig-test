import json
import subprocess
from itertools import chain

from cli_helper.log import log

# GitHub API documentation: https://docs.github.com/en/rest/reference/packages
GitHubApiAccept = "application/vnd.github.v3+json"
# https://docs.github.com/en/rest/overview/api-versions?apiVersion=2022-11-28
GitHubApiVersion = "2022-11-28"

###############################################################################
# Make a GH API call, filter the result with jq, and parse the resulting JSON
###############################################################################
def gh_api(
  url: str,
  jq_filter: str | None = None,
  default: object = None,
  noop: bool = False,
  method: str = "GET",
) -> dict | list | None:
  gh_cmd = [
    "gh", "api", "--paginate",
    "-H", f"Accept: {GitHubApiAccept}",
    "-H", f"X-GitHub-Api-Version: {GitHubApiVersion}",
    *(["-X", method] if method else []),
    url
  ]
  if jq_filter:
    gh_cmd.extend(["--jq", jq_filter])

  log.command(gh_cmd)
  if noop and method != "GET":
    return default

  gh_process = subprocess.Popen(gh_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

  if jq_filter:
    jq_result = subprocess.run(["jq", "-s"], check=True, stdin=gh_process.stdout, stdout=subprocess.PIPE)
  
  gh_stdout, gh_stderr = gh_process.communicate()

  if gh_process.returncode != 0:
    raise RuntimeError("gh api call failed", gh_cmd,
      gh_stdout, gh_stderr)

  if jq_filter:
    stdout = jq_result.stdout
  else:
    stdout = gh_stdout

  stdout = stdout.decode().strip() if stdout else ""

  if not stdout:
    return default

  try:
    result = json.loads(stdout)
    if jq_filter and result and isinstance(next(iter(result)), list):
      # Flatten slurped arrays
      result = list(chain.from_iterable(result))
    return result
  except Exception as e:
    log.error("failed to parse result as JSON")
    log.exception(e)
    log.error("JSON parse input:\n{}", stdout)
    return default
