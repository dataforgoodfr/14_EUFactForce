terraform {
  required_version = ">= 1.10.0"

  required_providers {
    clevercloud = {
      source  = "CleverCloud/clevercloud"
      version = "~> 1.2"
    }
  }

  backend "s3" {
    key    = "eufactforce.tfstate"
    region = "par"

    #on neutralise les vérifications AWS-spécifiques.
    skip_credentials_validation = true
    skip_region_validation      = true
    skip_requesting_account_id  = true
    skip_metadata_api_check     = true
    use_path_style              = true
    skip_s3_checksum            = true

    use_lockfile = true
  }

  # state_encryption_passphrase est contenu dans secrets.auto.tfvars
  encryption {
    key_provider "pbkdf2" "k" {
      passphrase = var.state_encryption_passphrase
    }
    method "aes_gcm" "m" {
      keys = key_provider.pbkdf2.k
    }
    state {
      method = method.aes_gcm.m
    }
    plan {
      method = method.aes_gcm.m
    }
  }
}
