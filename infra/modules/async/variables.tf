variable "name_prefix" {
  type = string
}

variable "alarm_topic_arn" {
  type = string
}

variable "worker_schedule_expression" {
  type    = string
  default = "rate(5 minutes)"
}

variable "tags" {
  type    = map(string)
  default = {}
}
