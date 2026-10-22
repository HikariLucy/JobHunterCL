/* Trusted, bounded synthetic probes only. Never execute outside Bubblewrap.
 * No compiler, shell, downloads, user-provided source or arbitrary commands.
 */
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <netinet/in.h>
#include <sched.h>
#include <signal.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/prctl.h>
#include <sys/resource.h>
#include <sys/socket.h>
#include <sys/statvfs.h>
#include <sys/un.h>
#include <unistd.h>

#define CHECK(x) do { if (!(x)) { fprintf(stderr, "failed line %d errno %d\n", __LINE__, errno); return 1; } } while (0)

static int denied_read(const char *path) {
    int fd = open(path, O_RDONLY);
    if (fd >= 0) { close(fd); return 0; }
    return errno == ENOENT || errno == EACCES;
}
static int denied_write(const char *path) {
    int fd = open(path, O_WRONLY | O_CREAT, 0600);
    if (fd >= 0) { close(fd); return 0; }
    return errno == EROFS || errno == ENOENT || errno == EACCES || errno == ETXTBSY;
}
static int unix_denied(const char *path, int abstract) {
    int fd = socket(AF_UNIX, SOCK_STREAM | SOCK_CLOEXEC, 0);
    if (fd < 0) return 0;
    struct sockaddr_un addr = {.sun_family = AF_UNIX};
    size_t n = strlen(path);
    if (n + 1 >= sizeof(addr.sun_path)) { close(fd); return 0; }
    memcpy(addr.sun_path + (abstract ? 1 : 0), path, n + 1);
    int rc = connect(fd, (struct sockaddr *)&addr,
                     offsetof(struct sockaddr_un, sun_path) + n + 1);
    int saved = errno;
    close(fd);
    return rc == -1 && (saved == ENOENT || saved == ECONNREFUSED || saved == EACCES);
}
int main(int argc, char **argv) {
    CHECK(argc == 2);
    const char *scenario = argv[1];
    if (!strcmp(scenario, "basic")) {
        CHECK(prctl(PR_GET_NO_NEW_PRIVS, 0, 0, 0, 0) == 1);
        CHECK(unshare(CLONE_NEWUSER) == -1 && (errno == EPERM || errno == ENOSPC));
        CHECK(getenv("HOME") == NULL);
        for (int fd = 3; fd < 64; fd++) CHECK(fcntl(fd, F_GETFD) == -1 && errno == EBADF);
        const char *names[] = {"user", "pid", "net", "ipc", "uts", "cgroup"};
        const char *envs[] = {"USER", "PID", "NET", "IPC", "UTS", "CGROUP"};
        for (int i = 0; i < 6; i++) {
            char path[64], ns[80] = {0}, env[64];
            snprintf(path, sizeof(path), "/proc/self/ns/%s", names[i]);
            snprintf(env, sizeof(env), "FIXTURE_NS_%s", envs[i]);
            CHECK(readlink(path, ns, sizeof(ns)-1) > 0);
            CHECK(strcmp(ns, getenv(env)) != 0);
        }
        FILE *status = fopen("/proc/self/status", "r");
        char line[256]; int caps = 0;
        CHECK(status != NULL);
        while (fgets(line, sizeof(line), status)) {
            if (!strncmp(line, "CapEff:", 7) || !strncmp(line, "CapPrm:", 7) ||
                !strncmp(line, "CapBnd:", 7)) {
                CHECK(strtoull(line + 7, NULL, 16) == 0); caps++;
            }
        }
        fclose(status); CHECK(caps == 3);
    } else if (!strcmp(scenario, "filesystem")) {
        char buf[32] = {0};
        int fd = open("/input", O_RDONLY);
        CHECK(fd >= 0 && read(fd, buf, sizeof(buf)) == 16);
        close(fd);
        CHECK(!strcmp(buf, "synthetic-input\n"));
        CHECK(denied_read(getenv("FIXTURE_HIDDEN")));
        CHECK(denied_read("/home") && denied_read("/run/host.sock"));
        struct statvfs mount;
        CHECK(!statvfs("/", &mount) && (mount.f_flag & ST_RDONLY));
        CHECK(!statvfs("/input", &mount) && (mount.f_flag & ST_RDONLY));
        CHECK(!statvfs("/probe", &mount) && (mount.f_flag & ST_RDONLY));
        CHECK(denied_write("/input") && denied_write("/probe"));
        CHECK(denied_write("/outside") && denied_write("/tmp/outside"));
        CHECK(denied_write("/proc/fixture"));
        fd = open("/out/result", O_WRONLY | O_CREAT | O_EXCL, 0600);
        CHECK(fd >= 0 && write(fd, "ok", 2) == 2);
        close(fd);
    } else if (!strcmp(scenario, "network")) {
        /* Only connect to an innocuous disposable host loopback listener.
         * Never probe an external address or a preexisting host service. */
        int fd = socket(AF_INET, SOCK_STREAM | SOCK_CLOEXEC, 0);
        CHECK(fd >= 0);
        struct sockaddr_in addr = {.sin_family = AF_INET,
            .sin_addr.s_addr = htonl(INADDR_LOOPBACK),
            .sin_port = htons(atoi(getenv("FIXTURE_PORT")))};
        CHECK(connect(fd, (struct sockaddr *)&addr, sizeof(addr)) == -1 && errno == ECONNREFUSED);
        close(fd);
        CHECK(unix_denied(getenv("FIXTURE_SOCKET"), 0));
        CHECK(unix_denied(getenv("FIXTURE_ABSTRACT"), 1));
        /* The host network namespace inode was supplied by the harness. */
        char ns[80] = {0};
        CHECK(readlink("/proc/self/ns/net", ns, sizeof(ns)-1) > 0);
        CHECK(strcmp(ns, getenv("FIXTURE_NETNS")) != 0);
        FILE *routes = fopen("/proc/net/route", "r");
        char line[512];
        CHECK(routes != NULL);
        CHECK(fgets(line, sizeof(line), routes) != NULL);
        CHECK(fgets(line, sizeof(line), routes) == NULL);
        fclose(routes);
    } else if (!strcmp(scenario, "limits")) {
        struct rlimit lim;
        CHECK(!getrlimit(RLIMIT_CPU, &lim) && lim.rlim_cur == 2 && lim.rlim_max == 2);
        CHECK(!getrlimit(RLIMIT_NPROC, &lim) && lim.rlim_cur == 4096 && lim.rlim_max == 4096);
        CHECK(!getrlimit(RLIMIT_NOFILE, &lim) && lim.rlim_cur == 64 && lim.rlim_max == 64);
        CHECK(!getrlimit(RLIMIT_AS, &lim) && lim.rlim_cur == 134217728 && lim.rlim_max == 134217728);
        CHECK(!getrlimit(RLIMIT_FSIZE, &lim) && lim.rlim_cur == 2097152 && lim.rlim_max == 2097152);
        CHECK(!getrlimit(RLIMIT_CORE, &lim) && !lim.rlim_cur && !lim.rlim_max);
        CHECK(malloc(192 * 1024 * 1024) == NULL);
        int fd;
        while ((fd = open("/input", O_RDONLY)) >= 0) { /* <= 61 opens */ }
        CHECK(errno == EMFILE);
    } else if (!strcmp(scenario, "quota")) {
        struct statvfs fs;
        CHECK(!statvfs("/out", &fs) && fs.f_blocks * fs.f_frsize <= 1048576);
        char buf[4096] = {0};
        /* Multiple files: demonstrate aggregate bytes rather than FSIZE. */
        int total = 0, full = 0;
        for (int i = 0; i < 8 && !full; i++) {
            char path[40]; snprintf(path, sizeof(path), "/out/quota-%d", i);
            int fd = open(path, O_CREAT | O_WRONLY, 0600);
            CHECK(fd >= 0);
            for (int j = 0; j < 64; j++) {
                ssize_t n = write(fd, buf, sizeof(buf));
                if (n < 0) { CHECK(errno == ENOSPC); full = 1; break; }
                total += n;
            }
            close(fd);
        }
        CHECK(full && total <= 1048576);
    } else if (!strcmp(scenario, "cpu")) {
        for (;;) { /* <= 2 CPU seconds, external wall timeout 3 seconds */ }
    } else if (!strcmp(scenario, "timeout") || !strcmp(scenario, "descendant")) {
        if (!strcmp(scenario, "descendant")) {
            pid_t pid = fork(); /* One child, never a fork bomb. */
            CHECK(pid >= 0);
            if (pid == 0) {
                CHECK(setsid() != -1);
                puts("child-ready"); fflush(stdout);
                sleep(30); /* Inherited stdout detects survivors after kill. */
                return 99;
            }
        }
        puts("parent-ready"); fflush(stdout);
        sleep(30);
        return 99;
    } else { return 2; }
    printf("ok:%s\n", scenario);
    return 0;
}
