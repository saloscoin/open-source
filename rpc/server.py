"""
SALOCOIN RPC Server
HTTP JSON-RPC server for wallet and node control.
"""

import json
import socket
import threading
import hashlib
import base64
import time
import traceback
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, Any, Optional, Callable
from functools import wraps

import config


class AuthenticationError(Exception):
    """RPC authentication error."""
    pass


class RPCError(Exception):
    """RPC error with code."""
    
    # Standard JSON-RPC error codes
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603
    
    # Custom error codes (Bitcoin-compatible)
    RPC_MISC_ERROR = -1
    RPC_FORBIDDEN_BY_SAFE_MODE = -2
    RPC_TYPE_ERROR = -3
    RPC_INVALID_ADDRESS_OR_KEY = -5
    RPC_OUT_OF_MEMORY = -7
    RPC_INVALID_PARAMETER = -8
    RPC_DATABASE_ERROR = -20
    RPC_DESERIALIZATION_ERROR = -22
    RPC_VERIFY_ERROR = -25
    RPC_VERIFY_REJECTED = -26
    RPC_VERIFY_ALREADY_IN_CHAIN = -27
    RPC_IN_WARMUP = -28
    RPC_METHOD_DEPRECATED = -32
    
    # Wallet errors
    RPC_WALLET_ERROR = -4
    RPC_WALLET_INSUFFICIENT_FUNDS = -6
    RPC_WALLET_INVALID_LABEL_NAME = -11
    RPC_WALLET_KEYPOOL_RAN_OUT = -12
    RPC_WALLET_UNLOCK_NEEDED = -13
    RPC_WALLET_PASSPHRASE_INCORRECT = -14
    RPC_WALLET_WRONG_ENC_STATE = -15
    RPC_WALLET_ENCRYPTION_FAILED = -16
    RPC_WALLET_ALREADY_UNLOCKED = -17
    RPC_WALLET_NOT_FOUND = -18
    RPC_WALLET_NOT_SPECIFIED = -19
    
    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


class RPCHandler(BaseHTTPRequestHandler):
    """HTTP handler for RPC requests."""
    
    # Silence logging
    def log_message(self, format, *args):
        if self.server.rpc_server.verbose:
            print(f"[RPC] {self.address_string()} - {format % args}")
    
    def do_POST(self):
        """Handle POST request."""
        try:
            # Check authentication
            if not self._authenticate():
                self._send_error(401, "Unauthorized")
                return
            
            # Read request body
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self._send_json_error(RPCError.INVALID_REQUEST, "Empty request")
                return
            
            body = self.rfile.read(content_length)
            
            # Parse JSON
            try:
                request = json.loads(body.decode('utf-8'))
            except json.JSONDecodeError as e:
                self._send_json_error(RPCError.PARSE_ERROR, f"Parse error: {e}")
                return
            
            # Handle request (or batch)
            if isinstance(request, list):
                # Batch request
                responses = []
                for req in request:
                    response = self._handle_single_request(req)
                    if response is not None:  # Only include if not notification
                        responses.append(response)
                self._send_response(responses if responses else None)
            else:
                # Single request
                response = self._handle_single_request(request)
                self._send_response(response)
                
        except Exception as e:
            traceback.print_exc()
            self._send_json_error(RPCError.INTERNAL_ERROR, str(e))
    
    def _authenticate(self) -> bool:
        """Check RPC authentication."""
        if not self.server.rpc_server.auth_required:
            return True
        
        auth_header = self.headers.get('Authorization')
        if not auth_header:
            return False
        
        try:
            # Parse Basic auth
            if not auth_header.startswith('Basic '):
                return False
            
            encoded = auth_header[6:]
            decoded = base64.b64decode(encoded).decode('utf-8')
            username, password = decoded.split(':', 1)
            
            return self.server.rpc_server.check_auth(username, password)
            
        except Exception:
            return False
    
    def _handle_single_request(self, request: Dict) -> Optional[Dict]:
        """Handle a single RPC request."""
        # Validate request
        if not isinstance(request, dict):
            return self._make_error_response(
                RPCError.INVALID_REQUEST, 
                "Invalid request",
                None
            )
        
        method = request.get('method')
        params = request.get('params', [])
        request_id = request.get('id')
        
        if not method:
            return self._make_error_response(
                RPCError.INVALID_REQUEST,
                "Method required",
                request_id
            )
        
        # If id is None, it's a notification (no response)
        is_notification = 'id' not in request
        
        # Execute method
        try:
            result = self.server.rpc_server.execute_method(method, params)
            
            if is_notification:
                return None
            
            return {
                'jsonrpc': '2.0',
                'result': result,
                'id': request_id,
            }
            
        except RPCError as e:
            if is_notification:
                return None
            
            return self._make_error_response(e.code, e.message, request_id)
            
        except Exception as e:
            if is_notification:
                return None
            
            return self._make_error_response(
                RPCError.INTERNAL_ERROR,
                str(e),
                request_id
            )
    
    def _make_error_response(self, code: int, message: str, request_id) -> Dict:
        """Create an error response."""
        return {
            'jsonrpc': '2.0',
            'error': {
                'code': code,
                'message': message,
            },
            'id': request_id,
        }
    
    def _send_response(self, response):
        """Send JSON response."""
        if response is None:
            self.send_response(204)
            self.end_headers()
            return
        
        body = json.dumps(response).encode('utf-8')
        
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', len(body))
        self.end_headers()
        self.wfile.write(body)
    
    def _send_json_error(self, code: int, message: str):
        """Send JSON error response."""
        response = self._make_error_response(code, message, None)
        self._send_response(response)
    
    def _send_error(self, code: int, message: str):
        """Send HTTP error response."""
        self.send_response(code)
        self.send_header('Content-Type', 'text/plain')
        self.send_header('WWW-Authenticate', 'Basic realm="SALOCOIN RPC"')
        self.end_headers()
        self.wfile.write(message.encode('utf-8'))


