import httpx
from typing import Optional, Dict, Any
from langchain.tools import BaseTool
from pydantic import Field

from ..utils.config import Config

class MapsTool(BaseTool):
    """Tool for getting location information and distances using Google Maps API"""
    
    name: str = "get_location_info"
    description: str = "Get location details, coordinates, or distance between two places. Input should be a location name or 'distance from PLACE1 to PLACE2'."
    
    def _run(self, query: str) -> str:
        """Get location information or distance"""
        if not Config.GOOGLE_MAPS_API_KEY:
            return self._fallback_location_info(query)
        
        try:
            # Check if it's a distance query
            if "distance from" in query.lower() and "to" in query.lower():
                return self._get_distance(query)
            else:
                return self._get_place_info(query)
        except Exception as e:
            return f"Error getting location information: {str(e)}"
    
    async def _arun(self, query: str) -> str:
        """Async version"""
        return self._run(query)
    
    def _get_distance(self, query: str) -> str:
        """Get distance between two places"""
        try:
            # Parse "distance from PLACE1 to PLACE2"
            query_lower = query.lower()
            from_idx = query_lower.find("distance from") + len("distance from")
            to_idx = query_lower.find(" to ")
            
            if to_idx == -1:
                return "Please use format: 'distance from PLACE1 to PLACE2'"
            
            origin = query[from_idx:to_idx].strip()
            destination = query[to_idx + 4:].strip()
            
            distance_info = self._fetch_distance(origin, destination)
            if distance_info:
                return self._format_distance_response(origin, destination, distance_info)
            else:
                return f"Could not calculate distance between {origin} and {destination}"
        except Exception as e:
            return f"Error calculating distance: {str(e)}"
    
    def _get_place_info(self, location: str) -> str:
        """Get information about a place"""
        place_info = self._fetch_place_details(location)
        if place_info:
            return self._format_place_response(place_info)
        else:
            return self._fallback_location_info(location)
    
    def _fetch_distance(self, origin: str, destination: str) -> Optional[Dict[str, Any]]:
        """Fetch distance using Google Maps Distance Matrix API"""
        base_url = "https://maps.googleapis.com/maps/api/distancematrix/json"
        
        params = {
            "origins": origin,
            "destinations": destination,
            "key": Config.GOOGLE_MAPS_API_KEY,
            "units": "metric"
        }
        
        try:
            with httpx.Client() as client:
                response = client.get(base_url, params=params)
                response.raise_for_status()
                data = response.json()
                
                if data['status'] == 'OK' and data['rows']:
                    element = data['rows'][0]['elements'][0]
                    if element['status'] == 'OK':
                        return {
                            'distance': element['distance']['text'],
                            'duration': element['duration']['text'],
                            'origin': data['origin_addresses'][0],
                            'destination': data['destination_addresses'][0]
                        }
                return None
        except (httpx.RequestError, KeyError):
            return None
    
    def _fetch_place_details(self, location: str) -> Optional[Dict[str, Any]]:
        """Fetch place details using Google Places API"""
        # Using Places API Text Search
        base_url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
        
        params = {
            "query": location,
            "key": Config.GOOGLE_MAPS_API_KEY
        }
        
        try:
            with httpx.Client() as client:
                response = client.get(base_url, params=params)
                response.raise_for_status()
                data = response.json()
                
                if data['status'] == 'OK' and data['results']:
                    place = data['results'][0]
                    return {
                        'name': place['name'],
                        'formatted_address': place['formatted_address'],
                        'location': place['geometry']['location'],
                        'rating': place.get('rating'),
                        'types': place.get('types', [])
                    }
                return None
        except (httpx.RequestError, KeyError):
            return None
    
    def _format_distance_response(self, origin: str, destination: str, distance_info: Dict) -> str:
        """Format distance response"""
        response = f"🗺️ Distance Information:\n"
        response += f"From: {distance_info['origin']}\n"
        response += f"To: {distance_info['destination']}\n"
        response += f"Distance: {distance_info['distance']}\n"
        response += f"Travel Time: {distance_info['duration']} (by car)"
        return response
    
    def _format_place_response(self, place_info: Dict) -> str:
        """Format place information response"""
        response = f"📍 Location: {place_info['name']}\n"
        response += f"Address: {place_info['formatted_address']}\n"
        response += f"Coordinates: {place_info['location']['lat']}, {place_info['location']['lng']}"
        
        if place_info.get('rating'):
            response += f"\nRating: {place_info['rating']}/5"
        
        return response
    
    def _fallback_location_info(self, location: str) -> str:
        """Fallback when Google Maps API is not available"""
        return f"📍 Location: {location}\n\nFor detailed location information, maps, and distances, please configure Google Maps API key. The travel agent can still provide general travel advice about this location."