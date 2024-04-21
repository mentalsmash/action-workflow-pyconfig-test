###############################################################################
# Copyright 2020-2024 Andrea Sorbini
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
###############################################################################
import yaml
import json
import os
import subprocess
from pathlib import Path
from collections import namedtuple
from typing import NamedTuple
import importlib


###############################################################################
#
###############################################################################
def dict_to_tuple(key: str, val: dict) -> NamedTuple:
  fields = {}
  for k, v in val.items():
    if k.startswith("_"):
      # field unsupported by namedtuple
      continue
    if isinstance(v, dict):
      v = dict_to_tuple(k, v)
    k = k.replace("-", "_").replace("/", "_")
    fields[k] = v

  keys = list(fields.keys())
  if not keys:
    return tuple()

  val_cls = namedtuple(key, keys)
  return val_cls(**fields)


###############################################################################
#
###############################################################################
def tuple_to_dict(val: NamedTuple) -> dict:
  result = val._asdict()
  for k in val._fields:
    v = getattr(val, k)
    if isinstance(v, tuple):
      v = tuple_to_dict(v)
    result[k] = v
  return result


###############################################################################
#
###############################################################################
def _select_attribute(ctx: tuple | dict, selector: str) -> str:
  def _getattr(obj: tuple | dict, k: str):
    if isinstance(obj, dict):
      return obj[k]
    else:
      return getattr(obj, k)

  def _lookup_recur(current: tuple | dict, selector_parts: list[str]) -> str:
    selected = _getattr(current, selector_parts[0])
    if len(selector_parts) == 1:
      return selected
    return _lookup_recur(selected, selector_parts[1:])

  selector_parts = selector.split(".")
  if not selector_parts:
    raise RuntimeError("a non-empty selector is required")
  return _lookup_recur(ctx, selector_parts)


###############################################################################
#
###############################################################################
def merge_dicts(result: dict, defaults: dict) -> dict:
  merged = {}
  for k in {*result.keys(), *defaults.keys()}:
    res_v = result.get(k)
    def_v = defaults.get(k)
    if def_v is None and res_v is None:
      continue
    elif def_v is None:
      v = res_v
    elif res_v is None:
      v = def_v
    elif isinstance(def_v, dict):
      assert isinstance(res_v, dict)
      v = merge_dicts(res_v, def_v)
    else:
      v = res_v
    merged[k] = v
  return merged


###############################################################################
#
###############################################################################
def sha_short(clone_dir: Path | str) -> str:
  return (
    subprocess.run(
      ["git", "rev-parse", "--short", "HEAD"],
      cwd=clone_dir,
      stdout=subprocess.PIPE,
    )
    .stdout.decode()
    .strip()
  )


###############################################################################
#
###############################################################################
def extract_registries(local_org: str, tags: list[str]) -> set[str]:
  def _registry_from_tag(image_tag: str) -> str:
    if image_tag.startswith(f"ghcr.io/{local_org}/"):
      return "github"
    elif image_tag.startswith(f"{local_org}/"):
      return "dockerhub"
    else:
      return None

  registries = set()
  for rel_tag in tags:
    registry = _registry_from_tag(rel_tag)
    if not registry:
      continue
    registries.add(registry)
  return registries


###############################################################################
#
###############################################################################
def write_output(
  vars: dict[str, bool | str | int | None] | None = None,
  export_env: list[str] | None = None,
):
  """Helper function to write variables to GITHUB_OUTPUT.

  Optionally, re-export environment variables so that they may be
  accessed from jobs.<job_id>.with.<with_id>, and other contexts
  where the env context is not available
  """

  def _output(var: str, val: bool | str | int | None):
    assert val is None or isinstance(
      val, (bool, str, int)
    ), f"unsupported output value type: {var} = {val.__class__}"
    if val is None:
      val = ""
    elif isinstance(val, bool):
      # Normalize booleans to non-empty/empty strings
      # Use lowercase variable name for easier debugging
      val = var.lower() if val else ""
    elif not isinstance(val, str):
      val = str(val)
    print(f"{var} = {repr(val)}")
    if "\n" not in val:
      output.write(var)
      output.write("=")
      if val:
        output.write(val)
      output.write("\n")
    else:
      output.write(f"{var}<<EOF" "\n")
      output.write(val)
      output.write("\n")
      output.write("EOF\n")

  print("::group::Step Outputs")
  github_output = Path(os.environ["GITHUB_OUTPUT"])
  with github_output.open("a") as output:
    for var in export_env or []:
      val = os.environ.get(var, "")
      _output(var, val)
    for var, val in (vars or {}).items():
      _output(var, val)
  print("::endgroup::")


