# Empty physical-copy OOL descriptors

`ool-zero-native.py <compiler-args.json> <scratch-directory>` compiles the production
`ipc_kmsg_copyin_body` and `ipc_kmsg_copyin_ool_descriptor` directly from the current
source, with the production includes/types and build flags. Supply a JSON array
containing clang plus the defines/includes/flags used to compile ipc_kmsg.c (omit
-MD/-MT/-MF/-o/-c and their operands). No container is needed.

VM allocation/copy services are isolated fixtures. Other descriptor services abort
if called. The checks exercise both user descriptor widths in the native 64-bit
server, its real descriptor-expansion code, threshold zero and 8192, empty physical
and virtual copies (NULL, non-NULL and invalid source), deallocation on/off,
normal/volatile OOL descriptors, a five-byte payload, interspersed empty/payload
regions, invalid copy options, and the preflight VM reservation limit.

Before the fix the first empty physical-copy case fails with result 0x400 instead
of success. After the fix all cases pass. This does not replace the guest Mach
send/receive differential test: `checks/mach-ool-zero.c` in lane mach-ool-zero.

Contract: rung 1, Apple's XNU 8019.80.24 `osfmk/ipc/ipc_kmsg.c`,
`ipc_kmsg_copyin_ool_descriptor` explicitly clears empty descriptors' address
without touching memory. The preflight must let them reach that path even when
Darling's allocator sets the small-copy threshold to zero.
https://raw.githubusercontent.com/apple-oss-distributions/xnu/xnu-8019.80.24/osfmk/ipc/ipc_kmsg.c
