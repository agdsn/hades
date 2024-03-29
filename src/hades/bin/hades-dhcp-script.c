/* SPDX-License-Identifier: MIT */
#include <stdbool.h>
#include <stddef.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <limits.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <unistd.h>
#include <errno.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <sysexits.h>

#include "config.h"

extern char **environ;

#define DNSMASQ_PREFIX "DNSMASQ_"
#define SOCKET_OPTION "HADES_DHCP_SCRIPT_SOCKET"
#define SOCKET_OPTION_EQ SOCKET_OPTION "="

#define CHECK(expr) \
    ({ \
        errno = 0; \
        __auto_type __result = (expr); \
        int __errno = errno; \
        long long __code = __result; \
        if (__result < 0) { \
            fprintf( \
                stderr, \
                "%s at %s:%d returned %lld: %s [errno=%d]\n", \
                #expr, \
                __FILE__, \
                __LINE__, \
                __code, \
                strerror(__errno), \
                __errno \
            ); \
        } \
        __result; \
    })


#define XFAIL(expr) \
    ({ \
        __auto_type __result = CHECK(expr); \
        if (__result < 0) { \
            exit(EX_OSERR); \
        } \
        __result; \
    })

static void print_usage(void) {
    fputs(
        "hades-dhcp-script ARGS...\n"
        "\n"
        "Sends its command-line arguments, environment variables starting\n"
        "with DNSMASQ_ and the stdin/stdout file descriptors to the UNIX\n"
        "socket set via the " SOCKET_OPTION " environment\n"
        "variable (see `systemctl list-units hades-\\*.socket` for running lease-server sockets).\n"
        "\n"
        "Use the `init` command to print out the current state of leases.\n"
        "See the -6, --dhcp-script options of dnsmasq for details.\n",
        stderr
    );
}

static size_t gather(size_t iov_max, struct iovec (*iovs)[iov_max], char *strings[]) {
    size_t iov_idx = 0;

    // Gather contiguous strings
    for (char *start = *strings; *strings;) {
        char *end = strchr(*strings, '\0');

        if (end + 1 != *(++strings)) {
            if (iov_idx < iov_max) {
                (*iovs)[iov_idx] = (struct iovec) { start, end + 1 - start, };
            }
            iov_idx++;
            start = *strings;
        }
    }

    return iov_idx;
}

static char buffer[4096];
static struct iovec iovs[IOV_MAX];

/**
 * Lightweight proxy for dnsmasq --dhcp-script invocations.
 *
 * Sends its arguments, environment variables and file descriptors over a UNIX
 * socket to a server. See the server for a detailed description of the
 * protocol.
 *
 * Idea: Let the kernel gather the different pieces of data via iovec, instead
 * of collecting it ourselves in a temporary buffer.
 */
