# Copyright 2021 Pants project contributors (see CONTRIBUTORS.md).
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import absolute_import

import json
import os

import pytest

from pex.common import safe_mkdtemp
from pex.interpreter import PythonInterpreter
from pex.pex_builder import PEXBuilder
from pex.testing import PY37, PY38, ensure_python_interpreter
from pex.tools.commands.virtualenv import Virtualenv
from pex.typing import TYPE_CHECKING

if TYPE_CHECKING:
    import attr  # vendor:skip
    from typing import Iterable, Dict, Any
else:
    from pex.third_party import attr


@pytest.fixture(scope="module")
def python37():
    # type: () -> PythonInterpreter
    return PythonInterpreter.from_binary(ensure_python_interpreter(PY37))


@pytest.fixture(scope="module")
def python38():
    # type: () -> PythonInterpreter
    return PythonInterpreter.from_binary(ensure_python_interpreter(PY38))


@attr.s(frozen=True)
class InterpreterTool(object):
    tools_pex = attr.ib()  # type: str
    interpreter = attr.ib()  # type: PythonInterpreter
    other_interpreters = attr.ib(default=())  # type: Iterable[PythonInterpreter]

    @classmethod
    def create(
        cls,
        interpreter,  # type: PythonInterpreter
        *other_interpreters  # type: PythonInterpreter
    ):
        # type: (...) -> InterpreterTool
        pex_builder = PEXBuilder(interpreter=interpreter)
        pex_builder.info.includes_tools = True
        pex_builder.freeze()
        return cls(
            tools_pex=pex_builder.path(),
            interpreter=interpreter,
            other_interpreters=other_interpreters,
        )

    def run(
        self,
        *args,  # type: str
        **env  # type: str
    ):
        # type: (...) -> str
        cmd = [self.tools_pex, "interpreter"]
        if args:
            cmd.extend(args)

        environ = os.environ.copy()
        interpreters = [self.interpreter]
        interpreters.extend(self.other_interpreters)
        environ.update(
            PEX_PYTHON_PATH=":".join(interpreter.binary for interpreter in interpreters),
            PEX_TOOLS="1",
        )
        environ.update(env)

        _, stdout, _ = self.interpreter.execute(args=cmd, env=environ)
        return stdout


@pytest.fixture(scope="module")
def interpreter_tool(
    python37,  # type: PythonInterpreter
    python38,  # type: PythonInterpreter
):
    # type: (...) -> InterpreterTool
    return InterpreterTool.create(python37, python38)


def expected_basic(interpreter):
    # type: (PythonInterpreter) -> str
    return interpreter.binary


def test_basic(
    python37,  # type: PythonInterpreter
    interpreter_tool,  # type: InterpreterTool
):
    # type: (...) -> None
    output = interpreter_tool.run()
    assert expected_basic(python37) == output.strip()


def test_basic_all(
    python37,  # type: PythonInterpreter
    python38,  # type: PythonInterpreter
    interpreter_tool,  # type: InterpreterTool
):
    # type: (...) -> None
    output = interpreter_tool.run("-a")
    assert [
        expected_basic(interpreter) for interpreter in (python37, python38)
    ] == output.splitlines()


def expected_verbose(interpreter):
    # type: (PythonInterpreter) -> Dict[str, Any]
    return {
        "path": interpreter.binary,
        "platform": str(interpreter.platform),
        "requirement": str(interpreter.identity.requirement),
    }


def test_verbose(
    python37,  # type: PythonInterpreter
    interpreter_tool,  # type: InterpreterTool
):
    # type: (...) -> None
    output = interpreter_tool.run("-v")
    assert expected_verbose(python37) == json.loads(output)


def test_verbose_all(
    python37,  # type: PythonInterpreter
    python38,  # type: PythonInterpreter
    interpreter_tool,  # type: InterpreterTool
):
    # type: (...) -> None
    output = interpreter_tool.run("-va")
    assert [expected_verbose(interpreter) for interpreter in (python37, python38)] == [
        json.loads(line) for line in output.splitlines()
    ]


def expected_verbose_verbose(interpreter):
    # type: (PythonInterpreter) -> Dict[str, Any]
    expected = expected_verbose(interpreter)
    expected.update(supported_tags=[str(tag) for tag in interpreter.identity.supported_tags])
    return expected


def test_verbose_verbose(
    python37,  # type: PythonInterpreter
    interpreter_tool,  # type: InterpreterTool
):
    # type: (...) -> None
    output = interpreter_tool.run("-vv")
    assert expected_verbose_verbose(python37) == json.loads(output)


def test_verbose_verbose_verbose(
    python37,  # type: PythonInterpreter
    interpreter_tool,  # type: InterpreterTool
):
    # type: (...) -> None
    output = interpreter_tool.run("-vvv")
    expected = expected_verbose_verbose(python37)
    expected.update(env_markers=python37.identity.env_markers, venv=False)
    assert expected == json.loads(output)


def test_verbose_verbose_verbose_venv(
    python38,  # type: PythonInterpreter
):
    # type: (...) -> None
    venv = Virtualenv.create(venv_dir=safe_mkdtemp(), interpreter=python38, force=True)
    assert venv.interpreter.is_venv

    # N.B.: Non-venv-mode PEXes always escape venvs to prevent `sys.path` contamination unless
    # `PEX_INHERIT_PATH` is not "false".
    output = InterpreterTool.create(venv.interpreter).run("-vvv", PEX_INHERIT_PATH="fallback")

    expected = expected_verbose_verbose(venv.interpreter)
    expected.update(
        env_markers=venv.interpreter.identity.env_markers,
        venv=True,
        base_interpreter=python38.binary,
    )
    assert expected == json.loads(output)
