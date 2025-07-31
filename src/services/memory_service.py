from typing import List, Dict, Optional
from langchain.memory import ConversationBufferWindowMemory
from langchain.schema import BaseMessage, HumanMessage, AIMessage

from ..models.travel_models import ChatMessage, TravelQuery

class TravelMemoryService:
    """Enhanced memory service for travel conversations"""
    
    def __init__(self, window_size: int = 10):
        self.conversations: Dict[str, ConversationBufferWindowMemory] = {}
        self.user_preferences: Dict[str, Dict] = {}
        self.window_size = window_size
    
    def get_memory(self, session_id: str) -> ConversationBufferWindowMemory:
        """Get or create memory for a session"""
        if session_id not in self.conversations:
            self.conversations[session_id] = ConversationBufferWindowMemory(
                k=self.window_size,
                return_messages=True
            )
        return self.conversations[session_id]
    
    def add_message(self, session_id: str, message: ChatMessage):
        """Add message to conversation memory"""
        memory = self.get_memory(session_id)
        
        if message.role == "user":
            memory.chat_memory.add_user_message(message.content)
            # Extract travel preferences
            self._extract_preferences(session_id, message.content)
        elif message.role == "assistant":
            memory.chat_memory.add_ai_message(message.content)
    
    def get_conversation_history(self, session_id: str) -> List[BaseMessage]:
        """Get conversation history as LangChain messages"""
        memory = self.get_memory(session_id)
        return memory.chat_memory.messages
    
    def get_context_summary(self, session_id: str) -> str:
        """Get a summary of the conversation context"""
        memory = self.get_memory(session_id)
        messages = memory.chat_memory.messages
        
        if not messages:
            return "New conversation started."
        
        # Extract key information
        destinations_mentioned = set()
        preferences = self.user_preferences.get(session_id, {})
        
        for message in messages:
            if isinstance(message, HumanMessage):
                content_lower = message.content.lower()
                # Simple destination extraction
                for destination in ["japan", "paris", "tokyo", "london", "new york", "bali", "thailand", "italy"]:
                    if destination in content_lower:
                        destinations_mentioned.add(destination.title())
        
        summary = f"Conversation history: {len(messages)} messages exchanged. "
        
        if destinations_mentioned:
            summary += f"Destinations discussed: {', '.join(destinations_mentioned)}. "
        
        if preferences:
            pref_list = []
            if preferences.get('budget'):
                pref_list.append(f"Budget: {preferences['budget']}")
            if preferences.get('interests'):
                pref_list.append(f"Interests: {', '.join(preferences['interests'])}")
            if pref_list:
                summary += f"User preferences: {'; '.join(pref_list)}."
        
        return summary
    
    def _extract_preferences(self, session_id: str, message: str):
        """Extract and store user travel preferences"""
        if session_id not in self.user_preferences:
            self.user_preferences[session_id] = {}
        
        prefs = self.user_preferences[session_id]
        message_lower = message.lower()
        
        # Extract budget preferences
        if any(word in message_lower for word in ["budget", "cheap", "expensive", "affordable"]):
            if "budget" in message_lower or "cheap" in message_lower or "affordable" in message_lower:
                prefs["budget"] = "budget-friendly"
            elif "expensive" in message_lower or "luxury" in message_lower:
                prefs["budget"] = "luxury"
        
        # Extract interests
        interests = []
        interest_keywords = {
            "adventure": ["adventure", "hiking", "climbing", "extreme"],
            "culture": ["culture", "museum", "history", "heritage"],
            "food": ["food", "cuisine", "restaurant", "eating"],
            "beach": ["beach", "ocean", "swimming", "resort"],
            "city": ["city", "urban", "shopping", "nightlife"],
            "nature": ["nature", "wildlife", "national park", "scenic"]
        }
        
        for interest_type, keywords in interest_keywords.items():
            if any(keyword in message_lower for keyword in keywords):
                interests.append(interest_type)
        
        if interests:
            prefs["interests"] = list(set(prefs.get("interests", []) + interests))
    
    def get_user_preferences(self, session_id: str) -> Dict:
        """Get stored user preferences"""
        return self.user_preferences.get(session_id, {})
    
    def clear_session(self, session_id: str):
        """Clear conversation and preferences for a session"""
        if session_id in self.conversations:
            del self.conversations[session_id]
        if session_id in self.user_preferences:
            del self.user_preferences[session_id]
    
    def get_relevant_context(self, session_id: str, current_query: str) -> str:
        """Get relevant context for the current query"""
        preferences = self.get_user_preferences(session_id)
        history_summary = self.get_context_summary(session_id)
        
        context = f"Context: {history_summary}\n"
        
        if preferences:
            context += "User preferences: "
            if preferences.get("budget"):
                context += f"Budget style: {preferences['budget']}. "
            if preferences.get("interests"):
                context += f"Interests: {', '.join(preferences['interests'])}. "
        
        return context