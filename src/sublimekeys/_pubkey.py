# Pinned production Ed25519 public key for api.sublimearts.io.
# This is what the offline verification hot path trusts by default — it is
# NEVER fetched over the network at runtime (see client.py). Pass
# public_key_b64u= to SublimeKeysClient to override for self-hosted/staging
# servers or emergency key rotation.

KEY_ID = "v1"
PUBLIC_KEY_B64U = "OEK14M1tAFMPuh0RkgdV3Xvgpb0igCfzbct527xoAzE"
