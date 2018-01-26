import asyncio
import socket
import threading
import unittest

from test.test_asyncio import utils as test_utils
from test.test_asyncio import functional as func_tests


class BaseStartServer(func_tests.FunctionalTestCaseMixin):

    def new_loop(self):
        raise NotImplementedError

    def test_start_server_1(self):
        HELLO_MSG = b'1' * 1024 * 5 + b'\n'

        def client(sock, addr):
            sock.connect(addr)
            sock.send(HELLO_MSG)
            sock.recv_all(1)
            sock.close()

        async def serve(reader, writer):
            await reader.readline()
            main_task.cancel()
            writer.write(b'1')
            writer.close()
            await writer.wait_closed()

        async def main(srv):
            async with srv:
                await srv.serve_forever()

        srv = self.loop.run_until_complete(asyncio.start_server(
            serve, '127.0.0.1', 0, loop=self.loop, start_serving=False))

        self.assertFalse(srv.is_serving())

        main_task = self.loop.create_task(main(srv))

        addr = srv.sockets[0].getsockname()
        with self.assertRaises(asyncio.CancelledError):
            with self.tcp_client(lambda sock: client(sock, addr)):
                self.loop.run_until_complete(main_task)

        self.assertEqual(srv.sockets, [])

        self.assertIsNone(srv._sockets)
        self.assertIsNone(srv._waiters)
        self.assertFalse(srv.is_serving())

        with self.assertRaisesRegex(RuntimeError, r'is closed'):
            self.loop.run_until_complete(srv.serve_forever())


class SelectorStartServerTests(BaseStartServer, unittest.TestCase):

    def new_loop(self):
        return asyncio.SelectorEventLoop()

    @unittest.skipUnless(hasattr(socket, 'AF_UNIX'), 'no Unix sockets')
    def test_start_unix_server_1(self):
        HELLO_MSG = b'1' * 1024 * 5 + b'\n'
        started = threading.Event()

        def client(sock, addr):
            started.wait(5)
            sock.connect(addr)
            sock.send(HELLO_MSG)
            sock.recv_all(1)
            sock.close()

        async def serve(reader, writer):
            await reader.readline()
            main_task.cancel()
            writer.write(b'1')
            writer.close()
            await writer.wait_closed()

        async def main(srv):
            async with srv:
                self.assertFalse(srv.is_serving())
                await srv.start_serving()
                self.assertTrue(srv.is_serving())
                started.set()
                await srv.serve_forever()

        with test_utils.unix_socket_path() as addr:
            srv = self.loop.run_until_complete(asyncio.start_unix_server(
                serve, addr, loop=self.loop, start_serving=False))

            main_task = self.loop.create_task(main(srv))

            with self.assertRaises(asyncio.CancelledError):
                with self.unix_client(lambda sock: client(sock, addr)):
                    self.loop.run_until_complete(main_task)

            self.assertEqual(srv.sockets, [])

            self.assertIsNone(srv._sockets)
            self.assertIsNone(srv._waiters)
            self.assertFalse(srv.is_serving())

            with self.assertRaisesRegex(RuntimeError, r'is closed'):
                self.loop.run_until_complete(srv.serve_forever())


@unittest.skipUnless(hasattr(asyncio, 'ProactorEventLoop'), 'Windows only')
class ProactorStartServerTests(BaseStartServer, unittest.TestCase):

    def new_loop(self):
        return asyncio.ProactorEventLoop()


if __name__ == '__main__':
    unittest.main()