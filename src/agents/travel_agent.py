from typing import List, Dict, Any, Optional
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.schema import BaseMessage

from ..tools.weather_tool import WeatherTool
from ..tools.currency_tool import CurrencyTool
from ..tools.maps_tool import MapsTool
from ..tools.tripadvisor_tool import TripAdvisorTool
from ..services.memory_service import TravelMemoryService
from ..models.travel_models import ChatMessage, TravelRecommendation
from ..utils.config import Config
from ..utils.logger import get_logger

logger = get_logger(__name__)

class TravelAgent:
    """Advanced AI Travel Agent with LangChain and multiple tools"""
    
    def __init__(self):
        # Validate configuration
        Config.validate()
        
        # Initialize LLM
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.7,
            api_key=Config.OPENAI_API_KEY
        )
        
        # Initialize tools
        self.tools = self._initialize_tools()
        
        # Initialize memory service
        self.memory_service = TravelMemoryService()
        
        # Create agent
        self.agent_executor = self._create_agent()
        
        logger.info(f"🤖 Travel Agent initialized with {len(self.tools)} tools")
    
    def _initialize_tools(self) -> List:
        """Initialize available tools based on configuration"""
        tools = []
        available_tools = Config.get_available_tools()
        
        # Always available tools
        tools.append(CurrencyTool())
        logger.info("✅ Currency tool loaded")
        
        # Conditional tools based on API keys
        if "weather" in available_tools:
            tools.append(WeatherTool())
            logger.info("✅ Weather tool loaded")
        
        if "maps" in available_tools:
            tools.append(MapsTool())
            logger.info("✅ Maps tool loaded")
        else:
            logger.info("⚠️ Maps tool not available (no API key)")
        
        if "tripadvisor" in available_tools:
            tools.append(TripAdvisorTool())
            logger.info("✅ TripAdvisor tool loaded")
        else:
            logger.info("⚠️ TripAdvisor tool not available (no API key)")
        
        return tools
    
    def _create_agent(self) -> AgentExecutor:
        """Create LangChain agent with tools"""
        
        # Create prompt template
        prompt = ChatPromptTemplate.from_messages([
            ("system", self._get_system_prompt()),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad")
        ])
        
        # Create agent
        agent = create_openai_tools_agent(
            llm=self.llm,
            tools=self.tools,
            prompt=prompt
        )
        
        # Create executor
        return AgentExecutor(
            agent=agent,
            tools=self.tools,
            verbose=Config.DEBUG,
            max_iterations=3,
            early_stopping_method="generate"
        )
    
    def _get_system_prompt(self) -> str:
        """Get the system prompt for the travel agent"""
        available_tools = Config.get_available_tools()
        
        prompt = """You are TravelBot, an expert AI travel agent with access to real-time data and specialized tools. You provide personalized, helpful travel advice.

CORE EXPERTISE:
• Destination recommendations based on preferences, budget, season
• Detailed itinerary planning and logistics
• Cultural insights and local customs
• Budget planning and cost-saving strategies
• Weather patterns and best travel times
• Food recommendations and dining tips
• Transportation options and booking advice
• Safety tips and travel requirements

AVAILABLE TOOLS:"""

        if "weather" in available_tools:
            prompt += "\n• Weather Tool: Get current weather conditions for any location"
        
        prompt += "\n• Currency Tool: Convert currencies and get exchange rates"
        
        if "maps" in available_tools:
            prompt += "\n• Maps Tool: Get location details, coordinates, and distances between places"
        
        if "tripadvisor" in available_tools:
            prompt += "\n• TripAdvisor Tool: Search for restaurants, hotels, and attractions with real ratings and reviews"

        prompt += """

CRITICAL RESPONSE FORMAT REQUIREMENTS:
You MUST return responses in this EXACT JSON-like structure. NO exceptions:

DESTINATIONS:
Tokyo - Modern metropolis with traditional temples
Kyoto - Ancient capital with beautiful shrines
Osaka - Food paradise and vibrant nightlife

HOTELS:
Hotel Gracery Shinjuku - Modern hotel near Godzilla head
Ryokan Yoshinoya - Traditional Japanese inn experience

RESTAURANTS:
Sukiyabashi Jiro - World-famous sushi restaurant
Ichiran Ramen - Customizable tonkotsu ramen chain

ACTIVITIES:
Visit Senso-ji Temple - Tokyo's oldest Buddhist temple
Experience Robot Restaurant - Unique dinner show

TRANSPORTATION:
JR Pass - Unlimited train travel for tourists
Tokyo Metro - Efficient subway system

BUDGET:
Accommodation - ¥8,000-15,000 per night
Meals - ¥3,000-8,000 per day
Activities - ¥2,000-5,000 per attraction

TIMING:
Spring (March-May) - Cherry blossom season, mild weather
Summer (June-August) - Hot and humid, festival season
Fall (September-November) - Comfortable weather, autumn colors
Winter (December-February) - Cold but clear, fewer crowds

IMPORTANT RULES:
1. Use category headers: DESTINATIONS, HOTELS, RESTAURANTS, ACTIVITIES, TRANSPORTATION, BUDGET, TIMING
2. Each item format: "Name/Title - Brief description (1 line max)"
3. Use relevant categories based on the user's question
4. Keep descriptions concise and informative
5. NO asterisks, NO markdown, NO long paragraphs
6. If using tools, integrate the data into this exact format

Example of perfect response:
DESTINATIONS:
Paris - City of lights with iconic Eiffel Tower
Lyon - Culinary capital with historic architecture

RESTAURANTS:
Le Comptoir du Relais - Classic French bistro in Saint-Germain
L'As du Fallafel - Famous falafel in the Marais district

Remember: ALWAYS use this exact structure. No exceptions!"""

        return prompt
    
    def _parse_structured_response(self, response: str) -> dict:
        """Parse structured response into categories"""
        import re
        
        categories = {}
        current_category = None
        
        lines = response.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Check if it's a category header
            category_match = re.match(r'^([A-Z][A-Z\s&]+):?\s*$', line)
            if category_match:
                current_category = category_match.group(1).strip(':')
                categories[current_category] = []
                continue
            
            # Check if it's an item (with or without bullet)
            item_match = re.match(r'^[•\-*]?\s*(.+)\s*-\s*(.+)$', line)
            if item_match and current_category:
                name = item_match.group(1).strip()
                description = item_match.group(2).strip()
                categories[current_category].append({
                    'name': name,
                    'description': description
                })
                continue
            
            # Fallback: treat as a simple item
            if current_category and line:
                if ' - ' in line:
                    parts = line.split(' - ', 1)
                    categories[current_category].append({
                        'name': parts[0].strip(),
                        'description': parts[1].strip()
                    })
                else:
                    categories[current_category].append({
                        'name': line,
                        'description': ''
                    })
        
        return categories

    async def get_response(self, message: str, session_id: str) -> str:
        """Get response from travel agent with structured formatting"""
        try:
            # Add user message to memory
            user_message = ChatMessage(role="user", content=message)
            self.memory_service.add_message(session_id, user_message)
            
            # Get conversation history
            chat_history = self.memory_service.get_conversation_history(session_id)
            
            # Get relevant context
            context = self.memory_service.get_relevant_context(session_id, message)
            
            # Enhance input with context
            enhanced_input = f"{context}\n\nUser Query: {message}"
            
            # Get agent response
            response = await self.agent_executor.ainvoke({
                "input": enhanced_input,
                "chat_history": chat_history
            })
            
            ai_response = response["output"]
            
            # Parse structured response
            structured_data = self._parse_structured_response(ai_response)
            
            # Format for frontend
            formatted_response = self._format_for_frontend(structured_data)
            
            # Add AI response to memory (store original)
            ai_message = ChatMessage(role="assistant", content=ai_response)
            self.memory_service.add_message(session_id, ai_message)
            
            logger.info(f"🎯 Generated structured response for session {session_id[:8]}...")
            return formatted_response
            
        except Exception as e:
            error_msg = "I'm sorry, I'm having trouble processing your request right now. Please try again in a moment."
            logger.error(f"Error in get_response: {e}")
            return error_msg
    
    def _format_for_frontend(self, structured_data: dict) -> str:
        """Format structured data for frontend consumption with special markers"""
        if not structured_data:
            return "I can help you with travel planning! What would you like to know?"
        
        # Create a special format that the frontend can parse
        formatted = "STRUCTURED_DATA_START\n"
        
        for category, items in structured_data.items():
            if items:
                formatted += f"CATEGORY:{category}\n"
                for item in items:
                    name = item.get('name', '')
                    description = item.get('description', '')
                    formatted += f"ITEM:{name}|{description}\n"
                formatted += "CATEGORY_END\n"
        
        formatted += "STRUCTURED_DATA_END"
        return formatted
    
    def get_session_info(self, session_id: str) -> Dict[str, Any]:
        """Get information about the current session"""
        preferences = self.memory_service.get_user_preferences(session_id)
        context_summary = self.memory_service.get_context_summary(session_id)
        available_tools = Config.get_available_tools()
        
        return {
            "session_id": session_id,
            "user_preferences": preferences,
            "context_summary": context_summary,
            "available_tools": available_tools,
            "total_tools": len(self.tools)
        }
    
    def clear_session(self, session_id: str):
        """Clear session data"""
        self.memory_service.clear_session(session_id)
        logger.info(f"🧹 Cleared session {session_id}")
    
    def get_welcome_message(self) -> str:
        """Get welcome message for new users"""
        available_tools = Config.get_available_tools()
        capabilities = []
        
        if "weather" in available_tools:
            capabilities.append("real-time weather information")
        if "tripadvisor" in available_tools:
            capabilities.append("restaurant and hotel recommendations")
        if "maps" in available_tools:
            capabilities.append("location details and distances")
        
        capabilities.append("currency conversion")
        
        message = "🌍 Welcome to your AI Travel Agent! I'm here to help plan your perfect trip. "
        
        if capabilities:
            message += f"I have access to {', '.join(capabilities[:-1])}"
            if len(capabilities) > 1:
                message += f", and {capabilities[-1]}. "
            else:
                message += ". "
        
        message += "Where would you like to go, or what travel questions do you have?"
        
        return message