###############################################################################
#
###############################################################################
def load_file_as_module(file: Path, module_name: str | None = None):
    # Load test case as a module
    # (see: https://stackoverflow.com/a/67692)
    import importlib.util
    import sys

    if module_name is None:
      module_name = file.stem

    spec = importlib.util.spec_from_file_location(module_name, str(file))
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


###############################################################################
#
###############################################################################
def configuration(
  clone_dir: Path,
  config_dir: Path,
  github: str,
  inputs: str | None = None,
  as_tuple: bool = True,
  workflow: str | None = None
) -> tuple[tuple, tuple, tuple | dict, object | None]:

  def _json_load(val: str):
    # Make sure the string doesn't contain literal or escaped newline
    val = val.replace("\n", "")
    val = val.replace("\\n", "")
    return json.loads(val)

  print("::group::Clone Directory")
  print(str(config_dir))
  print("::endgroup::")

  github_dict = _json_load(github.strip())
  github = dict_to_tuple("github", github_dict)
  print("::group::GitHub Context")
  print(yaml.safe_dump(github_dict))
  print("::endgroup::")

  inputs = (inputs or "").strip()
  if inputs:
    inputs_dict = _json_load(inputs.strip())
    inputs = dict_to_tuple("inputs", inputs_dict)
    print("::group::Inputs")
    print(yaml.safe_dump(tuple_to_dict(inputs)))
    print("::endgroup::")

  cfg_file = config_dir / "settings.yml"
  if cfg_file.exists():
    cfg_dict = yaml.safe_load(cfg_file.read_text())
  else:
    cfg_dict = {}
  print("::group::Static Settings (settings.yml)")
  print(yaml.safe_dump(cfg_dict))
  print("::endgroup::")

  cfg_mod_py = config_dir / "settings.py"
  if cfg_mod_py.exists():
    cfg_mod = load_file_as_module(cfg_mod_py)
    derived_cfg = cfg_mod.settings(clone_dir=clone_dir, cfg=dict_to_tuple("settings", cfg_dict), github=github)
    print("::group::Dynamic Settings")
    print(yaml.safe_dump(derived_cfg))
    print("::endgroup::")
  else:
    derived_cfg = {}

  cfg_dict = merge_dicts(derived_cfg, cfg_dict)
  cfg_dict = merge_dicts(
    cfg_dict,
    {
      "build": {
        "clone_dir": str(clone_dir),
      },
    },
  )

  print("::group::Project Settings")
  print(yaml.safe_dump(cfg_dict))
  print("::endgroup::")

  project_cfg = dict_to_tuple("settings", cfg_dict)

  if workflow:
    workflow_mod_py = config_dir / "workflows" / f"{workflow}.py"
    workflow_mod = load_file_as_module(workflow_mod_py, workflow)
    workflow_cfg = workflow_mod.configure(
      clone_dir=clone_dir, cfg=project_cfg, github=github, inputs=inputs
    )
    print(f"::group::Workflow {workflow} Settings")
    print(yaml.safe_dump(workflow_cfg))
    print("::endgroup::")

    cfg_dict = merge_dicts(workflow_cfg, cfg_dict)
    print("::group::Final Settings")
    print(yaml.safe_dump(cfg_dict))
    print("::endgroup::")
  else:
    workflow_mod = None

  return github, inputs, (dict_to_tuple("settings", cfg_dict) if as_tuple else cfg_dict), workflow_mod


###############################################################################
#
###############################################################################
def dynamic_output(
  clone_dir: Path,
  config_dir: Path,
  github: str,
  outputs: str,
  inputs: str | None = None,
  workflow: str | None = None,
):
  github, inputs, cfg_dict, _ = configuration(clone_dir, config_dir, github, inputs, as_tuple=False, workflow=workflow)
  cfg = dict_to_tuple("settings", cfg_dict)
  action_outputs = {}

  for line in outputs.splitlines():
    line = line.strip()
    if not line:
      continue
    var, val_k = line.split("=")
    var = var.strip()
    val_k = val_k.strip()
    ctx_name = val_k[: val_k.index(".")]
    ctx_select = val_k[len(ctx_name) + 1 :]
    ctx = {
      "cfg": cfg,
      "env": os.environ,
      "github": github,
      "inputs": inputs,
    }[ctx_name]
    action_outputs[var] = _select_attribute(ctx, ctx_select)

  if action_outputs:
    write_output(action_outputs)
  else:
    print("WARNING no output generated")


###############################################################################
#
###############################################################################
def summarize(clone_dir: Path, config_dir: Path, workflow: str, github: str, inputs: str | None = None):
  github, inputs, cfg, workflow_mod = configuration(clone_dir, config_dir, github, inputs, workflow=workflow)
  summary = workflow_mod.summarize(clone_dir=clone_dir, github=github, inputs=inputs, cfg=cfg)
  with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a") as output:
    output.write(summary)
    output.write("\n")
