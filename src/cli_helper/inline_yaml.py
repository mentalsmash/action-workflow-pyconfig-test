from pathlib import Path
import yaml

def inline_yaml_load(val: str | Path) -> dict:
  # Try to interpret the string as a Path
  yml_val = val
  args_file = Path(val)
  if args_file.is_file():
    yml_val = args_file.read_text()
  # Interpret the string as inline YAML
  if not isinstance(yml_val, str):
    raise ValueError("failed to load yaml", val)
  return yaml.safe_load(yml_val)
