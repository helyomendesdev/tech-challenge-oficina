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
}

variable "django_secret_key" {
  type      = string
  sensitive = true
}

variable "django_debug" {
  type    = string
  default = "False"
}

variable "django_allowed_hosts" {
  type    = string
  default = "*"
}
