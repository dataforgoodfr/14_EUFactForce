variable "environment" {
  type        = string
  description = "Environnement cible."

  validation {
    condition     = contains(["preprod", "prod"], var.environment)
    error_message = "environment doit valoir : preprod ou prod."
  }
}

variable "region" {
  type    = string
  default = "par"
}

variable "postgresql_plan" {
  type        = string
  description = "Plan PostgreSQL Clever Cloud. Ne doit pas être dev, pg_vector n'y est pas dispo."

  validation {
    condition     = var.postgresql_plan != "dev"
    error_message = "Le plan DEV ne supporte pas les extensions."
  }
}

variable "postgresql_version" {
  type        = string
  description = "Version majeure PostgreSQL"
  default     = "18"
}

variable "app_bucket_name" {
  type        = string
  description = "Bucket pour les données applicatives (documents, sources d'embeddings, etc.)."

  validation {
    condition     = !strcontains(var.app_bucket_name, "_")
    error_message = "Les noms de bucket Cellar ne peuvent pas contenir d'underscore."
  }
}


variable "organisation" {
  type      = string
  sensitive = true
}

variable "cc_token" {
  type      = string
  sensitive = true
}

variable "cc_secret" {
  type      = string
  sensitive = true
}

variable "cc_consumer_key" {
  type = string
}

variable "cc_consumer_secret" {
  type      = string
  sensitive = true
}

variable "state_encryption_passphrase" {
  type      = string
  sensitive = true

  validation {
    condition     = length(var.state_encryption_passphrase) >= 16
    error_message = "La passphrase doit faire au moins 16 caractères."
  }
}
