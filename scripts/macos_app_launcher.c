#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <mach-o/dyld.h>

int main(void) {
    char exe_path[PATH_MAX];
    uint32_t size = sizeof(exe_path);

    if (_NSGetExecutablePath(exe_path, &size) != 0) {
        return 1;
    }

    char root[PATH_MAX];
    snprintf(root, sizeof(root), "%s", exe_path);

    for (int i = 0; i < 4; i++) {
        char *slash = strrchr(root, '/');
        if (slash == NULL) {
            return 1;
        }
        *slash = '\0';
    }

    if (chdir(root) != 0) {
        return 1;
    }

    execl("/usr/bin/python3", "python3", "launcher_web.py", (char *)NULL);
    return 1;
}
