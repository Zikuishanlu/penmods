"""Install pip packages despite this sandbox's mkdtemp DACL problem.

On this machine `tempfile.mkdtemp()` (which calls os.mkdir(path, 0o700)) produces a
directory the same process cannot write into, so pip's unpack step fails with
`Permission denied`. os.mkdir(path, 0o777) works, so force the permissive mode.
"""
import os
import sys

_real_mkdir = os.mkdir


def _mkdir(path, mode=0o777, *, dir_fd=None):
    if dir_fd is None:
        return _real_mkdir(path, 0o777)
    return _real_mkdir(path, 0o777, dir_fd=dir_fd)


os.mkdir = _mkdir

from pip._internal.cli.main import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
