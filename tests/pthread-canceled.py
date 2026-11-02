#!/usr/bin/env python3
"""Native production RPC/state-machine regression; no containers or guest code."""
import os
from pathlib import Path
import re
import subprocess
import tempfile

root = Path(os.environ.get('DSERVER_TEST_SOURCE', Path(__file__).resolve().parents[1]))
work = Path(tempfile.mkdtemp(prefix='pthread-canceled-'))

def function(text, signature):
    start = text.index(signature)
    brace = text.index('{', start)
    depth = 1
    end = brace + 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end]

thread = (root / 'duct-tape/src/thread.c').read_text()
handler = function((root / 'src/call.cpp').read_text(),
                   'void DarlingServer::Call::PthreadCanceled::processCall()')
helper = function(thread, 'int dtape_pthread_canceled(') if 'int dtape_pthread_canceled(' in thread else ''
flags = '\n'.join(line for line in (root / 'duct-tape/xnu/bsd/sys/user.h').read_text().splitlines()
                  if re.match(r'#define UT_(CANCEL|CANCELED|CANCELDISABLE|NO_SIGMASK|VFORK|NOTCANCELPT)\s', line))
source = work / 'test.cpp'
source.write_text('''#include <cassert>
#include <cerrno>
#include <cstdint>
#include <iostream>
struct Quiet { Quiet& warning() { return *this; } template<class T> Quiet& operator<<(T) { return *this; } int endLog; } callLog;
struct dtape_thread_t { uint32_t uu_flag; int xnu_thread; } state;
struct Hooks { dtape_thread_t* (*current_thread)(); } hooks = { [] { return &state; } }, *dtape_hooks = &hooks;
int lockDepth;
void thread_lock(int*) { assert(lockDepth++ == 0); }
void thread_unlock(int*) { assert(--lockDepth == 0); }
#define LINUX_EINVAL 22
''' + flags + '\n' + helper + '''
namespace DarlingServer { namespace Call { struct PthreadCanceled {
 struct { int action; } _body; int reply;
 void _sendReply(int code) { reply = code; }
 void processCall();
}; }}
''' + handler + '''
int call(int action) {
 DarlingServer::Call::PthreadCanceled rpc; rpc._body.action = action;
 rpc.processCall(); assert(lockDepth == 0); return rpc.reply;
}
int main() {
 state.uu_flag = 0;
 assert(call(0) == -EINVAL);
 assert(call(2) == 0); assert(state.uu_flag == UT_CANCELDISABLE);
 assert(call(2) == 0); assert(call(0) == -EINVAL);
 state.uu_flag |= UT_CANCEL;
 assert(call(0) == -EINVAL); assert((state.uu_flag & UT_CANCEL) != 0);
 assert(call(1) == 0); assert(state.uu_flag == UT_CANCEL);
 assert(call(0) == 0); assert(state.uu_flag == (UT_CANCELED | UT_NO_SIGMASK));
 assert(call(0) == -EINVAL); // consumption is one-shot
 assert(call(2) == 0); assert(call(1) == 0); assert(call(0) == -EINVAL);
 // XNU treats other actions as queries, preserving unrelated flags.
 for (int action : {-1, 3, 2147483647}) {
  state.uu_flag = UT_CANCEL | UT_NOTCANCELPT | UT_VFORK;
  assert(call(action) == 0);
  assert(state.uu_flag == (UT_CANCELED | UT_NO_SIGMASK | UT_NOTCANCELPT | UT_VFORK));
 }
 state.uu_flag = UT_CANCELED | UT_CANCEL;
 assert(call(0) == -EINVAL); assert(state.uu_flag == (UT_CANCELED | UT_CANCEL));
 std::cout << "PASS RPC cancellation query, disable/enable, pending preservation, one-shot consumption, default actions, unrelated flags\\n";
}
''')
subprocess.run([os.environ.get('CXX', 'c++'), '-std=c++17', '-Wall', '-Wextra', '-Werror',
                str(source), '-o', str(work / 'test')], check=True)
subprocess.run([str(work / 'test')], check=True)
print('Native fixture:', work)
