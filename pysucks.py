#!/usr/bin/env python

# sys is probably from CPython and cannot be replaced
import sys

# os is not from CPython but cannot be replaced (always goes to package)
import os

# Python puts the path of _this file_ here first.
# also remove the cwd dir in case it"s here.
reldir = os.path.dirname(__file__)
sys.path = list(filter(lambda name: not (name == os.getcwd() or name == reldir), sys.path))

# Import anything we need here from Python built-in before we nuke the path.
from importlib import util as importlib_util
import types
import tempfile

actual_path = sys.path
sys.path = []

if len(sys.argv) < 2:
  print(f"usage: {sys.argv[0]} <script>")
  sys.exit(1)

def choose_moduleroot(dirname):
  """
  Short-circuits a moduleroot. Uses VIRTUAL_ENV if found.
  """
  venv = os.getenv("VIRTUAL_ENV")
  if os.path.commonprefix([venv, dirname]) == venv:
    return venv

def use_as_moduleroot(dirname):
  """
  Returns whether the passed dirname should be the module root.
  Called in order from largest absolute path to smallest.
  """
  # TODO: could be user-configured or look for e.g., ".git" to stop
  part = os.path.basename(dirname)
  if "." in part:
    return True

# Grab cwd, convert to absolute path: e.g., "/Users/whatever/path/to"
# Will be "/foo.py" for script or "/foo" for dir (no trailing slash)
cmd = sys.argv.pop(1)
if not os.path.isabs(cmd):
  cmd = os.path.abspath(cmd)

if os.path.isdir(cmd):
  # TODO: this is implicit in module loader but here so "cmd" is always a file
  dir = cmd
  script = "__main__.py"
  cmd = os.path.join(dir, script)
else:
  dir = os.path.dirname(cmd)
  script = os.path.basename(cmd)

if not os.path.exists(cmd):
  print(f"file does not exist: {cmd}")
  sys.exit(1)

moduleroot = choose_moduleroot(dir)
if not moduleroot:
  # Fall back to finding via `use_as_moduleroot`, or uses the root dir.
  moduleroot = dir
  while True:
    if use_as_moduleroot(moduleroot):
      break
    part = os.path.basename(moduleroot)
    update = os.path.dirname(moduleroot)
    if moduleroot == update:
      break
    moduleroot = update

rel = os.path.relpath(cmd, moduleroot)

# Modules cannot end with '.py'
if rel.endswith(".py"):
  rel = rel[:-3]
import_name = rel.replace(os.path.sep, ".")

print("moduleroot=", moduleroot, "import_name=", import_name)

with tempfile.TemporaryDirectory() as tmpdir:
  os.symlink(moduleroot, os.path.join(tmpdir, 'root'))

  print("got tmpdir")

  # importlib.util.find_spec will find our code but not evaluate it
  sys.path = [tmpdir]

  import_name = 'root.' + import_name

  spec = importlib_util.find_spec(import_name)
  code = spec.loader.get_code(import_name)

  # TODO: this is what runpy module does for some reason
  module = types.ModuleType(import_name)
  g = module.__dict__
  g.update(
    __name__ = "__main__",
    __file__ = cmd,
    __cached__ = None,
    __doc__ = None,
    __loader__ = spec.loader,
    __package__ = import_name,
    __spec__ = spec,
  )

  # Restore path - we"ve loaded code and now want to run it.
  # This is the path without any cwd or the path of this script.
  sys.path = actual_path
  exec(code, g)
