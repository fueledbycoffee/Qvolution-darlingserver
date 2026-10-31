#!/usr/bin/env python3
import pathlib,re,subprocess,tempfile,sys
root=pathlib.Path(__file__).resolve().parents[1]
revision=sys.argv[1] if len(sys.argv)>1 else '9353d34ea77df8b34c6f9c23a67e1894eb7d2811'
with tempfile.TemporaryDirectory(prefix='qv-unix-rpc-') as tmp:
 d=pathlib.Path(tmp);old=d/'old.py';old.write_text(subprocess.check_output(['git','show',revision+':scripts/generate-rpc-wrappers.py'],cwd=root,text=True));maps=[]
 for i,script in enumerate((old,root/'scripts/generate-rpc-wrappers.py')):
  h=d/str(i)/'rpc.h';subprocess.run(['python3',str(script),str(h),str(h.with_suffix('.internal.h')),str(h.with_suffix('.c')),'"rpc.h"'],check=True)
  maps.append(dict(re.findall(r'^\s*(dserver_callnum_\w+) = (.*),$',h.read_text(),re.M)))
 before,after=maps
 assert all(after.get(k)==v for k,v in before.items()),'existing wire number changed'
 assert set(after)-set(before)=={'dserver_callnum_vchroot_socket_root'},'unexpected appended RPCs'
 print('PASS: all existing wire numbers preserved, only caller-root socket RPC appended')
