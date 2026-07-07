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
    SECURE_SSL_REDIRECT    = "False"
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
              command = ["sh", "-c", "pg_isready -U \"$POSTGRES_USER\" -d \"$POSTGRES_DB\""]
            }
            initial_delay_seconds = 15
            period_seconds        = 10
          }

          readiness_probe {
            exec {
              command = ["sh", "-c", "pg_isready -U \"$POSTGRES_USER\" -d \"$POSTGRES_DB\""]
            }
            initial_delay_seconds = 5
            period_seconds        = 5
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

# ── Migrations ────────────────────────────────────────────────────────────────

resource "kubernetes_job_v1" "migrate" {
  metadata {
    name      = "oficina-migrate"
    namespace = kubernetes_namespace.oficina.metadata[0].name
  }

  spec {
    backoff_limit              = 3
    ttl_seconds_after_finished = 300

    template {
      metadata {
        labels = {
          app = "oficina-migrate"
        }
      }

      spec {
        restart_policy = "Never"

        container {
          name              = "migrate"
          image             = var.app_image
          image_pull_policy = "IfNotPresent"
          command = [
            "sh",
            "-c",
            "until python -c \"import socket; s=socket.create_connection(('oficina-db', 5432), timeout=2); s.close()\"; do sleep 3; done; python manage.py migrate --noinput",
          ]

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
        }
      }
    }
  }

  wait_for_completion = true

  timeouts {
    create = "5m"
    update = "5m"
  }

  depends_on = [
    kubernetes_stateful_set.postgres,
    kubernetes_service.postgres,
  ]
}

# ── App Deployment ───────────────────────────────────────────────────────────

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
              cpu    = "100m"
              memory = "256Mi"
            }
            limits = {
              cpu    = "500m"
              memory = "512Mi"
            }
          }

          liveness_probe {
            http_get {
              path = "/health/live/"
              port = 8000
            }
            initial_delay_seconds = 10
            period_seconds        = 20
          }

          readiness_probe {
            http_get {
              path = "/health/ready/"
              port = 8000
            }
            initial_delay_seconds = 5
            period_seconds        = 10
          }

          startup_probe {
            http_get {
              path = "/health/live/"
              port = 8000
            }
            initial_delay_seconds = 3
            period_seconds        = 10
            failure_threshold     = 30
          }
        }
      }
    }
  }

  lifecycle {
    ignore_changes = [spec[0].replicas]
  }

  depends_on = [
    kubernetes_job_v1.migrate,
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
    max_replicas = 6

    behavior {
      scale_up {
        stabilization_window_seconds = 0
        select_policy                = "Max"

        policy {
          type           = "Pods"
          value          = 2
          period_seconds = 15
        }

        policy {
          type           = "Percent"
          value          = 100
          period_seconds = 15
        }
      }

      scale_down {
        stabilization_window_seconds = 60
        select_policy                = "Max"

        policy {
          type           = "Percent"
          value          = 50
          period_seconds = 15
        }
      }
    }

    metric {
      type = "Resource"

      resource {
        name = "cpu"

        target {
          type                = "Utilization"
          average_utilization = 50
        }
      }
    }
  }
}
