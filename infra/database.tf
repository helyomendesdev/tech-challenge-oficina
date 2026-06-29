# ── Namespace ────────────────────────────────────────────────────────────────

resource "kubernetes_namespace" "oficina" {
  metadata {
    name = var.namespace
  }

  depends_on = [kind_cluster.oficina]
}

# ── Secret ───────────────────────────────────────────────────────────────────

resource "kubernetes_secret" "oficina" {
  metadata {
    name      = "oficina-secret"
    namespace = kubernetes_namespace.oficina.metadata[0].name
  }

  data = {
    DJANGO_SECRET_KEY = var.django_secret_key
    POSTGRES_DB       = var.postgres_db
    POSTGRES_USER     = var.postgres_user
    POSTGRES_PASSWORD = var.postgres_password
  }
}

# ── ConfigMap ─────────────────────────────────────────────────────────────────

resource "kubernetes_config_map" "oficina" {
  metadata {
    name      = "oficina-config"
    namespace = kubernetes_namespace.oficina.metadata[0].name
  }

  data = {
    DJANGO_DEBUG           = var.django_debug
    DJANGO_ALLOWED_HOSTS   = var.django_allowed_hosts
    DJANGO_SETTINGS_MODULE = "app.settings"
    DB_HOST                = kubernetes_service.postgres.metadata[0].name
    DB_PORT                = "5432"
    DJANGO_LOG_FILE        = "/tmp/oficina_atividades.log"
    STATIC_ROOT            = "/app/staticfiles"
  }
}

# ── PostgreSQL StatefulSet ────────────────────────────────────────────────────

resource "kubernetes_stateful_set" "postgres" {
  metadata {
    name      = "postgres"
    namespace = kubernetes_namespace.oficina.metadata[0].name
  }

  spec {
    service_name = "oficina-db"
    replicas     = 1

    selector {
      match_labels = {
        app = "postgres"
      }
    }

    template {
      metadata {
        labels = {
          app = "postgres"
        }
      }

      spec {
        container {
          name  = "postgres"
          image = "postgres:15"

          port {
            container_port = 5432
          }

          env_from {
            secret_ref {
              name = kubernetes_secret.oficina.metadata[0].name
            }
          }

          volume_mount {
            name       = "postgres-data"
            mount_path = "/var/lib/postgresql/data"
          }

          resources {
            requests = {
              cpu    = "250m"
              memory = "256Mi"
            }
            limits = {
              cpu    = "500m"
              memory = "512Mi"
            }
          }

          liveness_probe {
            exec {
              command = ["pg_isready", "-U", "postgres"]
            }
            initial_delay_seconds = 15
            period_seconds        = 10
          }
        }
      }
    }

    volume_claim_template {
      metadata {
        name = "postgres-data"
      }

      spec {
        access_modes = ["ReadWriteOnce"]

        resources {
          requests = {
            storage = "1Gi"
          }
        }
      }
    }
  }
}

# ── PostgreSQL Service (headless) ─────────────────────────────────────────────

resource "kubernetes_service" "postgres" {
  metadata {
    name      = "oficina-db"
    namespace = kubernetes_namespace.oficina.metadata[0].name
  }

  spec {
    selector = {
      app = "postgres"
    }

    port {
      port        = 5432
      target_port = 5432
    }

    cluster_ip = "None"
  }
}

# ── App Deployment ────────────────────────────────────────────────────────────

resource "kubernetes_deployment" "oficina_app" {
  metadata {
    name      = "oficina-app"
    namespace = kubernetes_namespace.oficina.metadata[0].name
    labels = {
      app = "oficina-app"
    }
  }

  spec {
    replicas = 2

    strategy {
      type = "RollingUpdate"
      rolling_update {
        max_surge       = "1"
        max_unavailable = "0"
      }
    }

    selector {
      match_labels = {
        app = "oficina-app"
      }
    }

    template {
      metadata {
        labels = {
          app = "oficina-app"
        }
      }

      spec {
        container {
          name              = "app"
          image             = var.app_image
          image_pull_policy = "IfNotPresent"

          port {
            container_port = 8000
          }

          env_from {
            config_map_ref {
              name = kubernetes_config_map.oficina.metadata[0].name
            }
          }

          env_from {
            secret_ref {
              name = kubernetes_secret.oficina.metadata[0].name
            }
          }

          resources {
            requests = {
              cpu    = "250m"
              memory = "256Mi"
            }
            limits = {
              cpu    = "500m"
              memory = "512Mi"
            }
          }

          liveness_probe {
            tcp_socket {
              port = "8000"
            }
            initial_delay_seconds = 10
            period_seconds        = 20
          }

          readiness_probe {
            tcp_socket {
              port = "8000"
            }
            initial_delay_seconds = 5
            period_seconds        = 10
          }

          startup_probe {
            tcp_socket {
              port = "8000"
            }
            initial_delay_seconds = 3
            period_seconds        = 10
            failure_threshold     = 20
          }
        }
      }
    }
  }

  lifecycle {
    ignore_changes = [spec[0].replicas]
  }

  depends_on = [
    kubernetes_stateful_set.postgres,
    kubernetes_service.postgres,
  ]
}

# ── App Service ───────────────────────────────────────────────────────────────

resource "kubernetes_service" "oficina_app" {
  metadata {
    name      = "oficina-app"
    namespace = kubernetes_namespace.oficina.metadata[0].name
  }

  spec {
    selector = {
      app = "oficina-app"
    }

    port {
      port        = 8000
      target_port = 8000
    }

    type = "ClusterIP"
  }
}

# ── HPA ───────────────────────────────────────────────────────────────────────

resource "kubernetes_horizontal_pod_autoscaler_v2" "oficina_app" {
  metadata {
    name      = "oficina-app-hpa"
    namespace = kubernetes_namespace.oficina.metadata[0].name
  }

  spec {
    scale_target_ref {
      api_version = "apps/v1"
      kind        = "Deployment"
      name        = kubernetes_deployment.oficina_app.metadata[0].name
    }

    min_replicas = 2
    max_replicas = 10

    metric {
      type = "Resource"

      resource {
        name = "cpu"

        target {
          type                = "Utilization"
          average_utilization = 70
        }
      }
    }
  }
}
