# Les buckets cellar sont composé de deux ressources: l'addon cellar et le bucket

resource "clevercloud_cellar" "cellar_app" {
  name   = "eufactforce-${var.environment}"
  region = var.region

  lifecycle {
    prevent_destroy = true
  }
}

resource "clevercloud_cellar_bucket" "cellar_bucket_app" {
  cellar_id = clevercloud_cellar.cellar_app.id
  id        = var.app_bucket_name

  lifecycle {
    prevent_destroy = true
  }
}
