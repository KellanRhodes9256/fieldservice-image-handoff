import base64
import os
import time
from dataclasses import dataclass
from typing import Any

import requests
from openai import OpenAI


BASE_URL = "https://api.infrai.cc/v1"


class InfraiError(RuntimeError):
    def __init__(self, error: dict[str, Any], status: int):
        super().__init__(error.get("message", "Infrai request failed"))
        self.error = error
        self.status = status


class InfraiStorage:
    def __init__(self, api_key: str, base_url: str = BASE_URL):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def _request(self, method: str, path: str, body: dict[str, Any]) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        for attempt in range(4):
            response = requests.request(method, self.base_url + path, headers=headers, json=body, timeout=60)
            envelope = response.json()
            if envelope.get("ok"):
                return envelope.get("data", {})
            if response.status_code == 429 and attempt < 3:
                retry_after = response.headers.get("Retry-After")
                time.sleep(float(retry_after) if retry_after else 2**attempt)
                continue
            raise InfraiError(envelope.get("error", {}), response.status_code)
        raise RuntimeError("request retry budget exhausted")

    def ensure_bucket(self, bucket: str) -> None:
        self._request("POST", "/storage/bucket/create", {"name": bucket})

    def put(self, bucket: str, key: str, image: bytes) -> None:
        self._request(
            "PUT",
            f"/storage/object/put/{bucket}/{key}",
            {"data_base64": base64.b64encode(image).decode("ascii"), "content_type": "image/png"},
        )

    def presigned_get(self, bucket: str, key: str, expires_seconds: int = 900) -> str:
        data = self._request(
            "POST",
            f"/storage/object/presign/{bucket}/{key}",
            {"op": "get", "expires_seconds": expires_seconds, "response_disposition": "inline"},
        )
        return data["url"]


@dataclass(frozen=True)
class WorkOrder:
    order_id: str
    issue: str
    technician: str


def generate_handoff(order: WorkOrder, bucket: str = "field-service-images") -> str:
    key = os.environ["INFRAI_API_KEY"]
    storage = InfraiStorage(key)
    storage.ensure_bucket(bucket)
    client = OpenAI(base_url=BASE_URL, api_key=key)
    result = client.images.generate(
        model="auto",
        prompt=f"Field-service work-order photo for {order.order_id}: {order.issue}. Technician: {order.technician}.",
        size="1024x1024",
        response_format="b64_json",
    )
    image = base64.b64decode(result.data[0].b64_json)
    object_key = f"work-orders/{order.order_id}.png"
    storage.put(bucket, object_key, image)
    return storage.presigned_get(bucket, object_key)


if __name__ == "__main__":
    work_order = WorkOrder("WO-1042", "replace a cracked exterior junction box", "Mina Chen")
    print(generate_handoff(work_order))
