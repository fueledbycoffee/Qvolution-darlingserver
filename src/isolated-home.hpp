#pragma once

#include <cerrno>
#include <fcntl.h>
#include <initializer_list>
#include <sys/stat.h>
#include <unistd.h>

// Resolve every component through directory descriptors; never follow a host link.
static int isolatedHomeDirectory(int parent, const char* name)
{
	if (mkdirat(parent, name, 0755) != 0 && errno != EEXIST)
		return -1;
	return openat(parent, name, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
}

static bool setupIsolatedHome(const char* prefix, const char* login)
{
	int parent = open(prefix, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
	if (parent < 0)
		return false;
	for (const char* name : { "Users", login }) {
		int child = isolatedHomeDirectory(parent, name);
		int error = errno;
		close(parent);
		if (child < 0) {
			errno = error;
			return false;
		}
		parent = child;
	}
	for (const char* name : { "Documents", "Desktop", "Downloads", "Movies", "Music", "Pictures", "Public" }) {
		int child = isolatedHomeDirectory(parent, name);
		if (child < 0) {
			int error = errno;
			close(parent);
			errno = error;
			return false;
		}
		close(child);
	}
	close(parent);
	return true;
}
