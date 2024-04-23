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
import subprocess
import json
from pathlib import Path

from cli_helper.log import log

def inspect(
    images: str,
    output: str,
) -> None:
  images = [img.strip() for img in images.strip().splitlines()]
  log.debug("inspecting {} docker images", len(images))
  r_images = {}
  r_layers = {}
  for img in images:
    cmd = [
      "docker", "buildx", "imagetools", "inspect", img, "--raw"
    ]
    log.command(cmd)
    result = subprocess.run(cmd, stdout=subprocess.PIPE, check=True)
    stdout = result.stdout.decode().strip()
    r_images[img] = json.loads(stdout)
    for img_manifest in r_images[img]["manifests"]:
      layer_digest = img_manifest["digest"]
      layer_images = r_layers[layer_digest] = r_layers.get(layer_digest, set())
      layer_images.add(img)
  result = {
    "images": r_images,
    "layers": {
      layer: list(images)
      for layer, images in r_layers.items()
    },
  }
  output = Path(str(output).strip())
  output.parent.mkdir(exist_ok=True, parents=True)
  with output.open("w") as outstream:
    outstream.write(json.dumps(result, indent=2))

