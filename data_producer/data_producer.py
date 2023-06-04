import csv
import logging
import uuid
from copy import deepcopy
from datetime import datetime, timedelta
from random import randint
from typing import Dict, Any

from confluent_kafka import Producer
from confluent_kafka.avro import CachedSchemaRegistryClient, MessageSerializer

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

ORDER_LINES_KAFKA_TOPIC_NAME = "order_lines"
ORDERS_KAFKA_TOPIC_NAME = "orders"
INVOICES_KAFKA_TOPIC_NAME = "invoices"

DISCOUNT_PERCENTAGE = 5
MAX_ORDER_ITEMS = 5
MAX_ITEM_AMOUNT = 3

DAILY_INCREASE_PERCENTAGE = 3

START_DATE = datetime(2023, 4, 1)
END_DATE = datetime(2023, 4, 30)

EU_14_COUNTRIES_WEIGHTS_MAP = {
    "AT": 1,
    "BE": 1,
    "DK": 1,
    "FI": 1,
    "FR": 5,
    "DE": 5,
    "GR": 1,
    "IE": 3,
    "IT": 4,
    "LU": 1,
    "NL": 1,
    "PT": 2,
    "ES": 5,
    "SE": 1,
}

INVOICE_STATUSES_WEIGHTS_MAP = {
    "PAID": 70,
    "PENDING": 25,
    "FAILED": 5
}

DAILY_SLOTS_WEIGHTS_MAP = {
    0: 1,
    1: 1,
    2: 1,
    3: 1,
    4: 1,
    5: 1,
    6: 1,
    7: 2,
    8: 3,
    9: 4,
    10: 6,
    11: 8,
    12: 9,
    13: 10,
    14: 11,
    15: 11,
    16: 10,
    17: 9,
    18: 8,
    19: 6,
    20: 4,
    21: 3,
    22: 2,
    23: 1,
}


def read_items_csv():
    items = []

    with open('items.csv') as csvfile:
        reader = csv.DictReader(csvfile)

        for row in reader:
            row['price'] = float(row['price'])
            row['probability_weigth'] = float(row['probability_weigth'])
            items.append(row)

    return items


ITEMS_COLLECTION = read_items_csv()

ITEMS_TOTAL_PROBABILITY_WEIGHTS = sum([item["probability_weigth"] for item in ITEMS_COLLECTION])

INVOICE_STATUSES_TOTAL_PROBABILITY_WEIGHTS = sum(INVOICE_STATUSES_WEIGHTS_MAP.values())

COUNTRIES_TOTAL_PROBABILITY_WEIGHTS = sum(EU_14_COUNTRIES_WEIGHTS_MAP.values())


def choose_random_order_item():
    result = randint(0, ITEMS_TOTAL_PROBABILITY_WEIGHTS)

    sum_prob = 0
    for item in ITEMS_COLLECTION:
        sum_prob += item["probability_weigth"]
        if result <= sum_prob:
            return item


def choose_random_invoice_status():
    result = randint(0, INVOICE_STATUSES_TOTAL_PROBABILITY_WEIGHTS)

    sum_prob = 0
    for invoice_status, prob in INVOICE_STATUSES_WEIGHTS_MAP.items():
        sum_prob += prob
        if result <= sum_prob:
            return invoice_status


def choose_random_country():
    result = randint(0, COUNTRIES_TOTAL_PROBABILITY_WEIGHTS)

    sum_prob = 0
    for country_code, prob in EU_14_COUNTRIES_WEIGHTS_MAP.items():
        sum_prob += prob
        if result <= sum_prob:
            return country_code


def apply_discount_decissor():
    rand = randint(0, 10)
    return rand <= 1


def is_new_user_decissor():
    rand = randint(0, 10)
    return rand <= 3


def create_order(current_ts):
    num_items = randint(1, MAX_ORDER_ITEMS)

    order_uuid = str(uuid.uuid4())

    order_total = 0
    order_lines = []
    for i in range(num_items):
        new_item = deepcopy(choose_random_order_item())

        new_item["order_uuid"] = order_uuid
        new_item["timestamp"] = str(current_ts)
        new_item["order_line_uuid"] = str(uuid.uuid4())

        new_item["amount"] = randint(1, MAX_ITEM_AMOUNT)
        new_item["total"] = new_item["amount"] * new_item["price"]
        del (new_item["probability_weigth"])

        order_lines.append(new_item)
        order_total += new_item["total"]

    apply_discount = apply_discount_decissor()
    if apply_discount:
        order_total = order_total * (100 - DISCOUNT_PERCENTAGE) / 100

    order_total = round(order_total, 2)

    order = {
        "order_uuid": order_uuid,
        "timestamp": str(current_ts),
        "country_code": choose_random_country(),
        "is_new_user": is_new_user_decissor(),
        "with_discount": apply_discount,
        "total": order_total
    }

    invoice = {
        "order_uuid": order_uuid,
        "timestamp": str(current_ts),
        "total": order_total,
        "status": choose_random_invoice_status(),
    }

    return order, order_lines, invoice


def publish_serialized_event_to_kafka(topic_name: str, event_data: Dict[str, Any]):
    _, event_schema, _ = schema_registry_client.get_latest_schema(topic_name)
    serialized_event = serializer.encode_record_with_schema(topic_name, event_schema, event_data)
    producer.produce(topic_name, serialized_event)


if __name__ == "__main__":

    logger.info("Starting data generation.")

    schema_registry_conf = {"url": "http://localhost:8084"}
    schema_registry_client = CachedSchemaRegistryClient(schema_registry_conf)
    serializer = MessageSerializer(schema_registry_client)

    producer_config = {
        "bootstrap.servers": "localhost:9092"
    }

    producer = Producer(producer_config)

    current_ts = START_DATE
    day_n = 0
    while current_ts <= END_DATE:
        logger.info(f"Generating data for date: {current_ts.strftime('%Y-%m-%d')}")

        for hour, orders_n in DAILY_SLOTS_WEIGHTS_MAP.items():
            current_ts = current_ts.replace(hour=hour)
            logger.info(f"Generating data for hour: {current_ts.strftime('%Y-%m-%d %H:00')}")

            orders_n = orders_n * pow(1 + (DAILY_INCREASE_PERCENTAGE / 100), day_n)

            for _ in range(orders_n):

                order, order_lines, invoice = create_order(current_ts)

                publish_serialized_event_to_kafka(INVOICES_KAFKA_TOPIC_NAME, invoice)
                publish_serialized_event_to_kafka(ORDERS_KAFKA_TOPIC_NAME, order)

                for order_line in order_lines:
                    print(order_line)
                    publish_serialized_event_to_kafka(ORDER_LINES_KAFKA_TOPIC_NAME, order_line)

        current_ts = current_ts + timedelta(days=1)
        day_n += 1

    producer.flush()
