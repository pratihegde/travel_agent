#!/usr/bin/env python3

import asyncio
import json
import os
import logging
from datetime import datetime
from typing import Dict, List
import openai
from dotenv import load_dotenv
from aiohttp import web, WSMsgType
import aiofiles

# Load environment variables
if os.path.exists('.env'):
    load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TravelAgent:
    """AI Travel Agent with conversation memory and travel expertise"""
    
    def __init__(self):
        # Initialize OpenAI client
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables")
        
        self.client = openai.OpenAI(api_key=api_key)
        
        # Conversation state
        self.conversations = {}  # Store conversations by connection ID
        
        # Travel knowledge base
        self.travel_knowledge = {
            "destinations": {
                "japan": {
                    "best_season": "Spring (March-May) for cherry blossoms, Fall (Sept-Nov) for colors",
                    "budget": "$100-200/day for mid-range travel",
                    "highlights": ["Tokyo", "Kyoto", "Osaka", "Mount Fuji"],
                    "culture_tips": "Bow when greeting, remove shoes indoors, don't tip"
                },
                "paris": {
                    "best_season": "Late spring (May-June) or early fall (September-October)",
                    "budget": "$120-250/day for mid-range travel", 
                    "highlights": ["Eiffel Tower", "Louvre", "Notre-Dame", "Montmartre"],
                    "culture_tips": "Greet with 'Bonjour', dress nicely, learn basic French phrases"
                },
                "bali": {
                    "best_season": "Dry season (April-October)",
                    "budget": "$50-100/day for mid-range travel",
                    "highlights": ["Ubud", "Seminyak", "Uluwatu", "Rice Terraces"],
                    "culture_tips": "Respect temples, dress modestly, bargain at markets"
                }
            }
        }
        
        # System prompt for travel expertise
        self.system_prompt = """You are TravelBot, an expert AI travel agent with extensive knowledge of destinations worldwide. You provide personalized, helpful travel advice in a friendly, conversational manner.

CORE EXPERTISE:
• Destination recommendations based on preferences, budget, season
• Detailed itinerary planning and logistics
• Cultural insights and local customs
• Budget planning and cost-saving strategies  
• Weather patterns and best travel times
• Food recommendations and dining tips
• Transportation options and booking advice
• Safety tips and travel requirements

CONVERSATION STYLE:
• Be warm, enthusiastic, and genuinely helpful
• Provide specific, actionable recommendations
• Ask clarifying questions to better understand needs
• Share insider tips and lesser-known gems
• Be honest about challenges or limitations
• Remember context from our conversation

RESPONSE GUIDELINES:
• Keep responses conversational and engaging
• Provide concrete examples and specific advice
• Include relevant details like costs, timing, booking tips
• Suggest follow-up questions or next steps
• Prioritize traveler safety and current information
• Use clean, natural language without markdown formatting, asterisks, or hash symbols
• Write in flowing paragraphs with clear sentences instead of bullet points or lists
• Don't make the sentences bold as it gives * symbols in the response

You're here to help plan amazing travel experiences! How can I assist with your travel dreams?"""

        logger.info("🌍 Travel Agent initialized successfully")
    
    def get_conversation(self, connection_id: str) -> List[Dict]:
        """Get or create conversation history for a connection"""
        if connection_id not in self.conversations:
            self.conversations[connection_id] = [
                {"role": "system", "content": self.system_prompt}
            ]
        return self.conversations[connection_id]
    
    def enhance_travel_query(self, message: str) -> str:
        """Enhance user queries with relevant travel context"""
        message_lower = message.lower()
        enhancements = []
        
        # Add destination-specific context
        for destination, info in self.travel_knowledge["destinations"].items():
            if destination in message_lower:
                context = f"Context for {destination.title()}: Best season is {info['best_season']}. "
                context += f"Budget around {info['budget']}. "
                context += f"Must-see: {', '.join(info['highlights'])}. "
                context += f"Cultural tip: {info['culture_tips']}"
                enhancements.append(context)
        
        # Add query-specific context
        if any(word in message_lower for word in ['weather', 'climate', 'season']):
            enhancements.append("Please provide current weather context and seasonal recommendations.")
        
        if any(word in message_lower for word in ['budget', 'cost', 'expensive', 'cheap']):
            enhancements.append("Include detailed budget breakdown and money-saving tips.")
        
        if any(word in message_lower for word in ['family', 'kids', 'children']):
            enhancements.append("Focus on family-friendly options and child-appropriate activities.")
        
        # Combine original message with enhancements
        if enhancements:
            enhanced = f"{message}\n\nAdditional context: {' '.join(enhancements)}"
            return enhanced
        
        return message
    
    async def get_travel_response(self, message: str, connection_id: str) -> str:
        """Get AI response for travel query"""
        try:
            # Get conversation history
            conversation = self.get_conversation(connection_id)
            
            # Enhance the query with travel context
            enhanced_message = self.enhance_travel_query(message)
            
            # Add user message to conversation
            conversation.append({"role": "user", "content": enhanced_message})
            
            # Get AI response
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=conversation,
                max_tokens=300,
                temperature=0.7,
                presence_penalty=0.1,
                frequency_penalty=0.1
            )
            
            ai_response = response.choices[0].message.content
            
            # Add AI response to conversation
            conversation.append({"role": "assistant", "content": ai_response})
            
            # Keep conversation history manageable (last 20 messages)
            if len(conversation) > 21:  # Keep system message + 20 messages
                conversation = [conversation[0]] + conversation[-20:]
                self.conversations[connection_id] = conversation
            
            logger.info(f"🤖 Generated response for connection {connection_id[:8]}...")
            return ai_response
            
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return "I'm sorry, I'm having trouble processing your request right now. Please try again in a moment."

