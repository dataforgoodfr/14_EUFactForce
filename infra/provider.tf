provider "clevercloud" {
  organisation    = var.organisation
  token           = var.cc_token
  secret          = var.cc_secret
  consumer_key    = var.cc_consumer_key
  consumer_secret = var.cc_consumer_secret
}