class RPCServer:
    """
    SALOCOIN JSON-RPC Server.
    
    Provides HTTP JSON-RPC interface for wallet and node control.
    """
    
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = config.RPC_PORT,
        username: str = None,
        password: str = None,
        verbose: bool = False,
    ):
        """
        Initialize RPC server.
        
        Args:
            host: Host to bind to
            port: Port to listen on
            username: RPC username
            password: RPC password
            verbose: Enable verbose logging
        """
        self.host = host
        self.port = port
        self.verbose = verbose
        
        # Authentication
        self.username = username
        self.password = password
        self.auth_required = username is not None and password is not None
        
        # Methods registry
        self._methods: Dict[str, Callable] = {}
        
        # Server
        self._server: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
    
    def register_method(self, name: str, handler: Callable):
        """
        Register an RPC method.
        
        Args:
            name: Method name
            handler: Handler function
        """
        self._methods[name] = handler
    
    def register_methods(self, methods: Dict[str, Callable]):
        """
        Register multiple RPC methods.
        
        Args:
            methods: Dictionary of method name -> handler
        """
        self._methods.update(methods)
    
    def execute_method(self, method: str, params) -> Any:
        """
        Execute an RPC method.
        
        Args:
            method: Method name
            params: Method parameters
            
        Returns:
            Method result
        """
        handler = self._methods.get(method)
        
        if not handler:
            raise RPCError(
                RPCError.METHOD_NOT_FOUND,
                f"Method not found: {method}"
            )
        
        try:
            # Handle both positional and named parameters
            if isinstance(params, dict):
                return handler(**params)
            elif isinstance(params, list):
                return handler(*params)
            else:
                return handler()
                
        except TypeError as e:
            raise RPCError(RPCError.INVALID_PARAMS, str(e))
    
    def check_auth(self, username: str, password: str) -> bool:
        """
        Check authentication credentials.
        
        Args:
            username: Username
            password: Password
            
        Returns:
            True if valid
        """
        return username == self.username and password == self.password
    
    def start(self):
        """Start the RPC server."""
        if self._running:
            return
        
        print(f"Starting RPC server on {self.host}:{self.port}")
        
        self._server = HTTPServer((self.host, self.port), RPCHandler)
        self._server.rpc_server = self
        
        self._running = True
        self._thread = threading.Thread(target=self._serve)
        self._thread.daemon = True
        self._thread.start()
    
    def stop(self):
        """Stop the RPC server."""
        if not self._running:
            return
        
        print("Stopping RPC server")
        self._running = False
        
        if self._server:
            self._server.shutdown()
            self._server.server_close()
        
        if self._thread:
            self._thread.join(timeout=5)
    
    def _serve(self):
        """Server thread main loop."""
        while self._running:
            try:
                self._server.handle_request()
            except Exception as e:
                if self._running:
                    print(f"RPC error: {e}")


def require_wallet_unlocked(func):
    """Decorator to require wallet unlocked."""
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if self.wallet and self.wallet.locked:
            raise RPCError(
                RPCError.RPC_WALLET_UNLOCK_NEEDED,
                "Wallet is locked"
            )
        return func(self, *args, **kwargs)
    return wrapper


def require_masternode_mode(func):
    """Decorator to require masternode mode."""
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if not self.node.masternode_manager.running:
            raise RPCError(
                RPCError.RPC_MISC_ERROR,
                "Masternode not running"
            )
        return func(self, *args, **kwargs)
    return wrapper
