"""Unprivileged filesystem sandbox (Linux Landlock, no user namespaces needed).

bio06 blocks unprivileged user namespaces (AppArmor), so bwrap cannot run. Landlock can: a process restricts itself and
every child inherits the restriction; it cannot be undone. We use it for two things:
  * agent sessions (Command Code and every shell command they start) can read only an allowlist of paths;
    the protected answer files (E7.25, E7.5) and everything else on /scratch are unreadable;
  * program runs (an agent's predict()) can read only the snapshot, the harness and the stage files of that split,
    write only their output directory, and cannot open TCP connections.

Usage as a launcher:  python -m fm.landlock --ro P ... --rw P ... [--no-tcp] [--scope-signals] -- CMD ARGS...
"""
import argparse
import ctypes
import os
import sys

SYS_CREATE, SYS_ADD_RULE, SYS_RESTRICT = 444, 445, 446  # x86_64
PATH_BENEATH = 1
PR_SET_NO_NEW_PRIVS = 38

EXECUTE, WRITE_FILE, READ_FILE, READ_DIR = 1 << 0, 1 << 1, 1 << 2, 1 << 3
REMOVE_DIR, REMOVE_FILE, MAKE_CHAR, MAKE_DIR, MAKE_REG, MAKE_SOCK, MAKE_FIFO, MAKE_BLOCK, MAKE_SYM = (1 << i for i in range(4, 13))
REFER, TRUNCATE, IOCTL_DEV = 1 << 13, 1 << 14, 1 << 15
FILE_ONLY = EXECUTE | WRITE_FILE | READ_FILE | TRUNCATE | IOCTL_DEV
RO = EXECUTE | READ_FILE | READ_DIR
NET_BIND_TCP, NET_CONNECT_TCP = 1, 2
SCOPE_SIGNAL = 2

_libc = ctypes.CDLL(None, use_errno=True)
_libc.syscall.restype = ctypes.c_long


class _RulesetAttr(ctypes.Structure):
    _fields_ = [('handled_access_fs', ctypes.c_uint64), ('handled_access_net', ctypes.c_uint64),
                ('scoped', ctypes.c_uint64)]


class _PathBeneath(ctypes.Structure):
    _pack_ = 1
    _fields_ = [('allowed_access', ctypes.c_uint64), ('parent_fd', ctypes.c_int32)]


def abi():
    v = _libc.syscall(SYS_CREATE, None, ctypes.c_size_t(0), ctypes.c_uint32(1))
    return int(v) if v >= 0 else 0


def _fs_mask(version):
    m = (1 << 13) - 1
    if version >= 2:
        m |= REFER
    if version >= 3:
        m |= TRUNCATE
    if version >= 5:
        m |= IOCTL_DEV
    return m


def restrict(ro=(), rw=(), no_tcp=False, scope_signals=False):
    """Restrict this process (and all future children) to the given paths. Missing paths are skipped."""
    version = abi()
    if version < 1:
        raise OSError('Landlock is not available on this kernel')
    handled = _fs_mask(version)
    attr = _RulesetAttr(handled, (NET_BIND_TCP | NET_CONNECT_TCP) if (no_tcp and version >= 4) else 0,
                        SCOPE_SIGNAL if (scope_signals and version >= 6) else 0)
    size = ctypes.sizeof(_RulesetAttr) if version >= 6 else (16 if version >= 4 else 8)
    fd = _libc.syscall(SYS_CREATE, ctypes.byref(attr), ctypes.c_size_t(size), ctypes.c_uint32(0))
    if fd < 0:
        raise OSError(ctypes.get_errno(), 'landlock_create_ruleset failed')
    try:
        for paths, access in ((ro, RO), (rw, handled)):
            for p in paths:
                if not os.path.exists(p):
                    continue
                pfd = os.open(p, os.O_PATH | os.O_CLOEXEC)
                try:
                    allowed = access & handled
                    if not os.path.isdir(p):
                        allowed &= FILE_ONLY
                    rule = _PathBeneath(allowed, pfd)
                    if _libc.syscall(SYS_ADD_RULE, ctypes.c_int(fd), ctypes.c_int(PATH_BENEATH), ctypes.byref(rule),
                                     ctypes.c_uint32(0)) < 0:
                        raise OSError(ctypes.get_errno(), f'landlock_add_rule failed for {p}')
                finally:
                    os.close(pfd)
        if _libc.prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) != 0:
            raise OSError(ctypes.get_errno(), 'prctl(NO_NEW_PRIVS) failed')
        if _libc.syscall(SYS_RESTRICT, ctypes.c_int(fd), ctypes.c_uint32(0)) < 0:
            raise OSError(ctypes.get_errno(), 'landlock_restrict_self failed')
    finally:
        os.close(fd)
    return version


SYSTEM_RO = ['/usr', '/lib', '/lib64', '/lib32', '/bin', '/sbin', '/etc', '/opt', '/run', '/sys', '/snap']
SYSTEM_RW = ['/dev', '/proc']


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ro', action='append', default=[])
    ap.add_argument('--rw', action='append', default=[])
    ap.add_argument('--no-tcp', action='store_true')
    ap.add_argument('--scope-signals', action='store_true')
    ap.add_argument('--no-system', action='store_true', help='do not add the standard system paths')
    ap.add_argument('cmd', nargs=argparse.REMAINDER)
    a = ap.parse_args()
    cmd = a.cmd[1:] if a.cmd and a.cmd[0] == '--' else a.cmd
    if not cmd:
        ap.error('no command')
    ro = list(a.ro) + ([] if a.no_system else SYSTEM_RO)
    rw = list(a.rw) + ([] if a.no_system else SYSTEM_RW)
    restrict(ro, rw, a.no_tcp, a.scope_signals)
    os.execvp(cmd[0], cmd)


if __name__ == '__main__':
    sys.exit(main())
