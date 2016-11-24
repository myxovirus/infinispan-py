# -*- coding: utf-8 -*-

import pytest

from .server import InfinispanServer
from infinispan import connection, error


class TestSocketConnection(object):
    @classmethod
    def setup_class(cls):
        cls.server = InfinispanServer()
        cls.server.start()

    @classmethod
    def teardown_class(cls):
        try:
            cls.server.stop()
        except RuntimeError:
            # is ok, already stopped
            pass

    @pytest.yield_fixture
    def conn(self):
        conn = connection.SocketConnection()
        conn.connect()
        yield conn
        conn.disconnect()

    def test_successful_connection(self, conn):
        conn.send(b'\xa0\x01\x19\x17\x00\x00\x01\x00')

        assert next(conn.recv()) == b'\xa1'

    def test_remote_hung_up(self, conn):
        TestSocketConnection.server.stop()
        try:
            with pytest.raises(error.ConnectionError):
                conn.send(b'\xa0\x01\x19\x17\x00\x00\x01\x00')
                next(conn.recv())
        finally:
            TestSocketConnection.server.start()

    def test_remote_conn_refused(self, conn):
        TestSocketConnection.server.kill()
        try:
            with pytest.raises(error.ConnectionError):
                conn.send(b'\xa0\x01\x19\x17\x00\x00\x01\x00')
                next(conn.recv())
        finally:
            TestSocketConnection.server.start()

    def test_disconnect_before_send(self, conn):
        TestSocketConnection.server.stop()
        try:
            with pytest.raises(error.ConnectionError):
                conn.send(b'\xa0\x01\x19\x17\x00\x00\x01\x00')
                conn.send(b'\xa0\x02\x19\x17\x00\x00\x01\x00')
        finally:
            TestSocketConnection.server.start()

    def test_connection_timeout(self, conn):
        with pytest.raises(error.ConnectionError):
            next(conn.recv())


class TestConnectionPool(object):
        @classmethod
        def setup_class(cls):
            cls.server = InfinispanServer()
            cls.server.start()

        @classmethod
        def teardown_class(cls):
            try:
                cls.server.stop()
            except RuntimeError:
                # is ok, already stopped
                pass

        @pytest.yield_fixture
        def conn(self):
            connections = [connection.SocketConnection() for _ in range(3)]
            conn = connection.ConnectionPool(connections=connections)
            conn.connect()
            yield conn
            conn.disconnect()

        def test_successful_connection(self, conn):
            conn.send(b'\xa0\x01\x19\x17\x00\x00\x01\x00')
            conn.send(b'\xa0\x02\x19\x17\x00\x00\x01\x00')
            conn.send(b'\xa0\x03\x19\x17\x00\x00\x01\x00')
            data1 = conn.recv()
            data2 = conn.recv()
            data3 = conn.recv()

            assert conn.available == 3
            assert next(data1) == b'\xa1'
            assert conn.available == 2
            assert next(data2) == b'\xa1'
            assert conn.available == 1
            assert next(data3) == b'\xa1'
            assert conn.available == 0
            assert next(data1) in [b'\x01', b'\x02', b'\x03']

            try:
                data1.send(0)
            except StopIteration:
                pass
            assert conn.available == 1
            try:
                data2.send(0)
            except StopIteration:
                pass
            try:
                data3.send(0)
            except StopIteration:
                pass
            assert conn.available == 3