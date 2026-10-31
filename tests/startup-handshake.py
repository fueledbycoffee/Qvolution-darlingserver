"""Compile actual startup helpers and production handshake snippets with native stubs.
No guest or full runtime is loaded; synchronization uses pipes, never timing delays.
"""
import argparse, ctypes, json, os, shlex, signal, subprocess, tempfile, time
from pathlib import Path
# Linux prctl.h: make only this test process the reaper for its own controls.
PR_SET_CHILD_SUBREAPER=36
signal.signal(signal.SIGCHLD,signal.SIG_DFL)
libc=ctypes.CDLL(None,use_errno=True)
if libc.prctl(PR_SET_CHILD_SUBREAPER,1,0,0,0):
    raise OSError(ctypes.get_errno(),'cannot supervise native controls')
def owned_children():
    return [int(pid) for pid in Path('/proc/self/task/'+str(os.getpid())+'/children').read_text().split()]
def reap_controls(deadline):
    while True:
        try:
            while os.waitpid(-1,os.WNOHANG)[0]: pass
        except ChildProcessError:
            return True
        if time.monotonic()>=deadline:return False
        time.sleep(0.005)
def stop_controls():
    deadline=time.monotonic()+2
    while owned_children() and time.monotonic()<deadline:
        for child in owned_children():
            try:os.kill(child,signal.SIGKILL)
            except ProcessLookupError:pass
        reap_controls(min(deadline,time.monotonic()+0.05))
    return not owned_children()
