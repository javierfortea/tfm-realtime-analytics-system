import asyncio
from typing import List

import databases
import psycopg2
import sqlalchemy
from fastapi import FastAPI
from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy import create_engine

# Materialize connection configuration.
MATERIALIZE_STRING_CONNECTION = "postgresql://materialize:@materialized:6875/materialize"

# Stream sleep.
MESSAGE_STREAM_DELAY = 2

database = databases.Database(MATERIALIZE_STRING_CONNECTION)
metadata = sqlalchemy.MetaData()
engine = create_engine(MATERIALIZE_STRING_CONNECTION)

# Convert numbers from postgres to floats instead of Decimal so that we can use serialize them as jsons with the
# defautl Python serializer
DEC2FLOAT = psycopg2.extensions.new_type(
    psycopg2.extensions.DECIMAL.values,
    "DEC2FLOAT",
    lambda value, curs: float(value) if value is not None else None,
)
psycopg2.extensions.register_type(DEC2FLOAT)

app = FastAPI()


@app.on_event("startup")
async def startup():
    await database.connect()


@app.on_event("shutdown")
async def shutdown():
    await database.disconnect()


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)


manager = ConnectionManager()


def orders_new_messages():
    results = engine.execute("SELECT count(*) FROM processed_orders")
    return None if results.fetchone()[0] == 0 else True


async def orders_event_generator():
    if orders_new_messages():
        connection = engine.raw_connection()
        with connection.cursor() as cur:
            cur.execute("DECLARE c CURSOR FOR TAIL processed_orders")
            cur.execute("FETCH ALL c")
            for row in cur:
                new_row = (row[0], row[1], row[2], str(row[3]), row[4], row[5], row[6], row[7])
                yield new_row

    await asyncio.sleep(MESSAGE_STREAM_DELAY)


def invoices_new_messages():
    results = engine.execute("SELECT count(*) FROM processed_invoices")
    return None if results.fetchone()[0] == 0 else True


async def invoices_event_generator():
    if invoices_new_messages():
        connection = engine.raw_connection()
        with connection.cursor() as cur:
            cur.execute("DECLARE c CURSOR FOR TAIL processed_invoices")
            cur.execute("FETCH ALL c")
            for row in cur:
                new_row = (row[0], row[1], row[2], str(row[3]), row[4], row[5])
                yield new_row

    await asyncio.sleep(MESSAGE_STREAM_DELAY)


def order_lines_new_messages():
    results = engine.execute("SELECT count(*) FROM processed_order_lines")
    return None if results.fetchone()[0] == 0 else True


async def order_lines_event_generator():
    if order_lines_new_messages():
        connection = engine.raw_connection()
        with connection.cursor() as cur:
            cur.execute("DECLARE c CURSOR FOR TAIL processed_order_lines")
            cur.execute("FETCH ALL c")
            for row in cur:
                new_row = (row[0], row[1], row[2], row[3], row[4], row[5], str(row[6]), row[7], row[8], row[9])
                yield new_row

    await asyncio.sleep(MESSAGE_STREAM_DELAY)


@app.websocket("/orders")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            async for data in orders_event_generator():
                await websocket.send_json(data)
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.websocket("/invoices")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            async for data in invoices_event_generator():
                await websocket.send_json(data)
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.websocket("/order_lines")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            async for data in order_lines_event_generator():
                await websocket.send_json(data)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
