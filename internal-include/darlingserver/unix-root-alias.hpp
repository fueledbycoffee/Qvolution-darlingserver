#ifndef DARLINGSERVER_UNIX_ROOT_ALIAS_HPP
#define DARLINGSERVER_UNIX_ROOT_ALIAS_HPP
#include <darlingserver/utility.hpp>
#include <memory>
#include <string>
#include <utility>
namespace DarlingServer {
int unixRootAliasProcessID();
// The returned descriptor is owned by the server registry, never by its caller.
std::pair<int, std::string> retainUnixRootAlias(std::shared_ptr<FD> root,
	const std::string& canonicalPath);
}
#endif
