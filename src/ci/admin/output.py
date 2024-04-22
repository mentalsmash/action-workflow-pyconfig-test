import subprocess

###############################################################################
# Global hooks to produce output to stdout, and possibly tabulate it
###############################################################################
TabulateEnabled = True
TabulateOutput = None
TabulateColumns = []


def tabulate_columns(*columns: list[str]) -> None:
  global TabulateColumns
  TabulateColumns.clear()
  TabulateColumns.extend(columns)


def output(*fields):
  global TabulateOutput
  global TabulateEnabled
  if TabulateEnabled and TabulateOutput is None:
    try:
      TabulateOutput = subprocess.Popen(
        ["column", "-t", "-s", "\t"],
        stdin=subprocess.PIPE,
        stderr=subprocess.PIPE,
      )
      if TabulateColumns:
        columns = "\t".join(col.upper().replace("_", " ") for col in TabulateColumns)
        TabulateOutput.stdin.write(columns.encode())
        TabulateOutput.stdin.write("\n".encode())
    except Exception:
      # The process failed, assume column is not available
      # and don't try to tabulate again
      TabulateEnabled = False

  line = "\t".join(fields).strip()
  if not TabulateOutput:
    print(line)
  else:
    TabulateOutput.stdin.write(line.encode())
    TabulateOutput.stdin.write("\n".encode())