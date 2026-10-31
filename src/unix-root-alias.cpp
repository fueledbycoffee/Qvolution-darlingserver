// Original reversible UNIX-path support. No host filesystem aliases are created.
#include <darlingserver/unix-root-alias.hpp>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <map>
#include <mutex>
#include <tuple>
#include <system_error>
#include <climits>

int DarlingServer::unixRootAliasProcessID() {
	char target[32];
	ssize_t count = readlink("/proc/self", target, sizeof(target));
	if (count <= 0 || static_cast<size_t>(count) >= sizeof(target))
		throw std::system_error(count < 0 ? errno : EINVAL, std::generic_category(), "resolve proc-visible server pid");
	int result = 0;
	for (ssize_t i = 0; i < count; i++) {
		if (target[i] < '0' || target[i] > '9' || result > (INT_MAX - (target[i] - '0')) / 10)
			throw std::system_error(EINVAL, std::generic_category(), "invalid proc-visible server pid");
		result = result * 10 + target[i] - '0';
	}
	if (result <= 0)
		throw std::system_error(EINVAL, std::generic_category(), "invalid proc-visible server pid");
	return result;
}

std::pair<int, std::string> DarlingServer::retainUnixRootAlias(std::shared_ptr<FD> root,
	const std::string& canonicalPath) {
	if (!root || root->fd() < 0 || canonicalPath.empty() || canonicalPath[0] != '/')
		throw std::system_error(EINVAL, std::generic_category(), "invalid virtual root");
	struct stat info;
	if (fstat(root->fd(), &info) < 0)
		throw std::system_error(errno, std::generic_category(), "stat virtual root");
	if (!S_ISDIR(info.st_mode))
		throw std::system_error(ENOTDIR, std::generic_category(), "virtual root is not a directory");
	char link[4096];
	std::string procPath = "/proc/self/fd/" + std::to_string(root->fd());
	ssize_t count = readlink(procPath.c_str(), link, sizeof(link));
	if (count < 0)
		throw std::system_error(errno, std::generic_category(), "resolve virtual root");
	if (static_cast<size_t>(count) >= sizeof(link) || std::string(link, count) != canonicalPath)
		throw std::system_error(ESTALE, std::generic_category(), "virtual root path changed");

	using Key = std::tuple<dev_t, ino_t, std::string>;
	static std::mutex lock;
	static std::map<Key, std::shared_ptr<FD>> roots;
	std::lock_guard guard(lock);
	Key key(info.st_dev, info.st_ino, canonicalPath);
	auto found = roots.find(key);
	if (found != roots.end())
		return {found->second->fd(), canonicalPath};
	// Entries cannot be evicted while kernel socket addresses may refer to them.
	// Bound namespace resource use; retain successful entries until server exit.
	if (roots.size() >= 256)
		throw std::system_error(EMFILE, std::generic_category(), "virtual root alias limit");
	FD duplicate(fcntl(root->fd(), F_DUPFD_CLOEXEC, 3));
	if (duplicate.fd() < 0)
		throw std::system_error(errno, std::generic_category(), "retain virtual root");
	auto owner = std::make_shared<FD>(std::move(duplicate));
	roots.emplace(std::move(key), owner);
	return {owner->fd(), canonicalPath};
}
