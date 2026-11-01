# Library policy and task-policy release fixture

Generate with `python3 tests/home-policy-native.py OUT`; build `ninja -C OUT -j6`
under the host build slot. Run `OUT/home-policy-test FIXTURES` with a fresh existing
directory. The fixture extracts our actual Library loop and task-policy deallocator.

It exercises a fresh hierarchy, an existing hierarchy with a deliberately different
Caches mode, a non-directory Library, native EACCES for a non-root runner, and
injected EACCES/ENOSPC on Caches. ENOSPC injection tests error handling without
filling the host filesystem. It is not a real full-disk or guest-filesystem test.
A mock task_deallocate counts exactly one forwarded release per invocation; it does
not measure live kernel-task reference counts. Keep the real task-policy Mach test
for integration. No files are deleted.

The created Library inventory is Darling initialization policy. WebKit and the
chosen modes remain rung-6 GUESS choices, not a promise about every fresh macOS
home. Existing directories retain their modes. Per-directory rationale remains in
9a35dbd's body; existing Darling policy supports our choice, not an Apple guarantee.
