import re
import traceback
from typing import NamedTuple
from datetime import datetime

from .log import log
from .date import github_date_parse, github_date_str

###############################################################################
# Helper for data objects
###############################################################################
class DataObject:
  Parsers = {}

  @classmethod
  def build(cls, obj_cls: type[NamedTuple], *args) -> NamedTuple:
    cls.data_object(obj_cls)
    build_args = list(args)
    for i, arg in enumerate(args):
      if i in obj_cls.DatetimeFields:
        if not isinstance(arg, datetime):
          build_args[i] = github_date_parse(arg)
      elif isinstance(arg, str):
        build_args[i] = arg.strip()
    return obj_cls(*build_args)

  @classmethod
  def parse(cls, obj_cls: type[NamedTuple], obj_line: str) -> object | None:
    cls.data_object(obj_cls)
    try:
      parse_re = cls.Parsers[obj_cls]
      fields = parse_re.findall(obj_line)
      fields = fields[0]
      return cls.build(obj_cls, *fields)
    except Exception:
      log.error("failed to parse {}: '{}'", obj_cls.__qualname__, obj_line)
      traceback.print_exc()
      return None

  @classmethod
  def str(cls, obj: NamedTuple) -> str:
    fields = list(obj)
    for i in obj.DatetimeFields:
      fields[i] = github_date_str(fields[i])
    return "\t".join(map(str, fields))

  @classmethod
  def parse_re(cls, obj_cls: type[NamedTuple]) -> re.Pattern:
    # Parse a string of fields separated by tabs.
    assert len(obj_cls._fields) >= 1
    return re.compile(
      "".join(
        (
          "^",
          *(r"([^\t]+)[\t]+" for i in range(len(obj_cls._fields) - 1)),
          r"(.*)",
          "$",
        )
      )
    )

  @classmethod
  def data_object(cls, obj_cls: type[NamedTuple]) -> None:
    if obj_cls not in cls.Parsers:
      cls.Parsers[obj_cls] = cls.parse_re(obj_cls)


###############################################################################
# Shorthand for DataObject.parse()
###############################################################################
def parse(obj_cls: type[NamedTuple], package_line) -> NamedTuple:
  return DataObject.parse(obj_cls, package_line)


###############################################################################
# Shorthand for DataObject.build()
###############################################################################
def build(obj_cls: type[NamedTuple], *args) -> object | None:
  return DataObject.build(obj_cls, *args)

