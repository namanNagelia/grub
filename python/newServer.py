from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict
import time
import plaid
from plaid.api import plaid_api
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid.model.transactions_get_request import TransactionsGetRequest
from plaid.model.products import Products
from plaid.model.country_code import CountryCode
from datetime import datetime, timedelta
from plaid.model.transactions_sync_request import TransactionsSyncRequest
import os
import uuid
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173",
                   "http://localhost:3000", "http://localhost:8000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Plaid configuration
PLAID_CLIENT_ID = os.getenv('PLAID_CLIENT_ID')
PLAID_SECRET = os.getenv('PLAID_SECRET')
PLAID_ENV = os.getenv('PLAID_ENV', 'sandbox')
PLAID_PRODUCTS = os.getenv('PLAID_PRODUCTS', 'transactions').split(',')
PLAID_COUNTRY_CODES = os.getenv('PLAID_COUNTRY_CODES', 'US').split(',')
PLAID_REDIRECT_URI = os.getenv('PLAID_REDIRECT_URI')
access_token = None

# Configure plaid environment
host = plaid.Environment.Sandbox if PLAID_ENV == 'sandbox' else plaid.Environment.Production

configuration = plaid.Configuration(
    host=host,
    api_key={
        'clientId': PLAID_CLIENT_ID,
        'secret': PLAID_SECRET,
        'plaidVersion': '2020-09-14'
    }
)

client = plaid_api.PlaidApi(plaid.ApiClient(configuration))

# Request models


class ExchangeTokenRequest(BaseModel):
    public_token: str


class TransactionRequest(BaseModel):
    access_token: str


@app.post("/api/create_link_token")
async def create_link_token():
    try:
        user = LinkTokenCreateRequestUser(
            client_user_id=str(uuid.uuid4())
        )

        request = LinkTokenCreateRequest(
            products=[Products(product) for product in PLAID_PRODUCTS],
            client_name="Grub",
            country_codes=[CountryCode(code) for code in PLAID_COUNTRY_CODES],
            language='en',
            user=user
        )

        if PLAID_REDIRECT_URI:
            request['redirect_uri'] = PLAID_REDIRECT_URI

        response = client.link_token_create(request)
        return response.to_dict()

    except plaid.ApiException as e:
        raise HTTPException(
            status_code=e.status,
            detail={
                'status_code': e.status,
                'display_message': e.body.get('error_message', 'An error occurred'),
                'error_code': e.body.get('error_code', 'INTERNAL_SERVER_ERROR'),
                'error_type': e.body.get('error_type', 'API_ERROR')
            }
        )


@app.post("/api/exchange_token")
async def exchange_public_token(request: ExchangeTokenRequest):
    try:
        exchange_request = ItemPublicTokenExchangeRequest(
            public_token=request.public_token
        )
        response = client.item_public_token_exchange(exchange_request)
        global access_token
        access_token = response['access_token']

        return {
            'access_token': response['access_token'],
            'item_id': response['item_id']
        }
    except plaid.ApiException as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/transactions")
async def get_transactions(request: TransactionRequest):
    cursor = ''

    # New transaction updates since "cursor"
    added = []
    modified = []
    removed = []  # Removed transaction ids
    has_more = True
    try:
        # Iterate through each page of new transaction updates for item
        while has_more:
            request = TransactionsSyncRequest(
                access_token=access_token,
                cursor=cursor,
            )
            response = client.transactions_sync(request).to_dict()
            cursor = response['next_cursor']
            # If no transactions are available yet, wait and poll the endpoint.
            # Normally, we would listen for a webhook, but the Quickstart doesn't
            # support webhooks. For a webhook example, see
            # https://github.com/plaid/tutorial-resources or
            # https://github.com/plaid/pattern
            if cursor == '':
                time.sleep(2)
                continue
            # If cursor is not an empty string, we got results,
            # so add this page of results
            added.extend(response['added'])
            modified.extend(response['modified'])
            removed.extend(response['removed'])
            has_more = response['has_more']

        # Return the 8 most recent transactions
        latest_transactions = sorted(added, key=lambda t: t['date'])[-8:]
        return {
            'latest_transactions': latest_transactions}

    except plaid.ApiException as e:
        return {"error": str(e)}


# to Run server: uvicorn newServer:app --reload
if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
