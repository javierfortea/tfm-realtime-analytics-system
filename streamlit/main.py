import asyncio
from collections import defaultdict

import aiohttp
import pandas as pd

import streamlit as st

ORDERS_WEBSOCKET_CONNECTION = "ws://api:9999/orders"
INVOICES_WEBSOCKET_CONNECTION = "ws://api:9999/invoices"
ORDER_LINES_WEBSOCKET_CONNECTION = "ws://api:9999/order_lines"

total_per_country = defaultdict(int)
total_per_status = defaultdict(int)
total_per_product = defaultdict(int)

st.set_page_config(page_title="TFM - Real-time analytics system.", layout="wide")
st.title("TFM - Real-time analytics system.")


async def orders_consumer(structure, status):
    async with aiohttp.ClientSession(trust_env=True) as session:
        status.text(f"Connecting to {ORDERS_WEBSOCKET_CONNECTION}")

        async with session.ws_connect(ORDERS_WEBSOCKET_CONNECTION) as websocket:
            status.text(f"Connected to: {ORDERS_WEBSOCKET_CONNECTION}")

            async for message in websocket:
                data = message.json()

                country = data[4]
                order_total = data[7]
                total_per_country[country] += order_total

                structure["raw"].write(data)

                chart_data = pd.DataFrame(
                    total_per_country.values(),
                    total_per_country.keys()
                )

                structure["graph"].bar_chart(chart_data)


st.subheader("Aggregated orders total per country.")

status = st.empty()
connect = st.checkbox("Connect to WS Server (orders)")

columns = st.columns(2)
structure = {
    "raw": columns[0].empty(),
    "graph": columns[1].empty()
}

if connect:
    asyncio.run(
        orders_consumer(structure, status)
    )
else:
    status.text(f"Disconnected.")


async def invoices_consumer(structure, status):
    async with aiohttp.ClientSession(trust_env=True) as session:
        status.text(f"Connecting to {INVOICES_WEBSOCKET_CONNECTION}")

        async with session.ws_connect(INVOICES_WEBSOCKET_CONNECTION) as websocket:
            status.text(f"Connected to: {INVOICES_WEBSOCKET_CONNECTION}")

            async for message in websocket:
                data = message.json()

                invoice_total = data[4]
                status = data[5]
                total_per_status[status] += invoice_total

                structure["raw"].write(data)

                chart_data = pd.DataFrame(
                    total_per_status.values(),
                    total_per_status.keys()
                )

                structure["graph"].bar_chart(chart_data)


st.subheader("Aggregated invoices total per invoice status.")

status = st.empty()
connect = st.checkbox("Connect to WS Server (invoices)")

columns = st.columns(2)
structure = {
    "raw": columns[0].empty(),
    "graph": columns[1].empty()
}

if connect:
    asyncio.run(
        invoices_consumer(structure, status)
    )
else:
    status.text(f"Disconnected.")


async def order_lines_consumer(structure, second_row_columns, status):
    async with aiohttp.ClientSession(trust_env=True) as session:
        status.text(f"Connecting to {ORDER_LINES_WEBSOCKET_CONNECTION}")

        async with session.ws_connect(ORDER_LINES_WEBSOCKET_CONNECTION) as websocket:
            status.text(f"Connected to: {ORDER_LINES_WEBSOCKET_CONNECTION}")

            async for message in websocket:
                data = message.json()

                order_line_total = data[9]
                category = data[3]
                product_name = data[2]

                total_per_status[category] += order_line_total
                total_per_product[product_name] += order_line_total

                structure["raw"].write(data)

                status_chart_data = pd.DataFrame(
                    total_per_status.values(),
                    total_per_status.keys()
                )

                structure["graph"].bar_chart(status_chart_data)

                product_chart_data = pd.DataFrame(
                    total_per_product.values(),
                    total_per_product.keys()
                )

                second_row_columns[1].bar_chart(product_chart_data)


st.subheader("Aggregated order lines total per category and product.")

status = st.empty()
connect = st.checkbox("Connect to WS Server (order lines)")

first_row_columns = st.columns(2)
structure = {
    "raw": first_row_columns[0].empty(),
    "graph": first_row_columns[1].empty()
}

second_row_columns = [col.empty() for col in st.columns(2)]

if connect:
    asyncio.run(
        order_lines_consumer(structure, second_row_columns, status)
    )
else:
    status.text(f"Disconnected.")
