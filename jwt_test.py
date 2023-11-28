import jwt


jwt_token = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZGVudGlmaWVyIjoiQ1RSSS1WLSIsInZlcnNpb24iOiJ2Mi4xLjIiLCJyZXNldF9kYXRlIjoiMjAyMy0xMS0xOCIsImlhdCI6MTcwMDQ3ODczOSwic3ViIjoiYWdlbnQtdG9rZW4ifQ.pZmKhGEcEds0UI1_nzLph_XsEwRA09WE-GnAH0m_XcmX4hN8TR0EFGGQxlM-nkVgjeeQnVkEVwsTA9WSGXjEPKaKb3IzJ_Xbxo07rYNggzclZlnsf6FRlJpiFhByxBY4fa-jmyBrrMWvq_XuSX0aZnfkEDzil0Ppvxtn13MaP9g4TXAgxilDNbQOMWojgZl8AngxzcnscYqvpjF5xQuCGP1ucsWg4gPK07kmIVKxfcwKBnRvVRFtLk3s2wLhyKZPcKju_YaSonNvRbu8h-r-6e9hN4Ga_W6Vr08H6l84nl-co_q0TkNLX_zaGkcClJhqXMtSCPXxXeixY5LFxuPnDA"

import base64
import json


def decode_jwt(token):
    # Split the JWT into its three components
    header_b64, payload_b64, signature = jwt_token.split(".")

    # Base64 decode the header and payload
    header = base64.urlsafe_b64decode(header_b64 + "==")
    payload = base64.urlsafe_b64decode(payload_b64 + "==")

    return json.loads(header), json.loads(payload)


# Example usage:
header, payload = decode_jwt(jwt_token)

print("Header:", json.dumps(header, indent=2))
print("Payload:", json.dumps(payload, indent=2))
