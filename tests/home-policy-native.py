#!/usr/bin/env python3
"""Exercise our exact Library mkdir loop with native and injected syscall failures.
ENOSPC is injected rather than filling the host filesystem. No fixtures are deleted.
The deallocator test counts calls to a mock task_deallocate, not real task references.
"""
from pathlib import Path
import sys
root=Path(__file__).resolve().parents[1]; out=Path(sys.argv[1]).resolve(); out.mkdir(parents=True,exist_ok=True)
s=(root/'src/darlingserver.cpp').read_text(); start=s.index('\t{\n\t\tstatic const char* library_dirs[]'); end=s.index('\n\n\tsnprintf(buf2, sizeof(buf2), "/Volumes/SystemRoot',start)
block=s[start:end]
t=(root/'duct-tape/src/task.c').read_text(); start=t.index('void task_policy_get_deallocate('); end=t.index('\n};',start)+3; dealloc=t[start:end]
prefix=r'''
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <string>
static int inject, calls, errors;
static int fixture_mkdir(const char *p, mode_t mode) {
    calls++;
    if(inject && strstr(p,"/Caches")) { errno=inject; return -1; }
    return mkdir(p,mode);
}
static int fixture_fprintf(FILE *stream,const char *format,...) { errors++; return 0; }
static void home(const char *base) { char buf[4096],buf2[8192]; snprintf(buf,sizeof(buf),"%s",base);
#define mkdir fixture_mkdir
#define fprintf fixture_fprintf
'''
post=r'''
#undef mkdir
#undef fprintf
}
using task_t=int; using task_policy_get_t=int;
static int releases;
static void task_deallocate(task_t t) { if(t==42) releases++; }
'''
main=r'''
static int failed;
static void expect(bool ok,const char *s) { printf("%s %s\n",ok?"ok":"FAIL",s); failed+=!ok; }
int main(int argc,char **argv) {
    std::string d=argv[1]; mode_t old=umask(0); struct stat st={};
    home(d.c_str()); expect(errors==0,"fresh Library hierarchy made");
    stat((d+"/Library").c_str(),&st); expect((st.st_mode&0777)==0700,"Library mode 0700");
    stat((d+"/Library/WebKit").c_str(),&st); expect((st.st_mode&0777)==0755,"WebKit mode 0755");
    chmod((d+"/Library/Caches").c_str(),0700); home(d.c_str());
    stat((d+"/Library/Caches").c_str(),&st); expect((st.st_mode&0777)==0700,"existing directory mode preserved");
    errors=0; calls=0; inject=ENOSPC; home(d.c_str()); expect(errors==1 && calls==13,"injected ENOSPC reported; siblings still attempted");
    errors=0; calls=0; inject=EACCES; home(d.c_str()); expect(errors==1 && calls==13,"injected EACCES reported; siblings still attempted"); inject=0;
    std::string blocked=d+"/blocked"; mkdir(blocked.c_str(),0700);
    int fd=open((blocked+"/Library").c_str(),O_CREAT|O_EXCL|O_WRONLY,0600); close(fd);
    errors=0; calls=0; home(blocked.c_str()); expect(errors==1 && calls==1,"non-directory Library stops descent");
    std::string denied=d+"/denied"; mkdir(denied.c_str(),0500); errors=0; calls=0; home(denied.c_str());
    if(geteuid()==0) printf("SKIP native EACCES: requires non-root\n");
    else expect(errors==1 && calls==1,"native EACCES stops descent");
    chmod(denied.c_str(),0700);
    for(int i=0;i<20000;i++) task_policy_get_deallocate(42);
    expect(releases==20000,"each deallocator call forwards exactly one release");
    umask(old); printf("HARNESS done: %d failed\n",failed); return failed!=0;
}
'''
(out/'home-policy-test.cpp').write_text(prefix+block+post+dealloc+main)
(out/'build.ninja').write_text(f'rule cxx\n  command = c++ -std=c++14 -O1 -Wall $in -o $out\nbuild {out}/home-policy-test: cxx {out}/home-policy-test.cpp\n')
print(out/'home-policy-test')
