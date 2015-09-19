import collections
import enum
from functools import partial
import grp
import logging
import os
import pwd
import select
import signal
import socket
import sys
import time

import netaddr

from hades.config.loader import get_config, CheckWrapper

logger = logging.getLogger(__name__)


def drop_privileges(passwd, group):
    if os.geteuid() != 0:
        logger.error("Can't drop privileges (EUID != 0)")
        return
    os.setgid(group.gr_gid)
    os.initgroups(passwd.pw_name, group.gr_gid)
    os.setuid(passwd.pw_uid)


def send_reload(config):
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    conn = client.connect(config['HADES_DNSMASQ_MONITOR_SOCKET'])
    conn.send(signal.SIGHUP)
    result = conn.recv(1)
    conn.close()
    client.close()
    return result == b'\x00'


class SignalProxyClient(object):
    def __init__(self, sockfile):
        self.sockfile = sockfile
        self.conn = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.conn.connect(self.sockfile)

    def send_signal(self, signo, timeout=None):
        prev_timeout = self.conn.gettimeout()
        self.conn.settimeout(timeout)
        sent = self.conn.send(signo.to_bytes(1, sys.byteorder))
        self.conn.settimeout(prev_timeout)
        data = self.conn.recv(1)
        return data == b'0'

    def close(self):
        self.conn.close()


def generate_dhcp_host_reservations(hosts):
    for mac, ip in hosts:
        try:
            mac = netaddr.EUI(mac, dialect=netaddr.mac_unix_expanded)
        except netaddr.AddrFormatError:
            logger.error("Invalid MAC address %s", mac)
            continue
        try:
            ip = netaddr.IPAddress(ip)
        except netaddr.AddrFormatError:
            logger.error("Invalid IP address %s", ip)
            continue
        yield "{0},{1}\n".format(mac, ip)


def main():
    if len(sys.argv) < 2:
        print("No config file specified")
        sys.exit(os.EX_USAGE)
    logger.info("dnsmasq monitor")
    conf_file = sys.argv[1]
    config = CheckWrapper(get_config())
    passwd = pwd.getpwnam(config['HADES_REGULAR_DNSMASQ_USER'])
    group = grp.getgrnam(config['HADES_REGULAR_DNSMASQ_GROUP'])
    sockfile = config['HADES_REGULAR_DNSMASQ_SIGNAL_SOCKET']
    hosts_file = config['HADES_REGULAR_DNSMASQ_HOSTS_FILE']
    if not os.path.exists(hosts_file):
        with open(hosts_file, mode='w'):
            pass
    args = ('dnsmasq', '--conf-file=' + conf_file)
    monitor = SignalProxyDaemon(sockfile, args, restart=True)
    os.chown(sockfile, passwd.pw_uid, group.gr_gid)
    drop_privileges(passwd, group)
    sys.exit(monitor.run())


signame_map = {getattr(signal, name): name for name in dir(signal)
               if name.startswith('SIG') and not name.startswith('SIG_')}


def try_close(file):
    try:
        file.close()
    except OSError:
        logger.exception("Closing file-like object %s failed", file)


def try_close_fd(fd):
    try:
        os.close(fd)
    except OSError:
        logger.exception("Closing file descriptor %d failed", fd)


class DaemonState(enum.Enum):
    started = 0
    running = 1
    stopped = 2


