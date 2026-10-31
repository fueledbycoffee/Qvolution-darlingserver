// Original test of the actual production registry/RAII implementation, no RPC stub.
#include <darlingserver/unix-root-alias.hpp>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <system_error>
#include <vector>
int main(){
 char first[]="/tmp/qv-root-registry-XXXXXX";assert(mkdtemp(first));
 auto root=std::make_shared<DarlingServer::FD>(open(first,O_RDONLY|O_DIRECTORY|O_CLOEXEC));assert(root->fd()>=0);
 auto retained=DarlingServer::retainUnixRootAlias(root,first);int alias=retained.first;assert(alias!=root->fd());assert(fcntl(alias,F_GETFD)&FD_CLOEXEC);
 root.reset();assert(fcntl(alias,F_GETFD)>=0); // Original owner destruction does not invalidate the alias.
 auto again=std::make_shared<DarlingServer::FD>(open(first,O_RDONLY|O_DIRECTORY|O_CLOEXEC));assert(DarlingServer::retainUnixRootAlias(again,first).first==alias);again.reset();
 char proc[100];snprintf(proc,sizeof proc,"/proc/%ld/fd/%d/marker",(long)DarlingServer::unixRootAliasProcessID(),alias);int marker=open(proc,O_CREAT|O_EXCL|O_WRONLY,0600);assert(marker>=0);assert(write(marker,"Q",1)==1);close(marker);
 std::string full=std::string(first)+"/marker";int original=open(full.c_str(),O_RDONLY);char byte=0;assert(original>=0&&read(original,&byte,1)==1&&byte=='Q');close(original);unlink(full.c_str());
 bool stale=false;try{DarlingServer::retainUnixRootAlias(std::make_shared<DarlingServer::FD>(dup(alias)),std::string(first)+"-wrong");}catch(const std::system_error&e){stale=e.code().value()==ESTALE;}assert(stale);
 std::string renamed=std::string(first)+"-renamed";assert(rename(first,renamed.c_str())==0);stale=false;try{DarlingServer::retainUnixRootAlias(std::make_shared<DarlingServer::FD>(dup(alias)),first);}catch(const std::system_error&e){stale=e.code().value()==ESTALE;}assert(stale);assert(rename(renamed.c_str(),first)==0);
 bool notDirectory=false;try{DarlingServer::retainUnixRootAlias(std::make_shared<DarlingServer::FD>(open("/dev/null",O_RDONLY)),"/dev/null");}catch(const std::system_error&e){notDirectory=e.code().value()==ENOTDIR;}assert(notDirectory);
 std::vector<std::string> owned{first};
 for(int i=0;i<256;i++){
  char next[]="/tmp/qv-root-registry-XXXXXX";assert(mkdtemp(next));owned.emplace_back(next);auto item=std::make_shared<DarlingServer::FD>(open(next,O_RDONLY|O_DIRECTORY|O_CLOEXEC));
  bool limit=false;try{auto other=DarlingServer::retainUnixRootAlias(item,next);assert(other.first!=alias);}catch(const std::system_error&e){assert(e.code().value()==EMFILE);limit=true;}
  if(limit){assert(i==255);break;}assert(i<255);
 }
 for(auto&path:owned)assert(rmdir(path.c_str())==0);
 assert(fcntl(alias,F_GETFD)>=0); // Registry owns descriptors until server exit, no eviction.
 puts("PASS: actual root registry lifetime, canonical identity, dedup, CLOEXEC and bounded capacity");
}
