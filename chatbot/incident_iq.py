import os
import json
import logging
import requests
from typing import Dict, List, Optional, Any

logger = logging.getLogger("iiqreply.incident_iq")


class IncidentIQConnector:
    """
    Handles integration with Incident IQ ticketing system.
    """

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        """
        Initialize the Incident IQ connector.

        Args:
            api_key: API key for Incident IQ
            base_url: Base URL for the Incident IQ API
        """
        self.api_key = api_key or os.getenv("INCIDENT_IQ_API_KEY", "")
        self.base_url = base_url or os.getenv("INCIDENT_IQ_BASE_URL", "https://api.incidentiq.com/v1")

        if not self.api_key:
            logger.warning("No Incident IQ API key provided -- IIQ integration disabled")

    def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Dict:
        """
        Make a request to the Incident IQ API.

        Args:
            method: HTTP method (GET, POST, PUT, etc.)
            endpoint: API endpoint to call
            data: Data to send in the request

        Returns:
            Response data from the API
        """
        if not self.api_key:
            logger.warning("IIQ request skipped -- no API key configured")
            return {"error": "Incident IQ API key not configured"}

        url = f"{self.base_url}/{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        logger.debug("IIQ %s %s", method.upper(), url)
        try:
            if method.upper() == "GET":
                response = requests.get(url, headers=headers, timeout=30)
            elif method.upper() == "POST":
                response = requests.post(url, headers=headers, json=data, timeout=30)
            elif method.upper() == "PUT":
                response = requests.put(url, headers=headers, json=data, timeout=30)
            else:
                return {"error": f"Unsupported method: {method}"}

            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            logger.error("Error making request to Incident IQ: %s", e)
            return {"error": str(e)}

    def get_ticket(self, ticket_id: str) -> Dict:
        """
        Get details for a specific ticket.

        Args:
            ticket_id: The ID of the ticket to retrieve

        Returns:
            Ticket details
        """
        return self._make_request("GET", f"tickets/{ticket_id}")

    def create_ticket(self, title: str, description: str,
                      category: str, user_id: Optional[str] = None) -> Dict:
        """
        Create a new ticket in Incident IQ.

        Args:
            title: Ticket title
            description: Ticket description
            category: Ticket category
            user_id: ID of the user creating the ticket

        Returns:
            Details of the created ticket
        """
        data = {
            "title": title,
            "description": description,
            "category": category,
            "submitter_id": user_id
        }

        return self._make_request("POST", "tickets", data)

    def update_ticket(self, ticket_id: str, updates: Dict) -> Dict:
        """
        Update an existing ticket.

        Args:
            ticket_id: ID of the ticket to update
            updates: Fields to update and their new values

        Returns:
            Updated ticket details
        """
        return self._make_request("PUT", f"tickets/{ticket_id}", updates)

    def resolve_ticket(self, ticket_id: str, resolution: str) -> Dict:
        """
        Mark a ticket as resolved.

        Args:
            ticket_id: ID of the ticket to resolve
            resolution: Resolution description

        Returns:
            Updated ticket details
        """
        data = {
            "status": "resolved",
            "resolution": resolution,
            "resolution_date": "auto"  # API will use current time
        }

        return self._make_request("PUT", f"tickets/{ticket_id}", data)

    def add_comment(self, ticket_id: str, comment: str,
                   is_private: bool = False) -> Dict:
        """
        Add a comment to a ticket.

        Args:
            ticket_id: ID of the ticket to comment on
            comment: Comment text
            is_private: Whether the comment is private/internal

        Returns:
            Comment details
        """
        data = {
            "ticket_id": ticket_id,
            "body": comment,
            "is_private": is_private
        }

        return self._make_request("POST", "comments", data)
