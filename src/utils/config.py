import os
from typing import Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    """Application configuration management"""
    
    # Required
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    
    # Server
    PORT: int = int(os.getenv("PORT", 8080))
    HOST: str = os.getenv("HOST", "0.0.0.0")
    
    # Optional APIs (free tier)
    OPENWEATHER_API_KEY: Optional[str] = os.getenv("OPENWEATHER_API_KEY")
    GOOGLE_MAPS_API_KEY: Optional[str] = os.getenv("GOOGLE_MAPS_API_KEY")
    TRIPADVISOR_API_KEY: Optional[str] = os.getenv("TRIPADVISOR_API_KEY")
    
    # App settings
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    
    @classmethod
    def validate(cls) -> bool:
        """Validate required configuration"""
        if not cls.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is required")
        return True
    
    @classmethod
    def get_available_tools(cls) -> list:
        """Return list of available tools based on API keys"""
        tools = ["basic_search", "travel_advice"]  # Always available
        
        if cls.OPENWEATHER_API_KEY:
            tools.append("weather")
        
        if cls.GOOGLE_MAPS_API_KEY:
            tools.append("maps")
        
        if cls.TRIPADVISOR_API_KEY:
            tools.append("tripadvisor")
            
        tools.append("currency")  # Free API, no key needed
        
        return tools