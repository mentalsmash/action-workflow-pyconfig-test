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
from typing import NamedTuple
from pathlib import Path

from helpers.a_function import a_function

def configure(
    clone_dir: Path,
    cfg: NamedTuple,
    github: NamedTuple,
    inputs: NamedTuple) -> dict:
  assert "a string" == inputs.string
  assert inputs.boolean
  assert int(inputs.int) == 42
  return {
    "A_FUNCTION_OUTPUT": a_function(cfg.bar),
  }


def summarize(
    clone_dir: Path,
    cfg: NamedTuple,
    github: NamedTuple,
    inputs: NamedTuple) -> str:
  
  return """\
# Dymamic Summary

Hello from Python!
"""
