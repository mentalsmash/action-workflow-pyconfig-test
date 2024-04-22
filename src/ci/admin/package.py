from typing import NamedTuple, Generator, TextIO
from datetime import datetime
from functools import partial

from .data_object import DataObject, build, parse
from .log import log
from .gh_api import gh_api
from .fzf import fzf_filter

###############################################################################
# GitHub Package data object (parsed from query result)
###############################################################################
class Package(NamedTuple):
  id: str
  repository: str
  name: str
  visibility: str
  created_at: datetime
  updated_at: datetime

  DatetimeFields = [4, 5]

  def __str__(self) -> str:
    return DataObject.str(self)

  ###############################################################################
  # List available packages for the current user or an organization
  ###############################################################################
  @classmethod
  def select(
    cls,
    org: str | None = None,
    filter: str | None = None,
    package_type: str = "container",
    prompt: str | None = None,
    noninteractive: bool = False,
    packages: list["Package"] | None = None,
    skip_last: bool = False
  ) -> list["Package"]:
    def _ls_packages() -> Generator[Package, None, None]:
      jq_filter = (
        "[ (.[] | [.id, .repository.full_name, .name, .visibility, .created_at, .updated_at]) ]"
      )
      url = (
        f"/orgs/{org}/packages?package_type={package_type}"
        if org
        else "/user/packages?package_type={package_type}"
      )
      log.activity("listing packages for {}", org if org else "current user")
      packages = gh_api(url, jq_filter, default=[])
      for pkg_entry in packages:
        pkg = build(cls, *pkg_entry)
        yield pkg

    def _read_and_parse_package(input_stream: TextIO) -> list[Package]:
      return [
        pkg
        for line in input_stream.readlines()
        for sline in [line.decode().strip()]
        if sline
        for pkg in [parse(cls, sline)]
        if pkg
      ]

    if packages is None:
      packages = list(_ls_packages())

    if not packages:
      log.warning("[{}] no package detected", org if org else "current user")
      return []

    if prompt is None:
      prompt = "available packages"
    sort_packages = partial(sorted, key=lambda p: p.updated_at)
    fzf = fzf_filter(
      filter=filter,
      inputs=sort_packages(packages),
      prompt=prompt,
      noninteractive=noninteractive,
    )
    result = sort_packages(_read_and_parse_package(fzf.stdout))
    if skip_last and result:
      log.warning("[{}] skipping most recent package: {}", org, result[-1])
      result = result[:-1]
    return result
