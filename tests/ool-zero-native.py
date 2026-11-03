#!/usr/bin/env python3
"""Run production OOL copy-in/body with vendored types and isolated VM services.
Usage: ool-zero-native.py <JSON compiler/flags array from ipc_kmsg.c build> <scratch-dir>
No containers, synthetic Mach types, or copied production function bodies.
"""
import json
import re
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
flags = json.loads(Path(sys.argv[1]).read_text())
work = Path(sys.argv[2]).resolve()
work.mkdir(parents=True, exist_ok=True)
text = (root / 'duct-tape/xnu/osfmk/ipc/ipc_kmsg.c').read_text()

def function(signature):
    start = re.search('^' + re.escape(signature), text, re.MULTILINE).start()
    brace = text.index('{', start)
    end, depth = brace + 1, 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end]

# Production includes and legacy types are required by the body function.
preamble = text[:text.index('typedef union{')]
fixture = (root / 'tests/ool-zero-native.c').read_text()
source = work / 'ool-zero.c'
source.write_text(preamble + '\n' + fixture.replace('/* PRODUCTION_FUNCTIONS */',
    'static mach_msg_descriptor_t *\n' + function('ipc_kmsg_copyin_ool_descriptor(') +
    '\nmach_msg_return_t\n' + function('ipc_kmsg_copyin_body(\n')))
subprocess.run(flags + ['-Werror=implicit-function-declaration', str(source), '-o', str(work / 'ool-zero')], check=True)
subprocess.run([str(work / 'ool-zero')], check=True)
