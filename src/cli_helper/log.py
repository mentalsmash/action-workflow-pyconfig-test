import sys
import os
from typing import Protocol, NamedTuple

###############################################################################
# mini logger API
###############################################################################
ColorEnabled = sys.stderr.isatty() and not os.environ.get("NO_COLORS", False)
try:
  import termcolor
except Exception:
  ColorEnabled = False


def _log_msg(lvl, fmt, *args, **print_args) -> None:
  print_args.setdefault("file", sys.stderr)
  line = fmt.format(*args) if args else fmt
  line = f"[{lvl}]" + ("" if line.startswith("[") else " ") + line
  if ColorEnabled:
    color = {
      "D": "magenta",
      "A": "cyan",
      "I": "green",
      "W": "yellow",
      "E": "red",
    }[lvl]
    line = termcolor.colored(line, color)
  print(line, **print_args)


def _log_debug(*args, **print_args) -> None:
  return _log_msg("D", *args, **print_args)


def _log_activity(*args, **print_args) -> None:
  return _log_msg("A", *args, **print_args)


def _log_info(*args, **print_args) -> None:
  return _log_msg("I", *args, **print_args)


def _log_error(*args, **print_args) -> None:
  return _log_msg("E", *args, **print_args)


def _log_warning(*args, **print_args) -> None:
  return _log_msg("W", *args, **print_args)


def _log_command(cmd: list[str], shell: bool = False, check: bool = False, **print_args) -> None:
  if shell:
    cmd = ["sh", f"-{'e' if check else ''}c", *cmd]
  _log_debug("+ " + " ".join(["{}"] * len(cmd)), *(map(str, cmd)), **print_args)


class LogFunction(Protocol):
  def __call__(self, *args, **print_args) -> None:
    pass


class LogCommandFunction(Protocol):
  def __call__(
    self, cmd: list[str], shell: bool = False, check: bool = False, **print_args
  ) -> None:
    pass


class Logger(NamedTuple):
  debug: LogFunction
  activity: LogFunction
  info: LogFunction
  warning: LogFunction
  error: LogFunction
  command: LogCommandFunction


log = Logger(_log_debug, _log_activity, _log_info, _log_warning, _log_error, _log_command)

