terraform {
  required_version = ">= 1.6.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

resource "google_artifact_registry_repository" "backend" {
  location      = var.region
  repository_id = "ai-trading-backend"
  description   = "Container images for the trading backend"
  format        = "DOCKER"
}

resource "google_redis_instance" "cache" {
  name           = "ai-trading-cache"
  tier           = "BASIC"
  memory_size_gb = 1
  region         = var.region
}
