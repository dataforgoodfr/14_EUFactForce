output "postgresql_id" {
  description = "ID de l'add-on PostgreSQL"
  value       = clevercloud_postgresql.postgresql_db_app.id
}

output "app_cellar_id" {
  description = "ID de l'add-on Cellar applicatif."
  value       = clevercloud_cellar.cellar_app.id
}

output "app_bucket" {
  description = "Nom du bucket applicatif."
  value       = clevercloud_cellar_bucket.cellar_bucket_app.id
}

output "postgresql_uri" {
  value     = clevercloud_postgresql.postgresql_db_app.uri
  sensitive = true
}
