import httpx
from typing import Optional
from langchain.tools import BaseTool
from pydantic import Field

from ..models.travel_models import WeatherInfo
from ..utils.config import Config

class WeatherTool(BaseTool):
    """Tool for getting weather information using OpenWeatherMap API"""
    
    name: str = "get_weather"
    description: str = "Get current weather information for a specific location. Input should be a city name or 'city, country'."
    
    def _run(self, location: str) -> str:
        """Get weather for a location"""
        if not Config.OPENWEATHER_API_KEY:
            return "Weather information is not available. API key not configured."
        
        try:
            weather_info = self._fetch_weather(location)
            if weather_info:
                return self._format_weather_response(weather_info)
            else:
                return f"Could not find weather information for {location}. Please check the city name."
        except Exception as e:
            return f"Error getting weather information: {str(e)}"
    
    async def _arun(self, location: str) -> str:
        """Async version"""
        return self._run(location)
    
    def _fetch_weather(self, location: str) -> Optional[WeatherInfo]:
        """Fetch weather data from OpenWeatherMap API"""
        base_url = "http://api.openweathermap.org/data/2.5/weather"
        
        params = {
            "q": location,
            "appid": Config.OPENWEATHER_API_KEY,
            "units": "metric"  # Celsius
        }
        
        try:
            with httpx.Client() as client:
                response = client.get(base_url, params=params)
                response.raise_for_status()
                data = response.json()
                
                return WeatherInfo(
                    location=f"{data['name']}, {data['sys']['country']}",
                    temperature=data['main']['temp'],
                    description=data['weather'][0]['description'].title(),
                    humidity=data['main']['humidity'],
                    wind_speed=data['wind'].get('speed', 0)
                )
        except httpx.RequestError:
            return None
        except KeyError:
            return None
    
    def _format_weather_response(self, weather: WeatherInfo) -> str:
        """Format weather information for user"""
        response = f"🌤️ Weather in {weather.location}:\n"
        response += f"Temperature: {weather.temperature}°C\n"
        response += f"Conditions: {weather.description}\n"
        response += f"Humidity: {weather.humidity}%"
        
        if weather.wind_speed:
            response += f"\nWind Speed: {weather.wind_speed} m/s"
        
        return response