import sys
from pathlib import Path


RepoDir = Path(__file__).parent.parent.parent.parent
ScriptsDir = RepoDir / "scripts"

ScriptNoninteractiveRequired = not sys.stdin.isatty() or not sys.stdout.isatty()
_ScriptNoninteractive = True

def script_noninteractive(val: bool | None = None) -> bool:
  global _ScriptNoninteractive
  if val is not None:
    _ScriptNoninteractive = val
  return _ScriptNoninteractive
