"""
Utility API for Indian Pincode lookup.

Endpoint example (after wiring in urls.py):

    GET /api/utils/pincode-lookup/?pincode=400017

Response example:

    {
      "pincode": "400017",
      "country": "India",
      "state": "Maharashtra",
      "district": "Mumbai",
      "post_offices": [
        {
          "name": "Chinchpokli",
          "branch_type": "Sub Post Office",
          "delivery_status": "Non-Delivery",
          "region": "Mumbai",
          "division": "Mumbai East",
          "block": "NA",
          "taluk": "Mumbai",
          "circle": "Maharashtra"
        }
      ]
    }
"""

import requests
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView


# -----------------------
# Serializer
# -----------------------

class PincodeLookupSerializer(serializers.Serializer):
    """
    Simple validator for 6-digit Indian pincode.
    """
    pincode = serializers.RegexField(
        r"^\d{6}$",
        error_messages={
            "invalid": "Pincode must be a 6 digit number.",
        },
    )


# -----------------------
# API View
# -----------------------

class PincodeLookupAPIView(APIView):
    """
    GET /api/utils/pincode-lookup/?pincode=400017

    Uses https://api.postalpincode.in/pincode/{pincode}
    to fetch Indian postal details.
    """

    def get(self, request, *args, **kwargs):
        # 1) Validate input
        serializer = PincodeLookupSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        pincode = serializer.validated_data["pincode"]

        # 2) Call external Postal Pincode API
        url = f"https://api.postalpincode.in/pincode/{pincode}"

        try:
            upstream_resp = requests.get(url, timeout=5)
        except requests.RequestException:
            return Response(
                {"detail": "Pincode service is not reachable. Please try again later."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        if upstream_resp.status_code != 200:
            return Response(
                {"detail": "Failed to fetch pincode details from upstream service."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        try:
            data = upstream_resp.json()
        except ValueError:
            return Response(
                {"detail": "Invalid response from pincode service."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        # 3) Parse upstream response
        if not data or not isinstance(data, list):
            return Response(
                {"detail": "Unexpected data format from pincode service."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        root = data[0]

        if root.get("Status") != "Success":
            # e.g. Status: "Error"
            message = root.get("Message") or "Invalid or unknown pincode."
            return Response(
                {"detail": message},
                status=status.HTTP_404_NOT_FOUND,
            )

        post_offices = root.get("PostOffice") or []
        if not post_offices:
            return Response(
                {"detail": "No data found for this pincode."},
                status=status.HTTP_404_NOT_FOUND,
            )

        first = post_offices[0]

        # 4) Build clean response
        result = {
            "pincode": pincode,
            "country": first.get("Country"),
            "state": first.get("State"),
            "district": first.get("District"),
            "post_offices": [
                {
                    "name": po.get("Name"),
                    "branch_type": po.get("BranchType"),
                    "delivery_status": po.get("DeliveryStatus"),
                    "region": po.get("Region"),
                    "division": po.get("Division"),
                    "block": po.get("Block"),
                    "taluk": po.get("Taluk"),
                    "circle": po.get("Circle"),
                }
                for po in post_offices
            ],
        }

        return Response(result, status=status.HTTP_200_OK)
