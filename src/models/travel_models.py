from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class WeatherInfo(BaseModel):
    """Weather information model"""
    location: str
    temperature: float
    description: str
    humidity: Optional[int] = None
    wind_speed: Optional[float] = None
    timestamp: datetime = Field(default_factory=datetime.now)

class CurrencyRate(BaseModel):
    """Currency exchange rate model"""
    from_currency: str
    to_currency: str
    rate: float
    timestamp: datetime = Field(default_factory=datetime.now)

class Destination(BaseModel):
    """Travel destination model"""
    name: str
    country: str
    description: Optional[str] = None
    best_time_to_visit: Optional[str] = None
    budget_range: Optional[str] = None
    highlights: List[str] = []
    weather: Optional[WeatherInfo] = None

class TravelQuery(BaseModel):
    """User travel query model"""
    destination: Optional[str] = None
    budget: Optional[str] = None
    duration: Optional[str] = None
    interests: List[str] = []
    travel_date: Optional[str] = None
    travelers: Optional[int] = 1

class ChatMessage(BaseModel):
    """Chat message model"""
    role: str  # user, assistant, system
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)
    metadata: Dict[str, Any] = Field(default_factory=dict)

class TravelRecommendation(BaseModel):
    """Travel recommendation model"""
    destination: Destination
    reasoning: str
    estimated_cost: Optional[str] = None
    suggested_duration: Optional[str] = None
    best_activities: List[str] = []