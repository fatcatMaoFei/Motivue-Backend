# pip install pika
import pika, json
url = "amqp://guest:guest@localhost:5672/%2f"  # 本机端口
conn = pika.BlockingConnection(pika.URLParameters(url))
ch = conn.channel()
ch.queue_declare(queue='readiness.baseline_updated', durable=False)

msg = {
  "event": "baseline_updated",
  "user_id": "u002",
  # 个性化CPT（示例：强推 hrv_trend=rising -> Peak）
  "emission_cpt": {
    "hrv_trend": {
      "rising": {
        "Peak": 0.90, "Well-adapted": 0.09, "FOR": 0.01,
        "Acute Fatigue": 0.00, "NFOR": 0.00, "OTS": 0.00
      }
    }
  },
  # 可选：baseline镜像（占位，不参与计算）
  "baseline": { "sleep_baseline_hours": 7.3 }
}
ch.basic_publish(exchange='', routing_key='readiness.baseline_updated',
                 body=json.dumps(msg).encode('utf-8'))
conn.close()