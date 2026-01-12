"""
SALOCOIN RPC Client
HTTP JSON-RPC client for connecting to SALOCOIN daemon.
"""

import json
import base64
import socket
import http.client
from typing import Any, Dict, Optional, List
from urllib.parse import urlparse

import config


class RPCClientError(Exception):
    """RPC client error."""
    pass


class RPCResponseError(Exception):
    """RPC response error."""
    
    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(f"[{code}] {message}")


class RPCClient:
    """
    SALOCOIN RPC Client.
    
    Provides JSON-RPC client for communicating with SALOCOIN daemon.
    """
    
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = config.RPC_PORT,
        username: str = None,
        password: str = None,
        timeout: int = 30,
    ):
        """
        Initialize RPC client.
        
        Args:
            host: RPC server host
            port: RPC server port
            username: RPC username
            password: RPC password
            timeout: Request timeout in seconds
        """
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.timeout = timeout
        
        # Request ID counter
        self._id = 0
    
    @classmethod
    def from_config(cls, config_file: str = None) -> 'RPCClient':
        """
        Create client from config file.
        
        Args:
            config_file: Path to config file
            
        Returns:
            RPCClient instance
        """
        if config_file is None:
            config_file = config.get_config_file()
        
        # Read config file
        settings = {}
        try:
            with open(config_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if '=' in line and not line.startswith('#'):
                        key, value = line.split('=', 1)
                        settings[key.strip()] = value.strip()
        except FileNotFoundError:
            pass
        
        return cls(
            host=settings.get('rpcconnect', '127.0.0.1'),
            port=int(settings.get('rpcport', config.RPC_PORT)),
            username=settings.get('rpcuser'),
            password=settings.get('rpcpassword'),
        )
    
    def call(self, method: str, *args) -> Any:
        """
        Call an RPC method.
        
        Args:
            method: Method name
            *args: Method arguments
            
        Returns:
            Method result
        """
        return self._request(method, list(args))
    
    def __getattr__(self, name: str):
        """Allow calling methods as attributes."""
        # Convert snake_case to camelCase for common methods
        method_name = name
        
        def method(*args):
            return self.call(method_name, *args)
        
        return method
    
    def _request(self, method: str, params: List = None) -> Any:
        """
        Make an RPC request.
        
        Args:
            method: Method name
            params: Parameters
            
        Returns:
            Result
        """
        self._id += 1
        
        # Build request
        request = {
            'jsonrpc': '2.0',
            'method': method,
            'params': params or [],
            'id': self._id,
        }
        
        body = json.dumps(request).encode('utf-8')
        
        # Build headers
        headers = {
            'Content-Type': 'application/json',
        }
        
        if self.username and self.password:
            auth = base64.b64encode(
                f"{self.username}:{self.password}".encode()
            ).decode()
            headers['Authorization'] = f"Basic {auth}"
        
        # Make request
        try:
            conn = http.client.HTTPConnection(
                self.host,
                self.port,
                timeout=self.timeout
            )
            conn.request('POST', '/', body, headers)
            
            response = conn.getresponse()
            response_data = response.read()
            
            conn.close()
            
        except socket.timeout:
            raise RPCClientError("Request timed out")
        except ConnectionRefusedError:
            raise RPCClientError(
                f"Cannot connect to RPC server at {self.host}:{self.port}"
            )
        except Exception as e:
            raise RPCClientError(f"Connection error: {e}")
        
        # Check HTTP status
        if response.status == 401:
            raise RPCClientError("Authentication failed")
        
        if response.status != 200:
            raise RPCClientError(f"HTTP error: {response.status}")
        
        # Parse response
        try:
            result = json.loads(response_data.decode('utf-8'))
        except json.JSONDecodeError as e:
            raise RPCClientError(f"Invalid JSON response: {e}")
        
        # Check for error
        if 'error' in result and result['error'] is not None:
            error = result['error']
            raise RPCResponseError(
                error.get('code', -1),
                error.get('message', 'Unknown error')
            )
        
        return result.get('result')
    
    def batch(self, calls: List[Dict]) -> List[Any]:
        """
        Execute batch RPC request.
        
        Args:
            calls: List of {'method': ..., 'params': [...]}
            
        Returns:
            List of results
        """
        requests = []
        for i, call in enumerate(calls):
            requests.append({
                'jsonrpc': '2.0',
                'method': call['method'],
                'params': call.get('params', []),
                'id': i + 1,
            })
        
        body = json.dumps(requests).encode('utf-8')
        
        # Build headers
        headers = {
            'Content-Type': 'application/json',
        }
        
        if self.username and self.password:
            auth = base64.b64encode(
                f"{self.username}:{self.password}".encode()
            ).decode()
            headers['Authorization'] = f"Basic {auth}"
        
        # Make request
        try:
            conn = http.client.HTTPConnection(
                self.host,
                self.port,
                timeout=self.timeout
            )
            conn.request('POST', '/', body, headers)
            
            response = conn.getresponse()
            response_data = response.read()
            
            conn.close()
            
        except Exception as e:
            raise RPCClientError(f"Connection error: {e}")
        
        # Parse response
        try:
            results = json.loads(response_data.decode('utf-8'))
        except json.JSONDecodeError as e:
            raise RPCClientError(f"Invalid JSON response: {e}")
        
        # Sort by id and extract results
        results.sort(key=lambda x: x.get('id', 0))
        
        return [
            r.get('result') if r.get('error') is None else r.get('error')
            for r in results
        ]


class AsyncRPCClient:
    """
    Async SALOCOIN RPC Client.
    
    Provides async JSON-RPC client for communicating with SALOCOIN daemon.
    """
    
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = config.RPC_PORT,
        username: str = None,
        password: str = None,
        timeout: int = 30,
    ):
        """
        Initialize async RPC client.
        
        Args:
            host: RPC server host
            port: RPC server port
            username: RPC username
            password: RPC password
            timeout: Request timeout in seconds
        """
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.timeout = timeout
        self._id = 0
    
    async def call(self, method: str, *args) -> Any:
        """
        Call an RPC method asynchronously.
        
        Args:
            method: Method name
            *args: Method arguments
            
        Returns:
            Method result
        """
        import asyncio
        import aiohttp
        
        self._id += 1
        
        request = {
            'jsonrpc': '2.0',
            'method': method,
            'params': list(args),
            'id': self._id,
        }
        
        headers = {'Content-Type': 'application/json'}
        auth = None
        
        if self.username and self.password:
            auth = aiohttp.BasicAuth(self.username, self.password)
        
        url = f"http://{self.host}:{self.port}/"
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json=request,
                auth=auth,
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            ) as response:
                if response.status == 401:
                    raise RPCClientError("Authentication failed")
                
                result = await response.json()
                
                if 'error' in result and result['error'] is not None:
                    error = result['error']
                    raise RPCResponseError(
                        error.get('code', -1),
                        error.get('message', 'Unknown error')
                    )
                
                return result.get('result')
