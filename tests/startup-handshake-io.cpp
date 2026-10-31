#include <errno.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>
#include <sys/socket.h>
#include <unistd.h>
static int mode, calls, sendFlags;
static ssize_t controlledRead(int, void *value, size_t) {
    ++calls;
    if(mode==1 && calls==1){errno=EINTR;return -1;}
    if(mode==2)return 0;
    if(mode==3){errno=EIO;return -1;}
    *(char*)value=mode==4?'!':'.';return 1;
}
static ssize_t controlledWrite(int, const void*,size_t) {
    ++calls;
    if(mode==1 && calls==1){errno=EINTR;return -1;}
    if(mode==2)return 0;
    if(mode==3){errno=EPIPE;return -1;}
    return 1;
}
static ssize_t controlledSend(int fd,const void *value,size_t length,int flags) {
    sendFlags=flags;return controlledWrite(fd,value,length);
}
#define read controlledRead
#define write controlledWrite
#define send controlledSend
#include "../src/startup-handshake.hpp"
#undef read
#undef write
#undef send
int main(){
    bool ok=true;
    for(mode=0;mode<5;++mode){
        calls=0;errno=0;
        bool result=startupReadByte(1);
        bool expected=mode<2;
        int expectedError=mode==2?EPIPE:mode==3?EIO:mode==4?EPROTO:0;
        bool passed=result==expected&&calls==(mode==1?2:1)&&(!expectedError||errno==expectedError);
        printf("read-helper=server mode=%d result=%d calls=%d errno=%d pass=%d\n",mode,result,calls,errno,passed);
        ok&=passed;
    }
    for(int socket=0;socket<2;++socket){
        for(mode=0;mode<4;++mode){
            calls=0;sendFlags=0;errno=0;
            bool result=startupWriteByte(1,socket);
            bool expected=mode<2;
            int expectedError=mode==2?EIO:mode==3?EPIPE:0;
            bool passed=result==expected&&calls==(mode==1?2:1)&&(!expectedError||errno==expectedError)&&(!socket||sendFlags==MSG_NOSIGNAL);
            printf("write-helper=%s mode=%d result=%d calls=%d errno=%d pass=%d\n",socket?"socket":"pipe",mode,result,calls,errno,passed);
            ok&=passed;
        }
    }
    return ok?0:1;
}
