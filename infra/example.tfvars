# Usage local :
#   cp example.tfvars secrets.auto.tfvars


# ─── Secrets (SENSIBLE ) ─────────
organisation                = "orga_xxxxxxxxxxxxxxxx"
cc_token                    = "REMPLACER" # clever login
cc_secret                   = "REMPLACER"
cc_consumer_key             = "REMPLACER" # consumer OAuth1 dédié
cc_consumer_secret          = "REMPLACER"
state_encryption_passphrase = "REMPLACER_32_CHARS_MIN" # openssl rand -base64 32
