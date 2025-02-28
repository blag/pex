# Copyright 2014 Pants project contributors (see CONTRIBUTORS.md).
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import absolute_import

import os

from pex.third_party.pkg_resources import Distribution
from pex.typing import TYPE_CHECKING

if TYPE_CHECKING:
    import attr  # vendor:skip
    from typing import Optional
else:
    from pex.third_party import attr


@attr.s(frozen=True)
class DistributionScript(object):
    @classmethod
    def find(
        cls,
        dist,  # type: Distribution
        name,  # type: str
    ):
        # type: (...) -> Optional[DistributionScript]
        script_path = os.path.join(dist.location, "bin", name)
        return cls(dist=dist, path=script_path) if os.path.isfile(script_path) else None

    dist = attr.ib()  # type: Distribution
    path = attr.ib()  # type: str

    def read_contents(self):
        # type: () -> str
        with open(self.path) as fp:
            return fp.read()

    def is_python_script(self):
        # type: () -> bool
        return is_python_script(self.read_contents(), self.path)


def get_script_from_distributions(name, dists):
    for dist in dists:
        distribution_script = DistributionScript.find(dist, name)
        if distribution_script:
            return distribution_script


def get_entry_point_from_console_script(script, dists):
    # Check all distributions for the console_script "script". De-dup by dist key to allow for a
    # duplicate console script IFF the distribution is platform-specific and this is a multi-platform
    # pex.
    def get_entrypoint(dist):
        script_entry = dist.get_entry_map().get("console_scripts", {}).get(script)
        if script_entry is not None:
            # Entry points are of the form 'foo = bar', we just want the 'bar' part.
            return str(script_entry).split("=")[1].strip()

    entries = {}
    for dist in dists:
        entry_point = get_entrypoint(dist)
        if entry_point is not None:
            entries[dist.key] = (dist, entry_point)

    if len(entries) > 1:
        raise RuntimeError(
            "Ambiguous script specification %s matches multiple entry points:\n\t%s"
            % (
                script,
                "\n\t".join(
                    "%r from %r" % (entry_point, dist) for dist, entry_point in entries.values()
                ),
            )
        )

    dist, entry_point = None, None
    if entries:
        dist, entry_point = next(iter(entries.values()))
    return dist, entry_point


# Copied from
# https://github.com/pypa/setuptools/blob/a4dbe3457d89cf67ee3aa571fdb149e6eb544e88/setuptools/command/easy_install.py#L1893-L1900
def is_python(text, filename="<string>"):
    # type: (str, str) -> bool
    "Is this string a valid Python script?"
    try:
        compile(text, filename, "exec")
    except (SyntaxError, TypeError):
        return False
    else:
        return True


# Copied from
# https://github.com/pypa/setuptools/blob/a4dbe3457d89cf67ee3aa571fdb149e6eb544e88/setuptools/command/easy_install.py#L1918-L1929
def is_python_script(script_text, filename):
    # type: (str, str) -> bool
    """Is this text, as a whole, a Python script? (as opposed to shell/bat/etc."""
    if filename.endswith(".py") or filename.endswith(".pyw"):
        return True  # extension says it's Python
    if is_python(script_text, filename):
        return True  # it's syntactically valid Python
    if script_text.startswith("#!"):
        # It begins with a '#!' line, so check if 'python' is in it somewhere
        return "python" in script_text.splitlines()[0].lower()

    return False  # Not any Python I can recognize