class TravelAgentServer:
    """HTTP + WebSocket server for the Travel Agent"""
    
    def __init__(self, host="0.0.0.0", port=None):
        self.host = host
        self.port = port or int(os.getenv("PORT", 8080))
        self.agent = TravelAgent()
        self.connections = set()
        self.app = web.Application()
        self.setup_routes()
        logger.info(f"🌐 Travel Agent Server initialized on {host}:{self.port}")
    
    def setup_routes(self):
        """Setup HTTP and WebSocket routes"""
        # Health check endpoint for Railway
        self.app.router.add_get('/', self.health_check)
        self.app.router.add_get('/health', self.health_check)
        
        # Serve the web interface
        self.app.router.add_get('/chat', self.serve_chat_interface)
        
        # WebSocket endpoint
        self.app.router.add_get('/ws', self.websocket_handler)
    
    async def health_check(self, request):
        """Health check endpoint for Railway load balancer"""
        return web.json_response({
            "status": "healthy",
            "service": "Travel Agent",
            "timestamp": datetime.now().isoformat(),
            "websocket_endpoint": "/ws",
            "chat_interface": "/chat"
        })
    
    async def serve_chat_interface(self, request):
        """Serve the chat web interface"""
        # Get the WebSocket URL based on the request
        scheme = 'wss' if request.scheme == 'https' else 'ws'
        ws_url = f"{scheme}://{request.host}/ws"
        
        # HTML content with dynamic WebSocket URL
        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Travel Voice Agent</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 10px;
        }}

        .container {{
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            padding: 20px;
            max-width: 800px;
            width: 100%;
            height: 80vh;
            min-height: 500px;
            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1);
            display: flex;
            flex-direction: column;
        }}

        .header {{
            text-align: center;
            margin-bottom: 15px;
        }}

        .header h1 {{
            color: #333;
            font-size: 1.8em;
            margin-bottom: 5px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }}

        .header p {{
            color: #666;
            font-size: 0.9em;
        }}

        .chat-container {{
            flex: 1;
            background: #f8f9fa;
            border-radius: 15px;
            padding: 15px;
            margin: 10px 0;
            display: flex;
            flex-direction: column;
            border: 2px solid #e9ecef;
        }}

        .messages {{
            flex: 1;
            overflow-y: auto;
            margin-bottom: 15px;
            padding-right: 10px;
        }}

        .message {{
            margin: 8px 0;
            padding: 10px 14px;
            border-radius: 18px;
            max-width: 85%;
            animation: slideIn 0.3s ease;
            font-size: 0.9em;
            line-height: 1.4;
        }}

        @keyframes slideIn {{
            from {{ opacity: 0; transform: translateY(10px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}

        .message.user {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            align-self: flex-end;
            margin-left: auto;
        }}

        .message.agent {{
            background: white;
            color: #333;
            border: 1px solid #e9ecef;
            align-self: flex-start;
        }}

        .message.typing {{
            background: #e9ecef;
            color: #666;
            font-style: italic;
            align-self: flex-start;
        }}

        .typing-dots {{
            display: inline-block;
            width: 40px;
        }}

        .typing-dots::after {{
            content: '•••';
            animation: typing 1.5s infinite;
        }}

        @keyframes typing {{
            0%, 20% {{ opacity: 0; }}
            50% {{ opacity: 1; }}
            100% {{ opacity: 0; }}
        }}

        .input-area {{
            display: flex;
            gap: 8px;
            align-items: center;
        }}

        .message-input {{
            flex: 1;
            padding: 10px 14px;
            border: 2px solid #e9ecef;
            border-radius: 20px;
            font-size: 14px;
            outline: none;
            transition: border-color 0.3s;
        }}

        .message-input:focus {{
            border-color: #667eea;
        }}

        .send-button, .voice-button {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 10px 16px;
            border-radius: 20px;
            font-size: 14px;
            cursor: pointer;
            transition: all 0.3s ease;
            min-width: 50px;
        }}

        .send-button:hover, .voice-button:hover {{
            transform: translateY(-1px);
            box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
        }}

        .send-button:disabled, .voice-button:disabled {{
            background: #6c757d;
            cursor: not-allowed;
            transform: none;
        }}

        .voice-button.recording {{
            background: linear-gradient(135deg, #ff6b6b 0%, #ee5a52 100%);
            animation: pulse 1.5s infinite;
        }}

        @keyframes pulse {{
            0% {{ box-shadow: 0 4px 15px rgba(255, 107, 107, 0.3); }}
            50% {{ box-shadow: 0 4px 25px rgba(255, 107, 107, 0.6); }}
            100% {{ box-shadow: 0 4px 15px rgba(255, 107, 107, 0.3); }}
        }}

        .status {{
            text-align: center;
            padding: 8px;
            border-radius: 8px;
            margin: 8px 0;
            font-weight: bold;
            font-size: 0.85em;
        }}

        .status.connected {{
            background: #d1ecf1;
            color: #0c5460;
            border: 1px solid #bee5eb;
        }}

        .status.disconnected {{
            background: #f8d7da;
            color: #721c24;
            border: 1px solid #f5c6cb;
        }}

        .status.connecting {{
            background: #fff3cd;
            color: #856404;
            border: 1px solid #ffeaa7;
        }}

        .quick-suggestions {{
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
            margin: 8px 0;
        }}

        .suggestion {{
            background: white;
            color: #667eea;
            border: 2px solid #667eea;
            padding: 4px 10px;
            border-radius: 12px;
            cursor: pointer;
            font-size: 12px;
            transition: all 0.3s ease;
        }}

        .suggestion:hover {{
            background: #667eea;
            color: white;
        }}

        @media (max-width: 768px) {{
            .container {{
                height: 90vh;
                padding: 15px;
                border-radius: 15px;
            }}
            
            .header h1 {{
                font-size: 1.5em;
            }}
            
            .message {{
                font-size: 0.85em;
                max-width: 90%;
            }}
            
            .suggestion {{
                font-size: 11px;
                padding: 3px 8px;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎙️ Travel Voice Agent</h1>
            <p>Your AI travel companion with voice and text chat</p>
        </div>

        <div id="status" class="status connecting">
            🔄 Connecting to Travel Agent...
        </div>

        <div class="chat-container">
            <div id="messages" class="messages">
                <!-- Messages will appear here -->
            </div>

            <div class="quick-suggestions">
                <div class="suggestion" onclick="sendSuggestion('Plan a trip to Japan')">Plan trip to Japan</div>
                <div class="suggestion" onclick="sendSuggestion('Best time to visit Europe')">Best time for Europe</div>
                <div class="suggestion" onclick="sendSuggestion('Budget travel tips')">Budget tips</div>
                <div class="suggestion" onclick="sendSuggestion('Family vacation ideas')">Family vacation</div>
            </div>

            <div class="input-area">
                <input 
                    type="text" 
                    id="messageInput" 
                    class="message-input" 
                    placeholder="Ask me about your next adventure..."
                    disabled
                >
                <button id="voiceButton" class="voice-button" onclick="toggleVoice()" disabled>
                    🎤
                </button>
                <button id="sendButton" class="send-button" onclick="sendMessage()" disabled>
                    Send
                </button>
            </div>
        </div>
    </div>

    <script>
        const WEBSOCKET_URL = '{ws_url}';
        
        class TravelAgentChat {{
            constructor() {{
                this.ws = null;
                this.isConnected = false;
                this.isRecording = false;
                this.recognition = null;
                this.synthesis = window.speechSynthesis;
                
                // Elements
                this.statusEl = document.getElementById('status');
                this.messagesEl = document.getElementById('messages');
                this.inputEl = document.getElementById('messageInput');
                this.sendBtn = document.getElementById('sendButton');
                this.voiceBtn = document.getElementById('voiceButton');
                
                // Initialize
                this.setupEventListeners();
                this.initializeSpeechRecognition();
                this.connect();
            }}
            
            setupEventListeners() {{
                // Enter key to send message
                this.inputEl.addEventListener('keypress', (e) => {{
                    if (e.key === 'Enter' && !e.shiftKey) {{
                        e.preventDefault();
                        this.sendMessage();
                    }}
                }});
            }}
            
            initializeSpeechRecognition() {{
                if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {{
                    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
                    this.recognition = new SpeechRecognition();
                    
                    this.recognition.continuous = false;
                    this.recognition.interimResults = true;
                    this.recognition.lang = 'en-US';
                    
                    this.recognition.onstart = () => {{
                        this.isRecording = true;
                        this.voiceBtn.classList.add('recording');
                        this.voiceBtn.innerHTML = '⏹️';
                        this.addMessage('Listening...', 'typing');
                    }};
                    
                    this.recognition.onresult = (event) => {{
                        const transcript = event.results[event.results.length - 1][0].transcript;
                        if (event.results[event.results.length - 1].isFinal) {{
                            this.removeTypingMessage();
                            this.inputEl.value = transcript;
                            this.sendMessage();
                        }}
                    }};
                    
                    this.recognition.onend = () => {{
                        this.isRecording = false;
                        this.voiceBtn.classList.remove('recording');
                        this.voiceBtn.innerHTML = '🎤';
                        this.removeTypingMessage();
                    }};
                    
                    this.recognition.onerror = (event) => {{
                        console.error('Speech recognition error:', event.error);
                        this.isRecording = false;
                        this.voiceBtn.classList.remove('recording');
                        this.voiceBtn.innerHTML = '🎤';
                        this.removeTypingMessage();
                    }};
                }} else {{
                    this.voiceBtn.style.display = 'none';
                }}
            }}
            
            connect() {{
                this.updateStatus('connecting', '🔄 Connecting to Travel Agent...');
                
                try {{
                    this.ws = new WebSocket(WEBSOCKET_URL);
                    
                    this.ws.onopen = () => {{
                        this.isConnected = true;
                        this.updateStatus('connected', '✅ Connected! Start chatting with your Travel Agent');
                        this.enableInterface();
                    }};
                    
                    this.ws.onmessage = (event) => {{
                        try {{
                            const data = JSON.parse(event.data);
                            this.handleMessage(data);
                        }} catch (error) {{
                            console.error('Error parsing message:', error);
                        }}
                    }};
                    
                    this.ws.onclose = () => {{
                        this.isConnected = false;
                        this.updateStatus('disconnected', '❌ Disconnected from Travel Agent');
                        this.disableInterface();
                        
                        // Try to reconnect after 5 seconds
                        setTimeout(() => {{
                            if (!this.isConnected) {{
                                this.connect();
                            }}
                        }}, 5000);
                    }};
                    
                    this.ws.onerror = (error) => {{
                        console.error('WebSocket error:', error);
                        this.updateStatus('disconnected', '❌ Connection error occurred');
                    }};
                }} catch (error) {{
                    console.error('WebSocket connection failed:', error);
                    this.updateStatus('disconnected', '❌ Failed to connect');
                }}
            }}
            
            handleMessage(data) {{
                switch (data.type) {{
                    case 'response':
                        this.removeTypingMessage();
                        this.addMessage(data.content, 'agent');
                        this.speakMessage(data.content);
                        break;
                    case 'typing':
                        if (data.content) {{
                            this.addMessage('Travel Agent is thinking...', 'typing');
                        }} else {{
                            this.removeTypingMessage();
                        }}
                        break;
                    case 'error':
                        this.removeTypingMessage();
                        this.addMessage('Sorry, there was an error: ' + data.content, 'agent');
                        break;
                }}
            }}
            
            sendMessage() {{
                const message = this.inputEl.value.trim();
                if (!message || !this.isConnected) return;
                
                this.addMessage(message, 'user');
                
                this.ws.send(JSON.stringify({{
                    type: 'message',
                    content: message
                }}));
                
                this.inputEl.value = '';
            }}
            
            sendSuggestion(suggestion) {{
                if (!this.isConnected) return;
                this.inputEl.value = suggestion;
                this.sendMessage();
            }}
            
            toggleVoice() {{
                if (!this.recognition) return;
                
                if (this.isRecording) {{
                    this.recognition.stop();
                }} else {{
                    this.recognition.start();
                }}
            }}
            
            speakMessage(text) {{
                const cleanText = text.replace(/[^\w\s.,!?-]/g, '');
                
                if (this.synthesis && cleanText) {{
                    this.synthesis.cancel();
                    
                    const utterance = new SpeechSynthesisUtterance(cleanText);
                    utterance.rate = 0.9;
                    utterance.pitch = 1;
                    utterance.volume = 0.6;
                    
                    const voices = this.synthesis.getVoices();
                    const naturalVoice = voices.find(voice => 
                        voice.lang.startsWith('en') && 
                        (voice.name.includes('Natural') || voice.name.includes('Neural'))
                    ) || voices.find(voice => voice.lang.startsWith('en'));
                    
                    if (naturalVoice) {{
                        utterance.voice = naturalVoice;
                    }}
                    
                    this.synthesis.speak(utterance);
                }}
            }}
            
            addMessage(content, type) {{
                const messageEl = document.createElement('div');
                messageEl.className = `message ${{type}}`;
                
                if (type === 'typing') {{
                    messageEl.innerHTML = `<span class="typing-dots"></span>`;
                    messageEl.id = 'typing-message';
                }} else {{
                    messageEl.textContent = content;
                }}
                
                this.messagesEl.appendChild(messageEl);
                this.scrollToBottom();
            }}
            
            removeTypingMessage() {{
                const typingMsg = document.getElementById('typing-message');
                if (typingMsg) {{
                    typingMsg.remove();
                }}
            }}
            
            scrollToBottom() {{
                this.messagesEl.scrollTop = this.messagesEl.scrollHeight;
            }}
            
            updateStatus(type, message) {{
                this.statusEl.className = `status ${{type}}`;
                this.statusEl.textContent = message;
            }}
            
            enableInterface() {{
                this.inputEl.disabled = false;
                this.sendBtn.disabled = false;
                this.voiceBtn.disabled = false;
                this.inputEl.focus();
            }}
            
            disableInterface() {{
                this.inputEl.disabled = true;
                this.sendBtn.disabled = true;
                this.voiceBtn.disabled = true;
            }}
        }}
        
        function sendMessage() {{
            chat.sendMessage();
        }}
        
        function toggleVoice() {{
            chat.toggleVoice();
        }}
        
        function sendSuggestion(suggestion) {{
            chat.sendSuggestion(suggestion);
        }}
        
        let chat;
        
        window.addEventListener('load', () => {{
            chat = new TravelAgentChat();
        }});
        
        document.addEventListener('visibilitychange', () => {{
            if (document.hidden && chat && chat.synthesis) {{
                chat.synthesis.cancel();
            }}
        }});
    </script>
</body>
</html>"""
        
        return web.Response(text=html_content, content_type='text/html')
    
    async def websocket_handler(self, request):
        """Handle WebSocket connections"""
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        
        connection_id = id(ws)
        self.connections.add(ws)
        logger.info(f"🔗 New WebSocket connection: {connection_id}")
        
        # Send welcome message
        welcome_message = {
            "type": "response",
            "content": "🌍 Welcome to your AI Travel Agent! I'm here to help plan your perfect trip. Where would you like to go, or what travel questions do you have?",
            "timestamp": datetime.now().isoformat()
        }
        await ws.send_str(json.dumps(welcome_message))
        
        try:
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                        
                        if data.get("type") == "message":
                            user_message = data.get("content", "")
                            logger.info(f"📝 Received: {user_message[:50]}...")
                            
                            # Send typing indicator
                            typing_msg = {
                                "type": "typing", 
                                "content": True,
                                "timestamp": datetime.now().isoformat()
                            }
                            await ws.send_str(json.dumps(typing_msg))
                            
                            # Get AI response
                            ai_response = await self.agent.get_travel_response(
                                user_message, str(connection_id)
                            )
                            
                            # Send response
                            response_msg = {
                                "type": "response",
                                "content": ai_response,
                                "timestamp": datetime.now().isoformat()
                            }
                            await ws.send_str(json.dumps(response_msg))
                            
                            # Stop typing indicator
                            typing_msg["content"] = False
                            await ws.send_str(json.dumps(typing_msg))
                        
                    except json.JSONDecodeError:
                        error_msg = {
                            "type": "error",
                            "content": "Invalid message format. Please send valid JSON.",
                            "timestamp": datetime.now().isoformat()
                        }
                        await ws.send_str(json.dumps(error_msg))
                        
                    except Exception as e:
                        logger.error(f"Error processing message: {e}")
                        error_msg = {
                            "type": "error", 
                            "content": "Sorry, I had trouble processing that message.",
                            "timestamp": datetime.now().isoformat()
                        }
                        await ws.send_str(json.dumps(error_msg))
                
                elif msg.type == WSMsgType.ERROR:
                    logger.error(f'WebSocket error: {ws.exception()}')
        
        except Exception as e:
            logger.error(f"WebSocket handler error: {e}")
        
        finally:
            self.connections.discard(ws)
            # Clean up conversation history
            if str(connection_id) in self.agent.conversations:
                del self.agent.conversations[str(connection_id)]
            logger.info(f"🔌 WebSocket connection {connection_id} closed")
        
        return ws
    
    async def start_server(self):
        """Start the HTTP + WebSocket server"""
        logger.info(f"🚀 Starting Travel Agent Server on http://{self.host}:{self.port}")
        
        runner = web.AppRunner(self.app)
        await runner.setup()
        
        site = web.TCPSite(runner, self.host, self.port)
        await site.start()
        
        print(f"""
╔══════════════════════════════════════════════════════════════╗
║                    🎙️ TRAVEL VOICE AGENT                     ║
║                                                              ║
║  🌍 AI Travel Assistant is running!                         ║
║  🌐 HTTP Server: http://{self.host}:{self.port}                    ║
║  🔗 Chat Interface: http://{self.host}:{self.port}/chat           ║
║  ⚡ WebSocket: ws://{self.host}:{self.port}/ws                    ║
║  ❤️ Health Check: http://{self.host}:{self.port}/health           ║
║                                                              ║
║  💡 The agent can help with:                                ║
║     • Destination recommendations                           ║
║     • Travel planning and itineraries                      ║
║     • Weather and seasonal advice                          ║
║     • Budget planning and tips                             ║
║     • Cultural insights and customs                        ║
║     • Food and activity recommendations                    ║
║                                                              ║
║  ⏹️ Press Ctrl+C to stop                                     ║
╚══════════════════════════════════════════════════════════════╝
        """)
        
        return runner

async def main():
    """Main function to run the Travel Agent server"""
    
    # Check environment variables
    if not os.getenv("OPENAI_API_KEY"):
        print("❌ Error: OPENAI_API_KEY not found")
        print("Please set environment variable: OPENAI_API_KEY=your_api_key_here")
        print("Get your API key from: https://platform.openai.com/api-keys")
        return
    
    try:
        # Create and start server
        server = TravelAgentServer()
        runner = await server.start_server()
        
        # Keep server running
        try:
            await asyncio.Future()  # Run forever
        except KeyboardInterrupt:
            print("\n👋 Travel Agent shutting down... Safe travels! ✈️")
        finally:
            await runner.cleanup()
        
    except Exception as e:
        print(f"❌ Error starting server: {e}")
        logger.error(f"Server error: {e}")

if __name__ == "__main__":
    asyncio.run(main())