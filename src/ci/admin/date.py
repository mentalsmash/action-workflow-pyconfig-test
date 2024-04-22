from datetime import datetime, timezone

###############################################################################
# Parse/print dates in the format used by the GH API
###############################################################################
GitHubDateFormat = "%Y-%m-%dT%H:%M:%SZ"

def github_date_parse(date: str) -> datetime:
  parsed = datetime.strptime(date, GitHubDateFormat)
  return parsed.replace(tzinfo=timezone.utc)

def github_date_str(date: datetime) -> str:
  result = date.replace(tzinfo=timezone.utc)
  return result.strftime(GitHubDateFormat)
