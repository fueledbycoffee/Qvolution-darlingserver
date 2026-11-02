# Cancellation-point state

`PthreadCanceled` uses the state transitions in published XNU's
`bsd/kern/kern_sig.c::__pthread_canceled` (vendored in the sibling xnu tree).
Actions 1 and 2 enable/disable handling without dropping a pending request.
Action 0 and other values consume an enabled pending request exactly once,
mark it canceled, and invalidate its signal mask; otherwise they return EINVAL.
The flags use the vendored `duct-tape/xnu/bsd/sys/user.h` definitions. State is
per duct-taped thread, initialized on creation, protected by the thread lock,
and replaced along with that thread on exec. The hot path has no allocation,
scan, or additional IPC.

Native verification: `python3 tests/pthread-canceled.py`. This compiles the
production RPC handler and state function in a lock-checking native fixture,
including disabled pending requests, repeated queries, and unrelated flags.
`DSERVER_TEST_SOURCE=<old-source> python3 tests/pthread-canceled.py` exercises
the same test against the old RPC handler (fails: ENOSYS instead of EINVAL).

This is not a complete pthread_cancel implementation: the separate existing
PthreadMarkcancel RPC still returns ENOSYS and cannot enqueue a request. The
native fixture seeds pending flags to cover their specified consumption.
No claim is made that this fixes the Stage41e server disappearance. That log
ends during process teardown without an exit status or fatal diagnostic.
