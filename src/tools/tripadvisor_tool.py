import httpx
from typing import Optional, List, Dict, Any
from langchain.tools import BaseTool
from pydantic import Field

from ..utils.config import Config

class TripAdvisorTool(BaseTool):
    """Tool for getting restaurant, hotel, and attraction data from TripAdvisor API"""
    
    name: str = "search_tripadvisor"
    description: str = "Search for restaurants, hotels, or attractions in a specific location. Input should be 'TYPE in LOCATION' (e.g., 'restaurants in Paris', 'hotels in Tokyo', 'attractions in Rome')."
    
    def _run(self, query: str) -> str:
        """Search TripAdvisor for places"""
        if not Config.TRIPADVISOR_API_KEY:
            return self._fallback_recommendations(query)
        
        try:
            search_type, location = self._parse_search_query(query)
            if not search_type or not location:
                return "Please specify what you're looking for in format: 'TYPE in LOCATION' (e.g., 'restaurants in Paris')"
            
            results = self._search_places(search_type, location)
            if results:
                return self._format_search_results(search_type, location, results)
            else:
                return self._fallback_recommendations(query)
        except Exception as e:
            return f"Error searching TripAdvisor: {str(e)}"
    
    async def _arun(self, query: str) -> str:
        """Async version"""
        return self._run(query)
    
    def _parse_search_query(self, query: str) -> tuple:
        """Parse search query to extract type and location"""
        query_lower = query.lower().strip()
        
        # Find " in " to split type and location
        if " in " not in query_lower:
            return None, None
        
        parts = query_lower.split(" in ", 1)
        search_type = parts[0].strip()
        location = parts[1].strip()
        
        # Normalize search types
        type_mapping = {
            "restaurant": "restaurants",
            "restaurants": "restaurants",
            "food": "restaurants",
            "dining": "restaurants",
            "hotel": "hotels",
            "hotels": "hotels",
            "accommodation": "hotels",
            "stay": "hotels",
            "attraction": "attractions",
            "attractions": "attractions",
            "things to do": "attractions",
            "activities": "attractions",
            "sightseeing": "attractions"
        }
        
        normalized_type = type_mapping.get(search_type)
        return normalized_type, location
    
    def _search_places(self, search_type: str, location: str) -> Optional[List[Dict]]:
        """Search TripAdvisor API for places"""
        # First, get location ID
        location_id = self._get_location_id(location)
        if not location_id:
            return None
        
        # Then search for places in that location
        return self._get_places_by_type(location_id, search_type)
    
    def _get_location_id(self, location: str) -> Optional[str]:
        """Get TripAdvisor location ID for a place"""
        base_url = "https://api.content.tripadvisor.com/api/v1/location/search"
        
        headers = {"accept": "application/json"}
        params = {
            "key": Config.TRIPADVISOR_API_KEY,
            "searchQuery": location,
            "language": "en"
        }
        
        try:
            with httpx.Client() as client:
                response = client.get(base_url, headers=headers, params=params)
                response.raise_for_status()
                data = response.json()
                
                if data.get("data") and len(data["data"]) > 0:
                    return data["data"][0]["location_id"]
                return None
        except (httpx.RequestError, KeyError):
            return None
    
    def _get_places_by_type(self, location_id: str, search_type: str) -> Optional[List[Dict]]:
        """Get places of specific type in location"""
        # TripAdvisor API endpoints for different types
        endpoints = {
            "restaurants": f"https://api.content.tripadvisor.com/api/v1/location/{location_id}/restaurants",
            "hotels": f"https://api.content.tripadvisor.com/api/v1/location/{location_id}/hotels",
            "attractions": f"https://api.content.tripadvisor.com/api/v1/location/{location_id}/attractions"
        }
        
        if search_type not in endpoints:
            return None
        
        headers = {"accept": "application/json"}
        params = {
            "key": Config.TRIPADVISOR_API_KEY,
            "language": "en"
        }
        
        try:
            with httpx.Client() as client:
                response = client.get(endpoints[search_type], headers=headers, params=params)
                response.raise_for_status()
                data = response.json()
                
                return data.get("data", [])[:5]  # Return top 5 results
        except (httpx.RequestError, KeyError):
            return None
    
    def _format_search_results(self, search_type: str, location: str, results: List[Dict]) -> str:
        """Format TripAdvisor search results"""
        icons = {
            "restaurants": "🍽️",
            "hotels": "🏨",
            "attractions": "🎯"
        }
        
        icon = icons.get(search_type, "📍")
        response = f"{icon} Top {search_type.title()} in {location.title()}:\n\n"
        
        for i, place in enumerate(results, 1):
            name = place.get("name", "Unknown")
            response += f"{i}. **{name}**\n"
            
            # Rating
            if place.get("rating"):
                response += f"   ⭐ Rating: {place['rating']}/5"
                if place.get("num_reviews"):
                    response += f" ({place['num_reviews']} reviews)"
                response += "\n"
            
            # Price level for restaurants/hotels
            if place.get("price_level"):
                price_symbols = "💲" * len(place["price_level"])
                response += f"   💰 Price: {price_symbols}\n"
            
            # Cuisine for restaurants
            if search_type == "restaurants" and place.get("cuisine"):
                cuisines = [c.get("name", "") for c in place["cuisine"][:3]]
                if cuisines:
                    response += f"   🍳 Cuisine: {', '.join(cuisines)}\n"
            
            # Address
            if place.get("address_obj"):
                addr = place["address_obj"]
                if addr.get("street1"):
                    response += f"   📍 {addr['street1']}"
                    if addr.get("city"):
                        response += f", {addr['city']}"
                    response += "\n"
            
            # Description
            if place.get("description"):
                desc = place["description"][:100] + "..." if len(place["description"]) > 100 else place["description"]
                response += f"   📝 {desc}\n"
            
            response += "\n"
        
        return response
    
    def _fallback_recommendations(self, query: str) -> str:
        """Provide fallback recommendations when API is not available"""
        search_type, location = self._parse_search_query(query.lower())
        
        if not search_type or not location:
            return "For specific recommendations, please format your request as 'TYPE in LOCATION' (e.g., 'restaurants in Paris')."
        
        fallback_data = {
            "restaurants": {
                "paris": ["Le Comptoir du Relais", "L'As du Fallafel", "Breizh Café", "Pierre Hermé"],
                "tokyo": ["Sukiyabashi Jiro", "Ramen Yokocho", "Tsukiji Fish Market", "Gonpachi"],
                "rome": ["Da Enzo al 29", "Trattoria Monti", "Pizzarium", "Ginger"],
                "london": ["Dishoom", "Sketch", "The Ivy", "Borough Market"]
            },
            "hotels": {
                "paris": ["Hotel Plaza Athénée", "Le Bristol", "Hotel des Grands Boulevards"],
                "tokyo": ["Park Hyatt Tokyo", "The Ritz-Carlton", "Aman Tokyo"],
                "rome": ["Hotel de Russie", "The First Roma Arte", "Hotel Artemide"],
                "london": ["The Savoy", "Claridge's", "The Shard Hotel"]
            },
            "attractions": {
                "paris": ["Eiffel Tower", "Louvre Museum", "Notre-Dame", "Montmartre"],
                "tokyo": ["Senso-ji Temple", "Tokyo Skytree", "Meiji Shrine", "Shibuya Crossing"],
                "rome": ["Colosseum", "Vatican City", "Trevi Fountain", "Roman Forum"],
                "london": ["Big Ben", "British Museum", "Tower of London", "London Eye"]
            }
        }
        
        location_key = location.lower()
        recommendations = fallback_data.get(search_type, {}).get(location_key, [])
        
        if recommendations:
            icons = {"restaurants": "🍽️", "hotels": "🏨", "attractions": "🎯"}
            icon = icons.get(search_type, "📍")
            
            response = f"{icon} Popular {search_type.title()} in {location.title()}:\n\n"
            for i, place in enumerate(recommendations, 1):
                response += f"{i}. {place}\n"
            
            response += f"\n💡 For detailed reviews, ratings, and booking info, please configure TripAdvisor API key."
            return response
        
        return f"I can provide general travel advice about {location}. For specific {search_type} recommendations with reviews and ratings, please configure TripAdvisor API key."