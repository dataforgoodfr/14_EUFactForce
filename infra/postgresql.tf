resource "clevercloud_postgresql" "postgresql_db_app" {
  name    = "eufactforce-${var.environment}-pg"
  plan    = var.postgresql_plan # != "dev": pg_vector indisponible en DEV
  region  = var.region
  version = var.postgresql_version

  # Refuse au plan toute opération qui détruirait la base.
  lifecycle {
    prevent_destroy = true
  }
}
