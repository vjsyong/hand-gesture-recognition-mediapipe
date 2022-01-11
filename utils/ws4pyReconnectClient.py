import time
import socket
import threading
import logging

from ws4py.client import WebSocketBaseClient
from ws4py.streaming import Stream

logger = logging.getLogger(__name__)

class ws4pyReconnectClient(WebSocketBaseClient):
    """Websocket client implementing reconnect logic."""

    def __init__(self, url, *args, **kwargs):
        super().__init__(url, *args, **kwargs)
        self._stop = threading.Event()
        """Maximum timeout to wait before a reconnect is attempted"""
        self.maxTimeout = 5

        """Connection status indicator"""
        self._connected = False
    
    def start(self, reconnect=True):
        """Runs a new thread for the setup method
        
        Args:
            reconnect (Boolean): indicates if reconnect should be performed
        """
        self.reconnect = reconnect

        self._st = threading.Thread(target=self._setup, name="wsSetupThread")
        self._st.daemon = True
        self._st.start()

    def _setup(self, timeout=1):
        """Tries to connect to the central system.

        On failure, timeout is waited before trying to reconnect.
        On failed attempt, the method calls itself recursively.

        Args:
            timeout: timeout to wait before a reconnect is done.
        """
        if self._stop.is_set():
            return

        try:
            logger.info("Trying to connect to {}:{}.".format(*self.bind_addr))
            self._setup_connection()
            self.connect()
        except ConnectionRefusedError:
            if timeout * 2 > self.maxTimeout:
                newTimeout = self.maxTimeout
            else:
                newTimeout = timeout * 2

            logger.warning("Connection to {}:{} refused!".format(*self.bind_addr))
            logger.warning("Timing out {} seconds before reconnect.".format(newTimeout))
            time.sleep(newTimeout)
            self._setup(newTimeout)
        except Exception as e:
            logger.warning(e)

    def stop(self, code=1001, reason=""):
        """Inits the shutdown of the client.""" 
        self._stop.set()
        if self._connected and self._th.is_alive():
            self.close(code, reason)
            self._th.join()

    def closed(self, code, reason):
        """Method is run when the connection is closed.
        
        Resets client_ and server_terminated variables to False in order
        to avoid Exceptions on successful reconnection. 
        
        Creates a new Thread which runs until a new connection is
        established. This is needed in order to end the old Thread which
        handeled the prior connection and is responsible for proper
        cleanup.
        """
        logger.warning("Connection closed: {} ({})".format(reason, code))

        self._connected = False

        if not self._stop.is_set() and self.reconnect:
            logger.info("Reconnecting ...")
            self.start()

    def handshake_ok(self):
        """
        Called when the upgrade handshake has completed
        successfully

        Starts the client's thread
        """
        logger.info("Connected to {}:{}.".format(*self.bind_addr))
        self._connected = True 
        self._th.start()

    def _setup_connection(self):
        """Prepares the connection.

        A new socket is opened to guarantee a proper reconnection when
        connection was lost prior.
        A new Stream handler is instantiated since the old one is
        destroyed when the connection terminates.
        Creates a new Thread which runs the inherited run() method.
        """
        self._open_socket()
        self.stream = Stream(always_mask=False)
        self.stream.always_mask = True
        self.stream.expect_masking = False

        self.client_terminated = False
        self.server_terminated = False

        self._th = threading.Thread(target=self.run, name="occpWsClient")
        self._th.daemon = True

    def _open_socket(self):
        """A :py:mod:`socket` is created.

        Handels unix sockets and IP4 and IP6 adresses.
        Extracted from the ws4py::WebSocketBaseClient constructor.
        """
        if self.unix_socket_path:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM, 0)
        else:
            # Let's handle IPv4 and IPv6 addresses
            # Simplified from CherryPy's code
            try:
                family, socktype, proto, canonname, sa = socket.getaddrinfo(
                                        self.host, self.port,
                                        socket.AF_UNSPEC,
                                        socket.SOCK_STREAM,
                                        0, socket.AI_PASSIVE)[0]

            except socket.gaierror:
                family = socket.AF_INET
                if self.host.startswith('::'):
                    family = socket.AF_INET6

                socktype = socket.SOCK_STREAM
                proto = 0
                canonname = ""
                sa = (self.host, self.port, 0, 0)

            sock = socket.socket(family, socktype, proto)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            if hasattr(socket, 'AF_INET6') and family == socket.AF_INET6 and \
              self.host.startswith('::'):
                try:
                    sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
                except (AttributeError, socket.error):
                    pass

        self.sock = sock

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)

    client = ws4pyReconnectClient("ws://127.0.0.1:8080")
    client.start()

    while True:
        try:
            pass
        except KeyboardInterrupt:
            client.stop()
            break