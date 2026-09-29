data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

resource "aws_kms_key" "async" {
  description             = "${var.name_prefix} asynchronous workflow encryption"
  deletion_window_in_days = 30
  enable_key_rotation     = true
  tags                    = var.tags
}

resource "aws_kms_alias" "async" {
  name          = "alias/${var.name_prefix}-async"
  target_key_id = aws_kms_key.async.key_id
}

locals {
  queues = toset(["notifications", "lifecycle", "audit-checkpoints"])
}

resource "aws_sqs_queue" "dlq" {
  for_each                  = local.queues
  name                      = "${var.name_prefix}-${each.key}-dlq"
  kms_master_key_id         = aws_kms_key.async.arn
  message_retention_seconds = 1209600
  tags                      = var.tags
}

resource "aws_sqs_queue" "work" {
  for_each                   = local.queues
  name                       = "${var.name_prefix}-${each.key}"
  kms_master_key_id          = aws_kms_key.async.arn
  message_retention_seconds  = 345600
  visibility_timeout_seconds = 300
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dlq[each.key].arn
    maxReceiveCount     = 5
  })
  tags = var.tags
}

resource "aws_secretsmanager_secret" "async_provider" {
  name                    = "${var.name_prefix}/async/provider-credentials"
  kms_key_id              = aws_kms_key.async.arn
  recovery_window_in_days = 30
  tags                    = var.tags
}

resource "aws_cloudwatch_event_rule" "worker_reconciliation" {
  name                = "${var.name_prefix}-worker-reconciliation"
  schedule_expression = var.worker_schedule_expression
  tags                = var.tags
}

resource "aws_cloudwatch_metric_alarm" "queue_age" {
  for_each            = aws_sqs_queue.work
  alarm_name          = "${var.name_prefix}-${each.key}-oldest-message"
  namespace           = "AWS/SQS"
  metric_name         = "ApproximateAgeOfOldestMessage"
  statistic           = "Maximum"
  period              = 300
  evaluation_periods  = 2
  threshold           = 900
  comparison_operator = "GreaterThanThreshold"
  alarm_actions       = [var.alarm_topic_arn]
  dimensions          = { QueueName = each.value.name }
  tags                = var.tags
}

resource "aws_cloudwatch_metric_alarm" "dlq_depth" {
  for_each            = aws_sqs_queue.dlq
  alarm_name          = "${var.name_prefix}-${each.key}-dlq-depth"
  namespace           = "AWS/SQS"
  metric_name         = "ApproximateNumberOfMessagesVisible"
  statistic           = "Sum"
  period              = 60
  evaluation_periods  = 1
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"
  alarm_actions       = [var.alarm_topic_arn]
  dimensions          = { QueueName = each.value.name }
  tags                = var.tags
}