class ShutdownDaemon(Exception):
    def __init__(self, code=0, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.code = code


class CloseConnection(Exception):
    pass


class SignalProxyDaemon(object):
    """
    Forward signals received on a Unix socket to a child daemon.

    Fork off a process that is expected to stay running. A Unix socket is opened
    and listens for incoming connections.
    The protocol is very simple. The client are expected to sent signal numbers
    as bytes and the daemon responds with a single byte.
    The byte is zero if the signal could be delivered successfully and non-zero,
    if any error occurs.

    The processes stdin is mapped to /dev/null, stdout and stderr are left as
    is, all other file descriptors are closed. The working directory is changed
    to '/' unconditionally.
    """
    MAX_CONNECTIONS = 5
    SHUTDOWN_SIGNALS = (signal.SIGHUP, signal.SIGQUIT, signal.SIGINT,
                        signal.SIGTERM)
    sigset = {signal.SIGCHLD, signal.SIGHUP, signal.SIGTERM, signal.SIGQUIT,
              signal.SIGINT}

    def __init__(self, sockfile, args, executable=None, use_path=True, env=None,
                 restart=False):
        """
        Start a new daemon. The child will be started and Unix socket will be
        opened. Connections are not yet accepted, call the run method to start
        handling connection and hand over the program execution to the
        SignalProxyDaemon.
        :param sockfile: Path to the Unix to listen on
        :param Sequence[str] args: Args of the process to exec
        :param str executable: Optional, if given this executable instead of the
        zeroth argument is used as executable.
        :param bool use_path: Use the PATH variable to find the executable,
        defaults to True
        :param dict[str,str] env: If given set the child process's
        environment, otherwise use the environment of the current process.
        :param bool restart: If True, restart the child process if it died,
        otherwise the SignalProxyDaemon will shut itself down, if the child
        dies.
        """
        if not args:
            raise ValueError("Empty argument list")
        if executable is None:
            executable = args[0]
        self.sockfile = sockfile
        self.restart = restart
        self.args = args
        self.executable = executable
        self.use_path = use_path
        self.env = env
        self.last_forkexec = -1

        try:
            options = os.O_CLOEXEC | os.O_NONBLOCK
            self.sig_read_fd, self.sig_write_fd = os.pipe2(options)
            signal.set_wakeup_fd(self.sig_write_fd)
            for signo in self.sigset:
                signal.signal(signo, self._noop_handler)
            logger.info('Listening on %s', sockfile)
            if os.path.exists(sockfile):
                os.unlink(sockfile)
            self.server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.server.bind(sockfile)
            self.server.setblocking(False)
            self.server.listen(0)
            self.poll = select.poll()
            self.connections = {}
            self.pid = self._forkexec()
            self.state = DaemonState.started
        except:
            self._restore_signals()
            self._close_files()
            raise

    def _close_files(self):
        try_close_fd(self.sig_write_fd)
        try_close_fd(self.sig_read_fd)
        try_close(self.server)
        for client in self.connections.values():
            client.close()

    def _noop_handler(self, signo, frame):
        logger.debug("Received signal %s with signal handler",
                     signame_map.get(signo, str(signo)))

    def _forkexec(self):
        if time.monotonic() - self.last_forkexec < 1:
            logger.error("Tried to execute a child less than a second ago")
            raise RuntimeError("Less than a second between last fork/exec")
        self.last_forkexec = time.monotonic()
        pid = os.fork()
        if pid == 0:
            os.chdir('/')
            devnull = os.open(os.devnull, os.O_RDONLY)
            sys.stdin.close()
            os.dup2(devnull, 0)
            sys.stdin = os.fdopen(0)
            os.closerange(3, os.sysconf("SC_OPEN_MAX"))
            self._restore_signals()
            if self.executable == self.args[0]:
                logger.info("Executing %s", ' '.join(self.args))
            else:
                logger.info("Executing %s as %s",
                            self.executable,
                            ' '.join(self.args))
            if self.use_path:
                if self.env is not None:
                    os.execvpe(self.executable, self.args, self.env)
                else:
                    os.execvp(self.executable, self.args)
            else:
                if self.env is not None:
                    os.execve(self.executable, self.args, self.env)
                else:
                    os.execv(self.executable, self.args)
        else:
            return pid

    def _restore_signals(self):
        for signo in self.sigset:
            signal.set_wakeup_fd(-1)
            signal.signal(signo, signal.SIG_DFL)

    def run(self):
        if self.state != DaemonState.started:
            raise RuntimeError("")
        logger.info("Running main event loop")
        self.poll.register(self.server, select.POLLIN)
        self.poll.register(self.sig_read_fd, select.POLLIN)
        self.state = DaemonState.running
        while True:
            try:
                reported = self.poll.poll()
            except InterruptedError:
                continue
            try:
                self.handle_events(reported)
            except OSError:
                logger.exception("Received OSError, shutting down")
                self.shutdown()
                return os.EX_OSERR
            except ShutdownDaemon as e:
                self.shutdown()
                return e.code

    def handle_events(self, reported):
        for fd, eventmask in reported:
            logger.debug("poll() reported %d on fd %d", eventmask, fd)
            if fd == self.server.fileno():
                self.handle_new_connection()
            elif fd == self.sig_read_fd:
                self.handle_signal()
            elif fd in self.connections:
                self.handle_connection(fd, eventmask)
            else:
                logger.error("poll() reported unknown fd %d", fd)

    def __del__(self):
        self.shutdown(in_finalizer=True)

    def handle_new_connection(self):
        try:
            conn, addr = self.server.accept()
        except BlockingIOError:
            logger.exception("poll() reported POLLIN on server socket,"
                             " accept should not have blocked")
            return
        conn_fd = conn.fileno()
        logger.debug("New connection on fd %d", conn_fd)
        connection = ClientConnection(self, conn)
        self.connections[conn_fd] = connection
        logger.info("New connection with id %d", connection.id)
        if len(self.connections) >= self.MAX_CONNECTIONS:
            self.poll.unregister(self.server)

    def handle_connection(self, fd, eventmask):
        connection = self.connections[fd]
        logger.debug("Handling poll event from connection %d", connection.id)
        try:
            connection.handle_poll(eventmask)
        except CloseConnection:
            logger.info("Connection %d disconnected", connection.id)
            self.connections.pop(fd)
            connection.close()
            if len(self.connections) < self.MAX_CONNECTIONS:
                self.poll.register(self.server, select.POLLIN)

    def handle_signal(self):
        raw = os.read(self.sig_read_fd, 1)
        signo = int.from_bytes(raw, sys.byteorder, signed=False)
        signame = signame_map.get(signo, signo)
        logger.info("Received signal %s with wakeup fd", signame)
        if signo == signal.SIGCHLD:
            self.handle_sigchld()
        elif signo in self.SHUTDOWN_SIGNALS:
            raise ShutdownDaemon(code=0)
        else:
            logger.error("Received unknown signal %s", signame)

    def handle_sigchld(self):
        while True:
            pid, status = os.waitpid(-1, os.WNOHANG)
            if pid == 0:
                break
            if pid == self.pid:
                if os.WIFEXITED(status):
                    code = os.WEXITSTATUS(status)
                    logger.fatal("Monitored process exited with status %d",
                                 code)
                    self.handle_child_death()
                elif os.WIFSIGNALED(status):
                    termsig = os.WTERMSIG(status)
                    signame = signame_map.get(termsig, str(termsig))
                    logger.fatal("Monitored process was killed by signal %s",
                                 signame)
                    self.handle_child_death()
                elif os.WIFCONTINUED(status):
                    logger.info("Monitored process continued")
                elif os.WIFSTOPPED(status):
                    logger.info("Monitored process was stopped")
            else:
                logger.warning("Received SIGCHLD for unknown child %d", pid)

    def handle_child_death(self):
        self.pid = None
        if self.restart:
            try:
                self.pid = self._forkexec()
            except (RuntimeError, OSError):
                raise ShutdownDaemon(code=os.EX_SOFTWARE)
        else:
            raise ShutdownDaemon(code=os.EX_SOFTWARE)

    def shutdown(self, timeout=5, in_finalizer=False):
        if self.state == DaemonState.stopped:
            return
        logger.info("Shutting down")
        if not in_finalizer:
            self._restore_signals()
        if self.pid is None:
            return
        logger.info("Sending SIGTERM to monitored process")
        try:
            os.kill(self.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
        except PermissionError:
            logger.error("Can't stop monitored process %d (Permission denied)",
                         self.pid)
            return
        delay = 0.0005
        endtime = time.monotonic() + timeout
        while True:
            if time.monotonic() >= endtime:
                logger.warning()
            try:
                pid, status = os.waitpid(self.pid, os.WNOHANG)
            except ChildProcessError:
                logger.warning("Someone else cleaned up %d", self.pid)
                return
            if pid == self.pid:
                return
            remaining = max(time.monotonic() - endtime, 0)
            delay = min(delay * 2, remaining, .05)
            time.sleep(delay)
        logger.info("Sending SIGKILL to monitored process.")
        try:
            os.kill(self.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        except PermissionError:
            logger.error("Can't stop monitored process %d (Permission denied)",
                         self.pid)
        else:
            try:
                os.waitpid(self.pid, 0)
            except ChildProcessError:
                pass
        return


class ConnectionState(enum.Enum):
    open = 0
    closed = 1


class ClientConnection(object):
    RETURN_OK = 0
    RETURN_INVALID = 1
    RETURN_CHILD_ERROR = 2
    MAX_PENDING_REQUESTS = 1024
    MAX_PENDING_RESPONSES = 1024
    id = 0

    encode = partial(int.to_bytes, length=1, byteorder=sys.byteorder)
    decode = partial(int.from_bytes, byteorder=sys.byteorder)

    def __init__(self, proxy, conn):
        self.id = ClientConnection.id
        ClientConnection.id += 1
        self.proxy = proxy
        self.poll = proxy.poll
        self.conn = conn
        self.conn.setblocking(False)
        self.poll.register(conn, select.POLLIN)
        # We do not set maxlen on the deques, as this would silently drop
        # requests/responses if there are bugs in our MAX_PENDING_* checks
        self.pending_requests = collections.deque()
        self.pending_responses = collections.deque()
        self.state = ConnectionState.open

    def handle_poll(self, eventmask):
        if self.state != ConnectionState.open:
            raise RuntimeError("Connection is not open")
        if select.POLLHUP & eventmask:
            raise CloseConnection()
        if select.POLLOUT & eventmask:
            self.send_responses()
        if select.POLLIN & eventmask:
            self.receive_requests()
        self.process_requests()
        self.send_responses()

    def send_responses(self):
        while self.pending_responses:
            response = self.encode(self.pending_responses.popleft())
            try:
                sent = self.conn.send(response)
            except InterruptedError:
                self.pending_responses.appendleft(response)
                continue
            except BlockingIOError:
                self.pending_responses.appendleft(response)
                return
            except BrokenPipeError:
                raise CloseConnection()
            else:
                if sent == 0:
                    raise CloseConnection()
        if not self.pending_responses:
            self.poll.modify(self.conn, select.POLLIN)

    def process_requests(self):
        while self.pending_requests:
            if len(self.pending_responses) == self.MAX_PENDING_RESPONSES:
                break
            signo = self.pending_requests.popleft()
            if signo not in signame_map:
                logger.warning("Client requested invalid signal %d", signo)
                self.pending_responses.append(self.RETURN_INVALID)
                continue
            try:
                os.kill(self.proxy.pid, signo)
            except OSError:
                logger.exception("Tried sending %s", signame_map[signo])
                self.pending_responses.append(self.RETURN_CHILD_ERROR)
                # Try to send the responses
                try:
                    self.send_responses()
                except (CloseConnection, OSError):
                    pass
                raise ShutdownDaemon()
            else:
                self.pending_responses.append(self.RETURN_OK)

    def receive_requests(self):
        """Read all available data from the client socket"""
        while True:
            read = self.MAX_PENDING_REQUESTS - len(self.pending_requests)
            if read <= 0:
                self.poll.modify(self.conn, select.POLLOUT)
                break
            try:
                data = self.conn.recv(read)
            except InterruptedError:
                continue
            except BlockingIOError:
                # All available data was read
                break
            if not data:
                raise CloseConnection()
            self.pending_requests.extend(data)

    def close(self):
        if self.state == ConnectionState.closed:
            logger.warning("Connection already closed")
            return
        self.poll.unregister(self.conn)
        try_close(self.conn)
        self.pending_responses.clear()
        self.pending_requests.clear()
        self.state = ConnectionState.closed


if __name__ == '__main__':
    main()
