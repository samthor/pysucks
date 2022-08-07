#!/usr/bin/env python

# we use this as the top-level import name
# this uses "bad" characters so it's difficult to accidentally import (need __import__)
virtual_root_name = '--root'

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
  if venv and os.path.commonprefix([venv, dirname]) == venv:
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

with tempfile.TemporaryDirectory() as tmpdir:
  os.symlink(moduleroot, os.path.join(tmpdir, virtual_root_name))

  # Load the "relative" import from the tmpdir: in the virtual root + path
  # importlib_util.find_spec will find our code but _not_ evaluate it
  sys.path = [tmpdir]
  import_name = virtual_root_name + '.' + rel.replace(os.path.sep, ".")
  spec = importlib_util.find_spec(import_name)
  code = spec.loader.get_code(import_name)

  # Drop right-most dot part from the package name, it's the filename
  package_name = import_name.rsplit('.', 1)[0]

  # TODO: this is what runpy module does for some reason
  module = types.ModuleType(import_name)
  g = module.__dict__
  g.update(
    __name__ = "__main__",
    __file__ = cmd,
    __cached__ = None,
    __doc__ = None,
    __loader__ = spec.loader,
    __package__ = package_name,
    __spec__ = spec,
  )

  # Restore path - we"ve loaded code and now want to run it.
  # This is the path without any cwd or the path of this script.
  sys.path = actual_path

  exec(code, g)
