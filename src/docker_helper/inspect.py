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

def inspect(
    images: str,
    output: str,
) -> None:
  images = [img.strip() for img in images.strip().splitlines()]
  images = {}
  layers = {}
  for img in images:
    result = subprocess.run([
      "docker", "buildx", "imagetools", "inspect", img, "--raw"
    ], stdout=subprocess.PIPE, check=True)
    images[img] = json.loads(result.stdout.decode())
    for img_manifest in images[img].manifests:
      layer_digest = img_manifest["digest"]
      layer_images = layers[layer_digest] = layers.get(layer_digest, set())
      layer_images.add(img)
  result = {
    "images": images,
    "layers": {
      layer: list(images)
      for layer, images in layers.items()
    },
  }
  output = Path(output.strip())
  output.parent.mkdir(exist_ok=True, parents=True)
  with output.open("w") as outstream:
    outstream.write(json.dumps(result))

