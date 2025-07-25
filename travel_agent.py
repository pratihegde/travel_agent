#!/usr/bin/env python3

import asyncio
import websockets
import json
import os
import logging
from datetime import datetime
from typing import Dict, List
import openai
from dotenv import load_dotenv

import os
if os.path.exists('.env'):
    load_dotenv()  # Only load .env in development

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TravelAgent:
    """AI Travel Agent with conversation memory and travel expertise"""
    
    def __init__(self):
        # Initialize OpenAI client
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            print("Available environment variables:")
            for key in os.environ:
                if 'OPENAI' in key or 'API' in key:
                    print(f"{key}: {os.environ[key][:10]}...")
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
• Start with "Hello beautiful soul, I'm here to help you plan your perfect trip. How can I assist you today?"



RESPONSE GUIDELINES:
• Keep responses conversational and engaging
• Provide concrete examples and specific advice
• Include relevant details like costs, timing, booking tips
• Suggest follow-up questions or next steps
• Prioritize traveler safety and current information
• Use clean, natural language without markdown formatting, asterisks, or hash symbols
• Write in flowing paragraphs with clear sentences instead of bullet points or lists
• Dont make the sentences bold as it gives * symbols in the response


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
    """WebSocket server for the Travel Agent"""
    
    def __init__(self, host="0.0.0.0", port=None):
        self.host = host
        # Use Railway's PORT or default to 8765
        self.port = port or int(os.getenv("PORT", 8765))
        self.agent = TravelAgent()
        self.connections = set()
        logger.info(f"🌐 Travel Agent Server initialized on {host}:{self.port}")
    
    async def handle_connection(self, websocket, path):
        """Handle new WebSocket connection"""
        connection_id = id(websocket)
        self.connections.add(websocket)
        logger.info(f"🔗 New connection: {connection_id}")
        
        # Send welcome message
        welcome_message = {
            "type": "response",
            "content": "🌍 Welcome to your AI Travel Agent! I'm here to help plan your perfect trip. Where would you like to go, or what travel questions do you have?",
            "timestamp": datetime.now().isoformat()
        }
        await websocket.send(json.dumps(welcome_message))
        
        try:
            async for message in websocket:
                try:
                    # Parse incoming message
                    data = json.loads(message)
                    
                    if data.get("type") == "message":
                        user_message = data.get("content", "")
                        logger.info(f"📝 Received: {user_message[:50]}...")
                        
                        # Send typing indicator
                        typing_msg = {
                            "type": "typing", 
                            "content": True,
                            "timestamp": datetime.now().isoformat()
                        }
                        await websocket.send(json.dumps(typing_msg))
                        
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
                        await websocket.send(json.dumps(response_msg))
                        
                        # Stop typing indicator
                        typing_msg["content"] = False
                        await websocket.send(json.dumps(typing_msg))
                    
                except json.JSONDecodeError:
                    error_msg = {
                        "type": "error",
                        "content": "Invalid message format. Please send valid JSON.",
                        "timestamp": datetime.now().isoformat()
                    }
                    await websocket.send(json.dumps(error_msg))
                    
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    error_msg = {
                        "type": "error", 
                        "content": "Sorry, I had trouble processing that message.",
                        "timestamp": datetime.now().isoformat()
                    }
                    await websocket.send(json.dumps(error_msg))
        
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"🔌 Connection {connection_id} closed")
        
        finally:
            self.connections.discard(websocket)
            # Clean up conversation history
            if str(connection_id) in self.agent.conversations:
                del self.agent.conversations[str(connection_id)]
    
    async def start_server(self):
        """Start the WebSocket server"""
        logger.info(f"🚀 Starting Travel Agent Server on ws://{self.host}:{self.port}")
        
        async with websockets.serve(self.handle_connection, self.host, self.port):
            print(f"""
╔══════════════════════════════════════════════════════════════╗
║                    🎙️ TRAVEL VOICE AGENT                     ║
║                                                              ║
║  🌍 AI Travel Assistant is running!                         ║
║  🌐 WebSocket server: ws://{self.host}:{self.port}                    ║
║  🔗 Connect via the web interface to start chatting         ║
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
            
            # Keep server running
            await asyncio.Future()  # Run forever

async def main():
    """Main function to run the Travel Agent server"""
    
    # Check environment variables
    if not os.getenv("OPENAI_API_KEY"):
        print("❌ Error: OPENAI_API_KEY not found")
        print("Please create a .env file with: OPENAI_API_KEY=your_api_key_here")
        print("Get your API key from: https://platform.openai.com/api-keys")
        return
    
    try:
        # Create and start server
        server = TravelAgentServer()
        await server.start_server()
        
    except KeyboardInterrupt:
        print("\n👋 Travel Agent shutting down... Safe travels! ✈️")
    except Exception as e:
        print(f"❌ Error starting server: {e}")
        logger.error(f"Server error: {e}")

if __name__ == "__main__":
    asyncio.run(main())