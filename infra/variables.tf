variable "cluster_name" {
  type    = string
  default = "oficina"
}

variable "namespace" {
  type    = string
  default = "oficina"
}

variable "app_image" {
  type    = string
  default = "oficina-app:latest"
}

variable "postgres_db" {
  type    = string
  default = "oficina"
}

variable "postgres_user" {
  type    = string
  default = "oficina_user"
}

variable "postgres_password" {
  type      = string
  sensitive = true

  validation {
    condition     = length(var.postgres_password) >= 16 && !strcontains(var.postgres_password, "CHANGE_ME")
    error_message = "postgres_password deve ter ao menos 16 caracteres e nao pode conter CHANGE_ME."
  }
}

variable "django_secret_key" {
  type      = string
  sensitive = true

  validation {
    condition     = length(var.django_secret_key) >= 32 && !strcontains(var.django_secret_key, "CHANGE_ME")
    error_message = "django_secret_key deve ter ao menos 32 caracteres e nao pode conter CHANGE_ME."
  }
}

variable "django_debug" {
  type    = string
  default = "False"
}

variable "django_allowed_hosts" {
  type    = string
  default = "*"
}
