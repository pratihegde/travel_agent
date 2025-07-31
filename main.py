#!/usr/bin/env python3

import asyncio
import os
from datetime import datetime
from aiohttp import web
import aiofiles

from src.api.websocket_handler import WebSocketHandler
from src.utils.config import Config
from src.utils.logger import get_logger

logger = get_logger(__name__)

class TravelAgentServer:
    """Main server for the Travel Agent application"""
    
    def __init__(self):
        self.app = web.Application()
        self.websocket_handler = WebSocketHandler()
        self.setup_routes()
        
    def setup_routes(self):
        """Setup HTTP and WebSocket routes"""
        # Health check endpoint
        self.app.router.add_get('/', self.health_check)
        self.app.router.add_get('/health', self.health_check)
        
        # Serve the web interface
        self.app.router.add_get('/chat', self.serve_chat_interface)
        
        # WebSocket endpoint
        self.app.router.add_get('/ws', self.websocket_handler.handle_websocket)
        
        # Static files
        self.app.router.add_static('/', 'static/', name='static')
    
    async def health_check(self, request):
        """Health check endpoint"""
        available_tools = Config.get_available_tools()
        
        return web.json_response({
            "status": "healthy",
            "service": "Enhanced Travel Agent",
            "timestamp": datetime.now().isoformat(),
            "version": "2.0",
            "features": {
                "langchain_agent": True,
                "real_time_weather": "weather" in available_tools,
                "currency_conversion": True,
                "maps_integration": "maps" in available_tools,
                "tripadvisor_data": "tripadvisor" in available_tools,
                "conversation_memory": True,
                "user_preferences": True
            },
            "endpoints": {
                "websocket": "/ws",
                "chat_interface": "/chat",
                "health": "/health"
            },
            "tools_available": len(available_tools),
            "tools_list": available_tools
        })
    
    async def serve_chat_interface(self, request):
        """Serve the enhanced chat web interface"""
        # Check if static file exists
        static_file = "static/index.html"
        if os.path.exists(static_file):
            async with aiofiles.open(static_file, 'r', encoding='utf-8') as f:
                content = await f.read()
            return web.Response(text=content, content_type='text/html')
        
        # Fallback: serve embedded interface
        return await self.serve_embedded_interface(request)
    
    async def serve_embedded_interface(self, request):
        """Serve embedded chat interface if static file doesn't exist"""
        # Get the WebSocket URL
        scheme = 'wss' if request.secure else 'ws'
        ws_url = f"{scheme}://{request.host}/ws"
        
        available_tools = Config.get_available_tools()
        features_list = []
        
        if "weather" in available_tools:
            features_list.append("🌤️ Real-time weather")
        if "tripadvisor" in available_tools:
            features_list.append("🍽️ Restaurant & hotel recommendations")
        if "maps" in available_tools:
            features_list.append("🗺️ Maps & distances")
        
        features_list.append("💱 Currency conversion")
        features_text = " • ".join(features_list)
        
        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Enhanced Travel Voice Agent</title>
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
            max-width: 900px;
            width: 100%;
            height: 85vh;
            min-height: 600px;
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
            font-size: 2em;
            margin-bottom: 5px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }}

        .header p {{
            color: #666;
            font-size: 0.9em;
            margin-bottom: 5px;
        }}

        .features {{
            background: #f8f9fa;
            padding: 8px 12px;
            border-radius: 10px;
            font-size: 0.8em;
            color: #495057;
            border: 1px solid #e9ecef;
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
            padding: 12px 16px;
            border-radius: 18px;
            max-width: 85%;
            animation: slideIn 0.3s ease;
            font-size: 0.9em;
            line-height: 1.5;
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
            padding: 12px 16px;
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
            padding: 12px 18px;
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
            padding: 10px;
            border-radius: 10px;
            margin: 8px 0;
            font-weight: bold;
            font-size: 0.9em;
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
            gap: 8px;
            margin: 10px 0;
        }}

        .suggestion {{
            background: white;
            color: #667eea;
            border: 2px solid #667eea;
            padding: 6px 12px;
            border-radius: 15px;
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
                font-size: 1.6em;
            }}
            
            .features {{
                font-size: 0.75em;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎙️ Enhanced Travel Agent</h1>
            <p>Your AI travel companion with LangChain & real-time data</p>
            <div class="features">
                {features_text}
            </div>
        </div>

        <div id="status" class="status connecting">
            🔄 Connecting to Enhanced Travel Agent...
        </div>

        <div class="chat-container">
            <div id="messages" class="messages">
                <!-- Messages will appear here -->
            </div>

            <div class="quick-suggestions">
                <div class="suggestion" onclick="sendSuggestion('Plan a 7-day trip to Japan')">Japan itinerary</div>
                <div class="suggestion" onclick="sendSuggestion('Weather in Paris next week')">Paris weather</div>
                <div class="suggestion" onclick="sendSuggestion('Convert 1000 USD to EUR')">Currency converter</div>
                <div class="suggestion" onclick="sendSuggestion('Best restaurants in Tokyo')">Tokyo restaurants</div>
                <div class="suggestion" onclick="sendSuggestion('Budget travel tips for Europe')">Europe budget tips</div>
            </div>

            <div class="input-area">
                <input 
                    type="text" 
                    id="messageInput" 
                    class="message-input" 
                    placeholder="Ask me about destinations, weather, restaurants, hotels..."
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
        
        class EnhancedTravelChat {{
            constructor() {{
                this.ws = null;
                this.isConnected = false;
                this.isRecording = false;
                this.recognition = null;
                this.synthesis = window.speechSynthesis;
                
                this.statusEl = document.getElementById('status');
                this.messagesEl = document.getElementById('messages');
                this.inputEl = document.getElementById('messageInput');
                this.sendBtn = document.getElementById('sendButton');
                this.voiceBtn = document.getElementById('voiceButton');
                
                this.setupEventListeners();
                this.initializeSpeechRecognition();
                this.connect();
            }}
            
            setupEventListeners() {{
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
                this.updateStatus('connecting', '🔄 Connecting to Enhanced Travel Agent...');
                
                try {{
                    this.ws = new WebSocket(WEBSOCKET_URL);
                    
                    this.ws.onopen = () => {{
                        this.isConnected = true;
                        this.updateStatus('connected', '✅ Connected! Enhanced Travel Agent ready');
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
                            this.addMessage('Enhanced Travel Agent is thinking...', 'typing');
                        }} else {{
                            this.removeTypingMessage();
                        }}
                        break;
                    case 'error':
                        this.removeTypingMessage();
                        this.addMessage('Sorry, there was an error: ' + data.content, 'agent');
                        break;
                    case 'session_info':
                        console.log('Session info:', data.content);
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
                const cleanText = text.replace(/[^\\w\\s.,!?-]/g, '');
                
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
            chat = new EnhancedTravelChat();
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

async def main():
    """Main function to run the Enhanced Travel Agent server"""
    
    try:
        # Validate configuration
        Config.validate()
        logger.info("✅ Configuration validated")
        
        # Create server
        server = TravelAgentServer()
        
        # Start server
        runner = web.AppRunner(server.app)
        await runner.setup()
        
        site = web.TCPSite(runner, Config.HOST, Config.PORT)
        await site.start()
        
        available_tools = Config.get_available_tools()
        
        print(f"""
╔══════════════════════════════════════════════════════════════════════════╗
║                    🎙️ ENHANCED TRAVEL VOICE AGENT                        ║
║                          Powered by LangChain                           ║
║                                                                          ║
║  🌍 AI Travel Assistant is running with advanced capabilities!          ║
║  🌐 HTTP Server: http://{Config.HOST}:{Config.PORT}                               ║
║  🔗 Chat Interface: http://{Config.HOST}:{Config.PORT}/chat                       ║
║  ⚡ WebSocket: ws://{Config.HOST}:{Config.PORT}/ws                               ║
║  ❤️ Health Check: http://{Config.HOST}:{Config.PORT}/health                      ║
║                                                                          ║
║  🛠️ Available Tools: {len(available_tools):<2} / 4                                        ║""")

        if "weather" in available_tools:
            print("║     ✅ Weather API - Real-time weather data                          ║")
        else:
            print("║     ❌ Weather API - Not configured                                  ║")
            
        if "tripadvisor" in available_tools:
            print("║     ✅ TripAdvisor API - Restaurant & hotel data                     ║")
        else:
            print("║     ❌ TripAdvisor API - Not configured                              ║")
            
        if "maps" in available_tools:
            print("║     ✅ Google Maps API - Location & distance data                    ║")
        else:
            print("║     ❌ Google Maps API - Not configured                              ║")
            
        print("║     ✅ Currency API - Exchange rates (always available)             ║")

        print(f"""║                                                                          ║
║  🚀 New Features:                                                       ║
║     • LangChain agent framework for smart tool selection               ║
║     • Conversation memory with user preference learning                ║
║     • Enhanced error handling and fallback strategies                  ║
║     • Real-time data integration from multiple APIs                    ║
║     • Improved natural language processing                             ║
║                                                                          ║
║  ⏹️ Press Ctrl+C to stop                                                 ║
╚══════════════════════════════════════════════════════════════════════════╝
        """)
        
        # Keep server running
        try:
            await asyncio.Future()  # Run forever
        except KeyboardInterrupt:
            print("\n👋 Enhanced Travel Agent shutting down... Safe travels! ✈️")
        finally:
            await runner.cleanup()
        
    except ValueError as e:
        print(f"❌ Configuration Error: {e}")
        print("Please check your .env file and ensure OPENAI_API_KEY is set")
    except Exception as e:
        print(f"❌ Error starting server: {e}")
        logger.error(f"Server error: {e}")

if __name__ == "__main__":
    asyncio.run(main())