def run_control(argv,timeout=10,env=None,cwd=None,ready_marker=None,finalize=True):
    with tempfile.TemporaryFile() as output,tempfile.TemporaryFile() as errors:
        process=subprocess.Popen(argv,stdout=output,stderr=errors,start_new_session=True,env=env,cwd=cwd)
        expired=False;cleaned=True;ready_seen=ready_marker is None
        if ready_marker is not None:
            deadline=time.monotonic()+2
            while time.monotonic()<deadline:
                ready_seen=ready_marker in os.pread(output.fileno(),1000001,0)
                if ready_seen:break
                if process.poll() is not None:
                    ready_seen=ready_marker in os.pread(output.fileno(),1000001,0)
                    break
                time.sleep(0.005)
        try:process.wait(timeout=timeout if ready_seen else 0)
        except subprocess.TimeoutExpired:
            expired=True
            # This fresh group contains only the authored controller/stubs.
            try:os.killpg(process.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            try:process.wait(timeout=1)
            except subprocess.TimeoutExpired:cleaned=False
            # Actual launcher children call setsid; after their controller dies,
            # the subreaper owns them directly. Never inspect or signal host peers.
            cleaned=stop_controls() and cleaned
        strays=bool(owned_children())
        if finalize and strays:cleaned=stop_controls() and cleaned
        output.seek(0);errors.seek(0)
        stdout=output.read(1000001);stderr=errors.read(1000001)
        overflow=len(stdout)>1000000 or len(stderr)>1000000
        result=subprocess.CompletedProcess(argv,124 if expired else process.returncode,
            stdout[:1000000].decode(errors='replace'),stderr[:1000000].decode(errors='replace'))
        return result,expired,cleaned and not overflow,ready_seen,strays

base=Path(__file__).resolve().parent.parent
parser=argparse.ArgumentParser()
parser.add_argument('--order-revision',help='Replay readiness/bind order from this source revision')
parser.add_argument('--order-only',action='store_true')
parser.add_argument('--expect-premature-ready',action='store_true',help='Require the exact gated ENOENT baseline outcome')
args=parser.parse_args()
if args.expect_premature_ready and not (args.order_only and args.order_revision):
    parser.error('--expect-premature-ready requires --order-only and --order-revision')
src=(base/'src/darlingserver.cpp').read_text()
order_source=subprocess.check_output(['git','-C',str(base),'show',args.order_revision+':src/darlingserver.cpp'],text=True) if args.order_revision else src
order_ready=order_source.index('write(pipefd, ".", 1);') if 'write(pipefd, ".", 1);' in order_source else order_source.index('startupWriteByte(pipefd)')
order_before=order_ready<order_source.index('auto server = new DarlingServer::Server(prefix);')
child_start=src.index('\t} else if (launchdGlobalPID == 0) {')
child_prefix=src[src.index('\t\tclose(pipefd);',child_start):src.index('\t\t// Detach launchd',child_start)]
notify_start=src.index('\t\tif (!startupWriteByte(childWaitFDs[0], true))',child_start)
notify=src[notify_start:src.index('\n\t\t// drop our privileges now',notify_start)]
await_start=src.index('\t\tif (!startupReadByte(childWaitFDs[0]))',child_start)
await_green=src[await_start:src.index('\n\t\t__builtin_unreachable();',await_start)]
parent_start=src.index('\t// this is the parent',await_start)
parent=src[parent_start:src.index('\n\t// start the main loop',parent_start)]
header=r'''
#include <sys/socket.h>
#include <sys/un.h>
#include <sys/wait.h>
#include <sys/prctl.h>
#include <poll.h>
#include <signal.h>
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <string>
#include "SERVER_HEADER"
#define startupReadReady startupReadByte
static std::string testMode;
static int ackRead=-1, ackWrite=-1, releaseRead=-1, releaseWrite=-1;
static void byteWrite(int fd) { if(write(fd,".",1)!=1) _exit(90); }
static void byteRead(int fd) { char byte; if(read(fd,&byte,1)!=1) _exit(91); }
static void perma_drop_privileges(uid_t, gid_t) {
    if(testMode=="green-eof") byteRead(ackRead);
}
static void spawnLaunchd(const char *prefix) {
    std::string marker=std::string(prefix)+"/launched";
    int fd=open(marker.c_str(),O_WRONLY|O_CREAT,0600); if(fd<0) _exit(92); close(fd); _exit(0);
}
namespace DarlingServer {
class Server {
    int fd; std::string path;
public:
    Server(const char *prefix):path(std::string(prefix)+"/.darlingserver.sock") {
        fd=socket(AF_UNIX,SOCK_DGRAM,0); sockaddr_un addr={}; addr.sun_family=AF_UNIX;
        snprintf(addr.sun_path,sizeof(addr.sun_path),"%s",path.c_str());
        if(fd<0 || bind(fd,(sockaddr*)&addr,sizeof(addr))<0) _exit(93);
    }
    ~Server(){close(fd);unlink(path.c_str());}
};
}
static int runServer(const char *prefix,int pipefd) {
    int childWaitFDs[2]; if(socketpair(AF_UNIX,SOCK_STREAM,0,childWaitFDs)) return 94;
    pid_t launchdGlobalPID=fork();
    if(launchdGlobalPID<0) return 95;
    if(launchdGlobalPID==0) {
CHILD_PREFIX
        if(testMode=="namespace-eof") _exit(0);
CHILD_NOTIFY
        if(testMode=="green-eof") {close(childWaitFDs[0]);byteWrite(ackWrite);_exit(0);}
CHILD_AWAIT
    }
    uid_t originalUID=getuid();gid_t originalGID=getgid();
PARENT
    byteRead(releaseRead);
    int status;while(waitpid(launchdGlobalPID,&status,0)<0&&errno==EINTR){}
    delete server;
    return WIFEXITED(status)&&WEXITSTATUS(status)==0 ? 0 : 96;
}
static int inheritedEOF() {
    int ready[2],childWaitFDs[2],ack[2],release[2];pipe(ready);pipe(ack);pipe(release);
    socketpair(AF_UNIX,SOCK_STREAM,0,childWaitFDs);
    int pipefd=ready[1];pid_t child=fork();
    if(child==0){close(ready[0]);close(ack[0]);close(release[1]);
CHILD_PREFIX
        byteWrite(ack[1]);byteRead(release[0]);_exit(0);
    }
    close(ready[1]);close(ack[1]);close(release[0]);byteRead(ack[0]);
    // Child acknowledged executing the production close. It is still alive,
    // so EOF now proves that it does not retain the ready writer.
    pollfd pfd={ready[0],POLLIN|POLLHUP,0};int available=poll(&pfd,1,0);
    bool eof=available==1 && !startupReadReady(ready[0]) && errno==EPIPE;
    byteWrite(release[1]);int status;waitpid(child,&status,0);
    printf("inherited-ready-eof=%d child=%d\n",eof,WEXITSTATUS(status));return eof?0:1;
}

static int orderingControl() {
    int ready[2],attempted[2],bound[2],done[2];pipe(ready);pipe(attempted);pipe(bound);pipe(done);
    char temporary[]="qv-order-XXXXXX";char *prefix=mkdtemp(temporary);if(!prefix)return 2;
    pid_t helper=fork();
    if(helper==0){
        close(ready[0]);
        if(ORDER_BEFORE){startupWriteByte(ready[1]);byteRead(attempted[0]);}
        auto server=new DarlingServer::Server(prefix);
        if(!ORDER_BEFORE)startupWriteByte(ready[1]);
        byteWrite(bound[1]);byteRead(done[0]);delete server;_exit(0);
    }
    close(ready[1]);bool gotReady=startupReadByte(ready[0]);
    int fd=socket(AF_UNIX,SOCK_DGRAM,0);sockaddr_un address={};address.sun_family=AF_UNIX;
    snprintf(address.sun_path,sizeof(address.sun_path),"%s/.darlingserver.sock",prefix);
    int first=sendto(fd,".",1,0,(sockaddr*)&address,sizeof(address));int error=first<0?errno:0;
    byteWrite(attempted[1]);byteRead(bound[0]);
    int later=sendto(fd,".",1,0,(sockaddr*)&address,sizeof(address));byteWrite(done[1]);close(fd);
    int status;waitpid(helper,&status,0);rmdir(prefix);
    int helperExit=WIFEXITED(status)?WEXITSTATUS(status):-1;
    printf("ready=%d first=%d errno=%d later=%d helper=%d\n",gotReady,first,error,later,helperExit);
    if(ORDER_BEFORE && !(gotReady&&first==-1&&error==ENOENT&&later==1&&helperExit==0))return 2;
    return gotReady&&first==1&&later==1&&helperExit==0?0:1;
}

int main(int argc,char **argv){
    if(argc!=2)return 2;testMode=argv[1];signal(SIGPIPE,SIG_IGN);
    if(testMode=="timeout-control" || testMode=="orphan-control"){
        int ack[2];if(pipe(ack))return 97;
        pid_t blocked=fork();if(blocked<0)return 98;
        if(blocked==0){close(ack[0]);byteWrite(ack[1]);for(;;)pause();}
        close(ack[1]);byteRead(ack[0]);puts("TIMEOUT_CHILD_READY");fflush(stdout);if(testMode=="orphan-control")return 0;for(;;)pause();
    }
    if(testMode=="inherit-eof")return inheritedEOF();
    if(testMode=="ordering")return orderingControl();
    char temporary[]="qv-contract-XXXXXX";char *prefix=mkdtemp(temporary);if(!prefix)return 3;
    int ready[2],ack[2],release[2],start[2];pipe(ready);pipe(ack);pipe(release);pipe(start);
    ackRead=ack[0];ackWrite=ack[1];releaseRead=release[0];releaseWrite=release[1];
    pid_t server=fork();if(server==0){close(ready[0]);close(start[1]);byteRead(start[0]);
        int result=runServer(prefix,ready[1]);_exit(result);}
    close(ready[1]);close(start[0]);
    bool cancelled=testMode=="cancel";
    if(cancelled)close(ready[0]);byteWrite(start[1]);close(start[1]);
    bool readyOK=false;int readyError=0,rpc=0;
    if(!cancelled){readyOK=startupReadReady(ready[0]);readyError=readyOK?0:errno;close(ready[0]);}
    if(testMode=="success"){
        int fd=socket(AF_UNIX,SOCK_DGRAM,0);sockaddr_un address={};address.sun_family=AF_UNIX;
        snprintf(address.sun_path,sizeof(address.sun_path),"%s/.darlingserver.sock",prefix);
        rpc=sendto(fd,".",1,0,(sockaddr*)&address,sizeof(address));close(fd);byteWrite(releaseWrite);
    }
    int status;while(waitpid(server,&status,0)<0&&errno==EINTR){}
    std::string marker=std::string(prefix)+"/launched",socket=std::string(prefix)+"/.darlingserver.sock";
    bool launched=access(marker.c_str(),F_OK)==0,remaining=access(socket.c_str(),F_OK)==0;
    int serverExit=WIFEXITED(status)?WEXITSTATUS(status):-1;
    printf("mode=%s ready=%d ready_errno=%d rpc=%d server=%d launched=%d socket_remaining=%d\n",
        argv[1],readyOK,readyError,rpc,serverExit,launched,remaining);
    unlink(marker.c_str());unlink(socket.c_str());rmdir(prefix);
    if(testMode=="success")return readyOK&&rpc==1&&serverExit==0&&launched&&!remaining?0:1;
    if(testMode=="namespace-eof")return !readyOK&&readyError==EPIPE&&serverExit==1&&!launched&&!remaining?0:1;
    return serverExit==1&&!launched&&!remaining?0:1;
}
'''
code=(header.replace('SERVER_HEADER',str(base/'src/startup-handshake.hpp'))
      .replace('CHILD_PREFIX',child_prefix).replace('CHILD_NOTIFY',notify)
      .replace('CHILD_AWAIT',await_green).replace('PARENT',parent))
code=code.replace('ORDER_BEFORE','true' if order_before else 'false')
records=[]
with tempfile.TemporaryDirectory(prefix='qv-startup-tests-') as temporary:
    temporary=Path(temporary)
    native=temporary/'controls.cpp';native.write_text(code)
    compiler=shlex.split(os.environ.get('CXX','c++'))
    binary=temporary/'controls'
    subprocess.run(compiler+['-std=c++17','-O0',str(native),'-o',str(binary)],check=True)
    modes=['ordering'] if args.order_only else ['ordering','success','cancel','namespace-eof','green-eof','inherit-eof','timeout-control','orphan-control']
    for mode in modes:
        result,expired,cleaned,ready_seen,strays=run_control([str(binary),mode],timeout=0.1 if mode=='timeout-control' else 10,cwd=temporary,ready_marker=b'TIMEOUT_CHILD_READY\n' if mode in ('timeout-control','orphan-control') else None)
        passed=expired and cleaned and ready_seen if mode=='timeout-control' else not expired and cleaned and not strays and result.returncode==0
        if mode=='orphan-control':passed=not expired and cleaned and ready_seen and strays and result.returncode==0
        if args.expect_premature_ready:
            passed=order_before and not expired and cleaned and not strays and result.returncode==1 and result.stdout=='ready=1 first=-1 errno=2 later=1 helper=0\n'
        records.append(dict(mode=mode,exit=result.returncode,stdout=result.stdout,stderr=result.stderr,timed_out=expired,cleaned=cleaned,child_ready=ready_seen,unexpected_children=strays,passed=passed))
    if not args.order_only:
        io_binary=temporary/'io-controls'
        subprocess.run(compiler+['-std=c++17','-O0',str(base/'tests/startup-handshake-io.cpp'),'-o',str(io_binary)],check=True)
        result=subprocess.run([str(io_binary)],text=True,capture_output=True,timeout=10)
        records.append(dict(mode='syscall-responses',exit=result.returncode,stdout=result.stdout,stderr=result.stderr,passed=result.returncode==0))
print(json.dumps(records,indent=2))
raise SystemExit(0 if all(record['passed'] for record in records) else 1)
