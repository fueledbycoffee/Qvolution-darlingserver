#ifndef DARLINGSERVER_STARTUP_HANDSHAKE_HPP
#define DARLINGSERVER_STARTUP_HANDSHAKE_HPP

#include <errno.h>
#include <sys/socket.h>
#include <unistd.h>

static bool startupReadByte(int fd) {
	char byte;
	ssize_t count;
	do {
		count = read(fd, &byte, 1);
	} while (count < 0 && errno == EINTR);
	if (count == 1 && byte == '.')
		return true;
	if (count >= 0)
		errno = count == 0 ? EPIPE : EPROTO;
	return false;
}

// The pipe caller ignores SIGPIPE; socket notifications suppress it per send.
static bool startupWriteByte(int fd, bool socket = false) {
	ssize_t count;
	do {
		count = socket ? send(fd, ".", 1, MSG_NOSIGNAL) : write(fd, ".", 1);
	} while (count < 0 && errno == EINTR);
	if (count == 1)
		return true;
	if (count >= 0)
		errno = EIO;
	return false;
}

#endif
