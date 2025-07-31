import httpx
from typing import Optional
from langchain.tools import BaseTool
from pydantic import Field

from ..models.travel_models import CurrencyRate

class CurrencyTool(BaseTool):
    """Tool for currency conversion using free exchangerate-api.com"""
    
    name: str = "convert_currency"
    description: str = "Convert currency amounts. Input should be in format 'amount FROM_CURRENCY to TO_CURRENCY' (e.g., '100 USD to EUR')."
    
    def _run(self, query: str) -> str:
        """Convert currency based on query"""
        try:
            amount, from_currency, to_currency = self._parse_currency_query(query)
            if not all([amount, from_currency, to_currency]):
                return "Please provide currency conversion in format: 'amount FROM_CURRENCY to TO_CURRENCY' (e.g., '100 USD to EUR')"
            
            rate_info = self._get_exchange_rate(from_currency, to_currency)
            if rate_info:
                converted_amount = amount * rate_info.rate
                return self._format_currency_response(amount, from_currency, converted_amount, to_currency, rate_info.rate)
            else:
                return f"Could not get exchange rate for {from_currency} to {to_currency}"
        except Exception as e:
            return f"Error converting currency: {str(e)}"
    
    async def _arun(self, query: str) -> str:
        """Async version"""
        return self._run(query)
    
    def _parse_currency_query(self, query: str) -> tuple:
        """Parse currency conversion query"""
        try:
            # Handle formats like "100 USD to EUR" or "50 usd to eur"
            query = query.strip().upper()
            parts = query.split()
            
            if len(parts) >= 4 and "TO" in parts:
                amount = float(parts[0])
                from_currency = parts[1]
                to_index = parts.index("TO")
                to_currency = parts[to_index + 1]
                return amount, from_currency, to_currency
            
            return None, None, None
        except (ValueError, IndexError):
            return None, None, None
    
    def _get_exchange_rate(self, from_currency: str, to_currency: str) -> Optional[CurrencyRate]:
        """Get exchange rate from free API"""
        # Using exchangerate-api.com free tier (1500 requests/month)
        base_url = f"https://api.exchangerate-api.com/v4/latest/{from_currency}"
        
        try:
            with httpx.Client() as client:
                response = client.get(base_url)
                response.raise_for_status()
                data = response.json()
                
                if to_currency in data['rates']:
                    rate = data['rates'][to_currency]
                    return CurrencyRate(
                        from_currency=from_currency,
                        to_currency=to_currency,
                        rate=rate
                    )
                return None
        except httpx.RequestError:
            return None
        except KeyError:
            return None
    
    def _format_currency_response(self, amount: float, from_currency: str, 
                                converted_amount: float, to_currency: str, rate: float) -> str:
        """Format currency conversion response"""
        response = f"💱 Currency Conversion:\n"
        response += f"{amount:,.2f} {from_currency} = {converted_amount:,.2f} {to_currency}\n"
        response += f"Exchange Rate: 1 {from_currency} = {rate:.4f} {to_currency}"
        return response