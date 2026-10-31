# Startup readiness contract

Run from the repository root on Linux with Python3 and a C++17 compiler:

```sh
python3 tests/startup-handshake.py
```

`CXX` selects the native compiler. Generated sources and executables are temporary;
no installed runtime, namespace mounts, guest programs or vendor images are used.
The tests need ordinary local UNIX sockets, which some sandboxes deny.

The runner compiles the actual production handshake snippets and
`src/startup-handshake.hpp` with authored socket-binding Server and launchd
stubs. It checks successful publication/RPC, a cancelled launcher reader,
namespace-child EOF, failed green-light notification, and EOF while the child is
still alive after closing its inherited ready writer. Failure cases require a
nonzero server result, no launch marker and no remaining RPC socket. Explicit
pipe acknowledgments establish ordering; scheduling delays do not.

`startup-handshake-io.cpp` exercises the actual header with controlled syscall
responses: EINTR retries, EOF, invalid byte, EIO, short write and EPIPE. Socket
notifications must use MSG_NOSIGNAL.

The ordering control replays the ready/bind action order read from production
source. The original source order fails deterministically with exactly ENOENT on
the first send, a successful later send and a successful helper exit:

```sh
python3 tests/startup-handshake.py --order-revision b646fa5 --order-only
# expected exit 1; ordering record: exit=1, first=-1 errno=2 later=1 helper=0

python3 tests/startup-handshake.py --order-revision b646fa5 --order-only --expect-premature-ready
# expected exit 0 only for that exact record, with no timeout/cleanup failure
```

This source-order replay and the native stubs are narrower than executing the
full server. Constructor exceptions, kernel/setup stalls, filesystem/namespace
setup, and real guest startup remain integration gates. These tests do not
attribute earlier empty timeout logs to a particular cause.

Each native control runs in a fresh session. The test process acts as a Linux
child subreaper; a deadline kills only that owned control group and any adopted
control children, then reaps them within a bound. Output goes to temporary files,
so inherited writers cannot block a pipe drain. A deliberately blocked controller
and child verify timeout cleanup; other timeouts are explicit test failures.

The blocked child acknowledges its setup before the controller flushes a ready
marker; the short cleanup deadline starts only after that marker is observed.
The supervisor resets SIGCHLD to SIG_DFL before spawning, so an inherited ignored
disposition cannot invalidate child ownership or reaping.

Owned children are finalized after normal controller exits too (after the
launcher's helper-completion acknowledgment). Lingering children fail ordinary
controls and are stopped/reaped before the runner returns. A second supervision
control deliberately exits the controller while its acknowledged child remains
alive; the suite requires detection and cleanup of that condition.