int main(int _argc, char *argv[]) {
    if (_argc < 2) {
        print_usage();
        return EX_USAGE;
    }
    unsigned int argc = _argc;

    if (strcmp("-h", argv[1]) == 0
        || strcmp("--help", argv[1]) == 0
        || strcmp("help", argv[1]) == 0
    ) {
        print_usage();
        return EX_OK;
    }

    const char *path = NULL;
    // Find socket path and count environment variables
    unsigned int envc;
    for (envc = 0; environ[envc]; envc++) {
        if (strncmp(SOCKET_OPTION_EQ, environ[envc], strlen(SOCKET_OPTION_EQ)) == 0) {
            path = environ[envc] + strlen(SOCKET_OPTION_EQ);
        }
    }
    if (!path) {
        fprintf(
            stderr, "You need to set the " SOCKET_OPTION " environment variable!\n"
            "Check `systemctl list-units hades-\\*.socket` for running lease-server sockets.\n"
        );
        return EX_USAGE;
    }

    struct sockaddr_un addr = { .sun_family = AF_UNIX };
    size_t path_len = strlen(path);
    if (path_len + 1 >= sizeof(addr.sun_path)) {
        fprintf(
            stderr, "The " SOCKET_OPTION " path\n%s\n is too long: %zu > %zu",
            path, path_len, sizeof(addr.sun_path) - 1
        );
        return EX_USAGE;
    }
    memcpy(addr.sun_path, path, path_len + 1);
    int fd = XFAIL(socket(addr.sun_family, SOCK_STREAM | SOCK_CLOEXEC, 0));

    if (CHECK(connect(fd, (struct sockaddr *) &addr, sizeof(addr)))) {
        fprintf(
            stderr,
            "Tried socket path: %s.\nHave you forgotten to start the lease server?\n",
            addr.sun_path
        );
        return EX_OSERR;
    }

    size_t iov_idx = 0;
    size_t iov_max = sizeof(iovs)/sizeof(iovs[0]);

    // Gather argc
    if (iov_idx >= iov_max) {
        fprintf(stderr, "Too many iovec to send (maximum %zu)", iov_max);
        return EX_DATAERR;
    }
    iovs[iov_idx++] = (struct iovec) { &argc, sizeof(argc), };
    iov_idx += gather(iov_max - iov_idx, (struct iovec (*)[])&iovs[iov_idx], argv);
    if (iov_idx >= iov_max) {
        fprintf(stderr, "Too many iovec to send (maximum %zu)", iov_max);
        return EX_DATAERR;
    }

    // Gather envc
    if (iov_idx >= iov_max) {
        fprintf(stderr, "Too many iovec to send (maximum %zu)", iov_max);
        return EX_DATAERR;
    }
    iovs[iov_idx++] = (struct iovec) { &envc, sizeof(envc), };
    iov_idx += gather(iov_max - iov_idx, (struct iovec (*)[])&iovs[iov_idx], environ);
    if (iov_idx >= iov_max) {
        fprintf(stderr, "Too many iovec to send (maximum %zu)", iov_max);
        return EX_DATAERR;
    }

    // Prepare file descriptor passing
    int fds[] = {STDIN_FILENO, STDOUT_FILENO, STDERR_FILENO};
    union {
        char   align[CMSG_SPACE(sizeof(fds))];
        struct cmsghdr hdr;
    } cmsg = {
        .hdr = {
            .cmsg_level = SOL_SOCKET,
            .cmsg_type = SCM_RIGHTS,
            .cmsg_len = CMSG_LEN(sizeof(fds)),
        },
    };
    memcpy(CMSG_DATA(&cmsg.hdr), &fds, sizeof(fds));

    size_t iov_cnt = iov_idx;
    iov_idx = 0;
    struct msghdr msg = {
        .msg_name = NULL,
        .msg_namelen = 0,
        .msg_iov = &iovs[iov_idx],
        .msg_iovlen = iov_cnt,
        .msg_control = &cmsg.hdr,
        .msg_controllen = sizeof(cmsg.align),
        .msg_flags = 0,
    };

    do {
        ssize_t rc = XFAIL(sendmsg(fd, &msg, 0));

        // Handle partial sendmsg
        for (size_t sent = rc; iov_idx < iov_cnt; iov_idx++) {
            if (sent >= iovs[iov_idx].iov_len) {
                sent -= iovs[iov_idx].iov_len;
                iovs[iov_idx].iov_base = NULL;
                iovs[iov_idx].iov_len = 0;
            } else {
                iovs[iov_idx].iov_base += sent;
                iovs[iov_idx].iov_len -= sent;
                break;
            }
        }

        msg.msg_iov = &iovs[iov_idx];
        msg.msg_iovlen = iov_cnt - iov_idx;
        // Sent ancillary data only once
        msg.msg_control = NULL;
        msg.msg_controllen = 0;
    } while (iov_idx < iov_cnt);

    // Indicate that we finished sending data on the socket level
    XFAIL(shutdown(fd, SHUT_WR));

    // Wait for the remote side to close the connection
    size_t received = 0;
    do {
        ssize_t l = XFAIL(recv(fd, buffer, sizeof(buffer), 0));

        if (l == 0) {
            break;
        } else {
            received += l;
        }
    } while (received < 1);

    if (received != 1) {
        fprintf(
            stderr,
            "Received unexpected number of bytes: %zu bytes\n",
            received
        );
        return EX_DATAERR;
    }

    XFAIL(close(fd));

    return buffer[0];
}
