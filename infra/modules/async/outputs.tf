output "queue_urls" {
  value = { for name, queue in aws_sqs_queue.work : name => queue.url }
}

output "dead_letter_queue_arns" {
  value = { for name, queue in aws_sqs_queue.dlq : name => queue.arn }
}

output "kms_key_arn" {
  value = aws_kms_key.async.arn
}
