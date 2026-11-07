// Compiled by tests/run-overlay-option-path.sh together with isValidOverlayOptionPath, which the script
// extracts from src/darlingserver.cpp. The call-site check is done by the script on the source text.
#include <cstdio>
#include <string>
#include <vector>

static bool isValidOverlayOptionPath(const char* path);
#include "extracted.inc"

// Splits an overlayfs option string the way the kernel does for the keys that matter here:
// ',' separates options (a backslash escapes the next character), ':' separates lowerdir layers.
static std::vector<std::string> optionKeys(const std::string& opts, size_t* lowerLayers) {
	std::vector<std::string> keys;
	std::string cur;
	for (size_t i = 0; i <= opts.size(); ++i) {
		if (i == opts.size() || opts[i] == ',') {
			size_t eq = cur.find('=');
			keys.push_back(cur.substr(0, eq));
			if (cur.compare(0, 9, "lowerdir=") == 0) {
				size_t n = 1;
				for (char c : cur) n += c == ':';
				*lowerLayers = n;
			}
			cur.clear();
		} else if (opts[i] == '\\' && i + 1 < opts.size()) {
			cur += opts[++i];
		} else {
			cur += opts[i];
		}
	}
	return keys;
}

static int failures = 0;
#define CHECK(cond, what) do { if (!(cond)) { printf("FAIL: %s\n", what); ++failures; } } while (0)

int main() {
	const char* accepted[] = { "/usr/local/libexec", "/opt/dar ling/x", "/a=b/c", "/home/u/.darling", "/\xc3\xa9t\xc3\xa9" };
	for (const char* p : accepted) {
		CHECK(isValidOverlayOptionPath(p), p);
		size_t layers = 0;
		auto keys = optionKeys(std::string("lowerdir=") + p + ",upperdir=/proc/self/fd/3,workdir=/proc/self/fd/4", &layers);
		CHECK(keys.size() == 3 && keys[0] == "lowerdir" && keys[1] == "upperdir" && keys[2] == "workdir" && layers == 1,
			"accepted path keeps the option layout");
	}
	const char* rejected[] = { "/x,upperdir=/etc", "/x:/y", "/x\\,y", "/x\ny", "/x\ty", "/x\x7f" , "/x\\" };
	for (const char* p : rejected) {
		CHECK(!isValidOverlayOptionPath(p), "rejected path");
	}
	// Show why the rejected ones matter: each changes the parsed layout.
	size_t layers = 0;
	auto keys = optionKeys("lowerdir=/x,upperdir=/etc,upperdir=/proc/self/fd/3,workdir=/proc/self/fd/4", &layers);
	CHECK(keys.size() == 4, "parser model sees an injected option");
	layers = 0;
	optionKeys("lowerdir=/x:/y,upperdir=/proc/self/fd/3,workdir=/proc/self/fd/4", &layers);
	CHECK(layers == 2, "parser model sees an injected layer");
	printf(failures ? "%d failure(s)\n" : "all checks passed\n", failures);
	return failures != 0;
}
