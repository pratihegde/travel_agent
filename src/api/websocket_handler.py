import json
import asyncio
from datetime import datetime
from typing import Set
from aiohttp import web, WSMsgType

from ..agents.travel_agent import TravelAgent
from ..utils.logger import get_logger

logger = get_logger(__name__)

class WebSocketHandler:
    """Enhanced WebSocket handler for travel agent"""
    
    def __init__(self):
        self.agent = TravelAgent()
        self.connections: Set[web.WebSocketResponse] = set()
        
    async def handle_websocket(self, request) -> web.WebSocketResponse:
        """Handle WebSocket connections"""
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        
        connection_id = id(ws)
        self.connections.add(ws)
        session_id = str(connection_id)
        
        logger.info(f"🔗 New WebSocket connection: {session_id[:8]}...")
        
        # Send welcome message
        welcome_message = {
            "type": "response",
            "content": self.agent.get_welcome_message(),
            "timestamp": datetime.now().isoformat(),
            "session_info": self.agent.get_session_info(session_id)
        }
        await self._send_message(ws, welcome_message)
        
        try:
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    await self._handle_text_message(ws, msg.data, session_id)
                elif msg.type == WSMsgType.ERROR:
                    logger.error(f'WebSocket error: {ws.exception()}')
                    break
        
        except Exception as e:
            logger.error(f"WebSocket handler error: {e}")
        
        finally:
            self.connections.discard(ws)
            # Clean up session
            self.agent.clear_session(session_id)
            logger.info(f"🔌 WebSocket connection {session_id[:8]}... closed")
        
        return ws
    
    async def _handle_text_message(self, ws: web.WebSocketResponse, data: str, session_id: str):
        """Handle text messages from client"""
        try:
            message_data = json.loads(data)
            message_type = message_data.get("type")
            
            if message_type == "message":
                await self._handle_chat_message(ws, message_data, session_id)
            elif message_type == "clear_session":
                await self._handle_clear_session(ws, session_id)
            elif message_type == "get_session_info":
                await self._handle_session_info(ws, session_id)
            else:
                await self._send_error(ws, "Unknown message type") 
        
        except json.JSONDecodeError:
            await self._send_error(ws, "Invalid JSON format")
        except Exception as e:
            logger.error(f"Error handling message: {e}")
            await self._send_error(ws, "Error processing message")
    
    async def _handle_chat_message(self, ws: web.WebSocketResponse, message_data: dict, session_id: str):
        """Handle chat messages"""
        user_message = message_data.get("content", "").strip()
        if not user_message:
            await self._send_error(ws, "Empty message")
            return
        
        logger.info(f"📝 Received: {user_message[:50]}...")
        
        # Send typing indicator
        await self._send_message(ws, {
            "type": "typing",
            "content": True,
            "timestamp": datetime.now().isoformat()
        })
        
        try:
            # Get AI response
            ai_response = await self.agent.get_response(user_message, session_id)
            
            # Send response
            await self._send_message(ws, {
                "type": "response",
                "content": ai_response,
                "timestamp": datetime.now().isoformat(),
                "session_info": self.agent.get_session_info(session_id)
            })
        
        except Exception as e:
            logger.error(f"Error getting agent response: {e}")
            await self._send_error(ws, "Sorry, I had trouble processing that message.")
        
        finally:
            # Stop typing indicator
            await self._send_message(ws, {
                "type": "typing",
                "content": False,
                "timestamp": datetime.now().isoformat()
            })
    
    async def _handle_clear_session(self, ws: web.WebSocketResponse, session_id: str):
        """Handle session clearing"""
        self.agent.clear_session(session_id)
        await self._send_message(ws, {
            "type": "session_cleared",
            "content": "Session cleared successfully",
            "timestamp": datetime.now().isoformat()
        })
    
    async def _handle_session_info(self, ws: web.WebSocketResponse, session_id: str):
        """Send session information"""
        session_info = self.agent.get_session_info(session_id)
        await self._send_message(ws, {
            "type": "session_info",
            "content": session_info,
            "timestamp": datetime.now().isoformat()
        })
    
    async def _send_message(self, ws: web.WebSocketResponse, message: dict):
        """Send message to WebSocket client"""
        try:
            await ws.send_str(json.dumps(message))
        except Exception as e:
            logger.error(f"Error sending message: {e}")
    
    async def _send_error(self, ws: web.WebSocketResponse, error_message: str):
        """Send error message to client"""
        error_msg = {
            "type": "error",
            "content": error_message,
            "timestamp": datetime.now().isoformat()
        }
        await self._send_message(ws, error_msg)
    
    async def broadcast_message(self, message: dict):
        """Broadcast message to all connected clients"""
        if not self.connections:
            return
        
        disconnected = set()
        for ws in self.connections:
            try:
                await ws.send_str(json.dumps(message))
            except Exception:
                disconnected.add(ws)
        
        # Remove disconnected clients
        self.connections -= disconnected