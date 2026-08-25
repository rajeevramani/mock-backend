#!/usr/bin/env python3
"""
OpenAPI Traffic Generator
Generates random API requests based on the OpenAPI spec for testing purposes.
"""

from __future__ import annotations

import argparse
import json
import random
import string
import sys
import time
from datetime import datetime, timedelta
from typing import Any

import requests
import yaml

# Faker-like data generators
FIRST_NAMES = ["John", "Jane", "Michael", "Sarah", "David", "Emily", "Robert", "Lisa", "James", "Maria"]
LAST_NAMES = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Wilson", "Taylor"]
CITIES = ["New York", "Los Angeles", "Chicago", "Houston", "Phoenix", "Philadelphia", "San Antonio", "San Diego"]
STATES = ["NY", "CA", "IL", "TX", "AZ", "PA", "TX", "CA"]
STREETS = ["Main Street", "Oak Avenue", "Maple Drive", "Cedar Lane", "Pine Road", "Elm Street", "Park Avenue"]
MERCHANTS = ["Amazon", "Walmart", "Target", "Costco", "Home Depot", "Best Buy", "Starbucks", "McDonald's"]
CATEGORIES = ["shopping", "groceries", "dining", "utilities", "entertainment", "travel", "healthcare"]
SYMBOLS = ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "META", "NVDA", "JPM", "V", "WMT"]
COMPANY_NAMES = ["Apple Inc.", "Alphabet Inc.", "Microsoft Corp.", "Amazon.com Inc.", "Tesla Inc."]


def random_string(length: int = 10) -> str:
    return ''.join(random.choices(string.ascii_letters, k=length))


def random_email() -> str:
    return f"{random_string(8).lower()}@example.com"


def random_phone() -> str:
    return f"+1-555-{random.randint(100, 999)}-{random.randint(1000, 9999)}"


def random_date(days_ago: int = 365) -> str:
    if days_ago >= 0:
        date = datetime.now() - timedelta(days=random.randint(0, days_ago))
    else:
        # Negative days_ago means future date
        date = datetime.now() + timedelta(days=random.randint(0, abs(days_ago)))
    return date.strftime("%Y-%m-%d")


def random_datetime(days_ago: int = 30) -> str:
    if days_ago >= 0:
        dt = datetime.now() - timedelta(days=random.randint(0, days_ago), hours=random.randint(0, 23))
    else:
        # Negative days_ago means future datetime
        dt = datetime.now() + timedelta(days=random.randint(0, abs(days_ago)), hours=random.randint(0, 23))
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def random_account_number() -> str:
    return f"{random.randint(1000, 9999)}-{random.randint(1000, 9999)}-{random.randint(1000, 9999)}"


def random_amount(min_val: float = 10.0, max_val: float = 10000.0) -> float:
    return round(random.uniform(min_val, max_val), 2)


def generate_address() -> dict:
    idx = random.randint(0, len(CITIES) - 1)
    return {
        "street": f"{random.randint(1, 999)} {random.choice(STREETS)}",
        "city": CITIES[idx],
        "state": STATES[idx],
        "zipCode": f"{random.randint(10000, 99999)}",
        "country": "USA"
    }


def generate_coordinates() -> dict:
    return {
        "latitude": round(random.uniform(25.0, 48.0), 4),
        "longitude": round(random.uniform(-125.0, -70.0), 4)
    }


def generate_business_hours() -> dict:
    return {
        "monday": "9:00 AM - 5:00 PM",
        "tuesday": "9:00 AM - 5:00 PM",
        "wednesday": "9:00 AM - 5:00 PM",
        "thursday": "9:00 AM - 5:00 PM",
        "friday": "9:00 AM - 6:00 PM",
        "saturday": "10:00 AM - 2:00 PM",
        "sunday": "Closed"
    }


# Schema generators for each resource type
def generate_customer_input() -> dict:
    return {
        "firstName": random.choice(FIRST_NAMES),
        "lastName": random.choice(LAST_NAMES),
        "email": random_email(),
        "phone": random_phone(),
        "dateOfBirth": random_date(days_ago=20000),
        "ssn": f"***-**-{random.randint(1000, 9999)}",
        "address": generate_address(),
        "customerSince": random_date(days_ago=2000),
        "status": random.choice(["active", "inactive", "suspended"]),
        "kycVerified": random.choice([True, False])
    }


def generate_account_input() -> dict:
    return {
        "customerId": random.randint(1, 10),
        "accountNumber": random_account_number(),
        "accountType": random.choice(["checking", "savings", "money_market"]),
        "accountName": random.choice(["Primary Checking", "Savings Account", "Money Market"]),
        "balance": random_amount(100, 50000),
        "availableBalance": random_amount(100, 50000),
        "currency": "USD",
        "status": random.choice(["active", "inactive", "closed"]),
        "openedDate": random_date(days_ago=2000),
        "interestRate": round(random.uniform(0.01, 5.0), 2),
        "overdraftLimit": random_amount(0, 1000),
        "minimumBalance": random_amount(0, 500)
    }


def generate_transaction_input() -> dict:
    return {
        "accountId": random.randint(1, 10),
        "type": random.choice(["debit", "credit"]),
        "category": random.choice(CATEGORIES),
        "amount": random_amount(5, 500),
        "currency": "USD",
        "description": f"{random.choice(MERCHANTS)} Purchase",
        "merchantName": random.choice(MERCHANTS),
        "merchantCategory": random.choice(["retail", "online_retail", "restaurant", "grocery"]),
        "date": random_datetime(),
        "status": random.choice(["pending", "completed", "failed", "cancelled"]),
        "reference": f"TXN-{datetime.now().strftime('%Y%m%d')}{random.randint(10000, 99999)}"
    }


def generate_card_input() -> dict:
    card_type = random.choice(["debit", "credit"])
    result = {
        "customerId": random.randint(1, 10),
        "accountId": random.randint(1, 10) if card_type == "debit" else None,
        "cardNumber": f"****-****-****-{random.randint(1000, 9999)}",
        "cardType": card_type,
        "cardBrand": random.choice(["Visa", "Mastercard", "Amex", "Discover"]),
        "cardName": f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}",
        "expiryDate": f"{random.randint(1, 12):02d}/{random.randint(2025, 2030)}",
        "status": random.choice(["active", "inactive", "blocked", "expired"]),
        "dailyLimit": random_amount(1000, 10000),
        "monthlyLimit": random_amount(10000, 50000),
        "isContactless": random.choice([True, False]),
        "isVirtual": random.choice([True, False]),
        "issueDate": random_date(days_ago=365)
    }
    if card_type == "credit":
        result["creditLimit"] = random_amount(5000, 50000)
        result["availableCredit"] = random_amount(1000, result["creditLimit"])
        result["currentBalance"] = random_amount(0, 5000)
        result["minimumPayment"] = random_amount(25, 500)
        result["paymentDueDate"] = random_date(days_ago=-30)
        result["apr"] = round(random.uniform(12.0, 25.0), 2)
    return result


def generate_beneficiary_input() -> dict:
    return {
        "customerId": random.randint(1, 10),
        "name": f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}",
        "nickname": random.choice(["Mom", "Dad", "Landlord", "Utilities", "Friend"]),
        "accountNumber": f"****{random.randint(1000, 9999)}",
        "bankName": random.choice(["Chase Bank", "Bank of America", "Wells Fargo", "Citibank"]),
        "routingNumber": f"{random.randint(100000000, 999999999)}",
        "accountType": random.choice(["checking", "savings"]),
        "email": random_email(),
        "phone": random_phone(),
        "status": random.choice(["active", "inactive"]),
        "addedDate": random_date(days_ago=500)
    }


def generate_transfer_input() -> dict:
    transfer_type = random.choice(["internal", "external"])
    return {
        "customerId": random.randint(1, 10),
        "fromAccountId": random.randint(1, 10),
        "toAccountId": random.randint(1, 10) if transfer_type == "internal" else None,
        "beneficiaryId": random.randint(1, 5) if transfer_type == "external" else None,
        "amount": random_amount(50, 5000),
        "currency": "USD",
        "type": transfer_type,
        "description": random.choice(["Monthly savings", "Rent payment", "Bill payment", "Gift"]),
        "status": random.choice(["pending", "scheduled", "completed", "failed", "cancelled"]),
        "reference": f"TRF-{datetime.now().strftime('%Y%m%d')}{random.randint(10000, 99999)}",
        "recurring": random.choice([True, False]),
        "frequency": random.choice(["daily", "weekly", "biweekly", "monthly", "quarterly", "annually"])
    }


def generate_loan_input() -> dict:
    principal = random_amount(5000, 500000)
    return {
        "customerId": random.randint(1, 10),
        "loanType": random.choice(["mortgage", "auto", "personal", "business"]),
        "loanName": random.choice(["Home Mortgage", "Auto Loan", "Personal Loan", "Business Loan"]),
        "principalAmount": principal,
        "currentBalance": random_amount(1000, principal),
        "interestRate": round(random.uniform(3.0, 15.0), 2),
        "monthlyPayment": random_amount(100, 5000),
        "termMonths": random.choice([36, 60, 120, 180, 240, 360]),
        "remainingMonths": random.randint(1, 360),
        "startDate": random_date(days_ago=2000),
        "endDate": random_date(days_ago=-3650),
        "nextPaymentDate": random_date(days_ago=-30),
        "status": random.choice(["active", "paid_off", "defaulted", "deferred"]),
        "collateral": f"{random.randint(1, 999)} {random.choice(STREETS)}, {random.choice(CITIES)}",
        "latePaymentFee": random_amount(25, 200),
        "autopayEnabled": random.choice([True, False])
    }


def generate_bill_payment_input() -> dict:
    return {
        "customerId": random.randint(1, 10),
        "payeeName": random.choice(["ConEdison", "Verizon", "AT&T", "Netflix", "Spotify"]),
        "payeeAccountNumber": f"****{random.randint(1000, 9999)}",
        "category": random.choice(["utilities", "telecom", "streaming", "insurance"]),
        "amount": random_amount(20, 500),
        "frequency": random.choice(["once", "weekly", "biweekly", "monthly", "quarterly", "annually"]),
        "nextDueDate": random_date(days_ago=-30),
        "autopayEnabled": random.choice([True, False]),
        "fromAccountId": random.randint(1, 10),
        "status": random.choice(["active", "inactive", "cancelled"])
    }


def generate_notification_input() -> dict:
    return {
        "customerId": random.randint(1, 10),
        "type": random.choice(["transaction", "payment_due", "deposit", "security", "low_balance", "promotion"]),
        "title": random.choice(["Purchase Alert", "Payment Reminder", "Low Balance", "Security Alert"]),
        "message": f"A transaction of ${random_amount(10, 500)} was processed.",
        "date": random_datetime(),
        "read": random.choice([True, False]),
        "priority": random.choice(["low", "normal", "high"])
    }


def generate_branch_input() -> dict:
    return {
        "name": f"{random.choice(CITIES)} {random.choice(['Main', 'Downtown', 'Central'])} Branch",
        "address": f"{random.randint(1, 999)} {random.choice(STREETS)}, {random.choice(CITIES)}",
        "phone": random_phone(),
        "email": f"branch{random.randint(1, 100)}@mockbank.com",
        "hours": generate_business_hours(),
        "services": random.sample(["deposits", "withdrawals", "loans", "safe_deposit", "notary"], k=3),
        "hasATM": random.choice([True, False]),
        "hasDriveThru": random.choice([True, False]),
        "coordinates": generate_coordinates()
    }


def generate_atm_input() -> dict:
    return {
        "name": f"{random.choice(CITIES)} ATM {random.randint(1, 100)}",
        "address": f"{random.randint(1, 999)} {random.choice(STREETS)}, {random.choice(CITIES)}",
        "status": random.choice(["online", "offline", "maintenance"]),
        "features": random.sample(["cash_withdrawal", "deposits", "balance_inquiry", "transfers"], k=3),
        "is24Hours": random.choice([True, False]),
        "coordinates": generate_coordinates()
    }


def generate_exchange_rate_input() -> dict:
    currencies = ["USD", "EUR", "GBP", "JPY", "CAD", "AUD", "CHF"]
    from_curr = random.choice(currencies)
    to_curr = random.choice([c for c in currencies if c != from_curr])
    return {
        "fromCurrency": from_curr,
        "toCurrency": to_curr,
        "rate": round(random.uniform(0.5, 150.0), 4),
        "lastUpdated": random_datetime(days_ago=1)
    }


def generate_investment_input() -> dict:
    return {
        "customerId": random.randint(1, 10),
        "accountType": random.choice(["brokerage", "ira", "401k", "roth_ira"]),
        "accountNumber": f"INV-{random.randint(100, 999)}-{random.randint(1000, 9999)}",
        "totalValue": random_amount(10000, 500000),
        "cashBalance": random_amount(1000, 20000),
        "contributionLimit": random_amount(6000, 23000),
        "contributedYTD": random_amount(0, 23000),
        "status": random.choice(["active", "inactive", "closed"]),
        "openedDate": random_date(days_ago=2000)
    }


def generate_holding_input() -> dict:
    symbol = random.choice(SYMBOLS)
    quantity = random.randint(1, 500)
    avg_cost = random_amount(50, 500)
    current_price = avg_cost * random.uniform(0.8, 1.5)
    market_value = quantity * current_price
    gain = market_value - (quantity * avg_cost)
    return {
        "investmentId": random.randint(1, 5),
        "symbol": symbol,
        "name": random.choice(COMPANY_NAMES),
        "quantity": quantity,
        "averageCost": round(avg_cost, 2),
        "currentPrice": round(current_price, 2),
        "marketValue": round(market_value, 2),
        "gain": round(gain, 2),
        "gainPercent": round((gain / (quantity * avg_cost)) * 100, 2)
    }


def generate_bank_info_input() -> dict:
    return {
        "name": "MockBank Financial",
        "routingNumber": f"{random.randint(100000000, 999999999)}",
        "swiftCode": f"MOCK{random.choice(['US', 'UK', 'EU'])}{random.randint(10, 99)}",
        "customerService": "+1-800-555-BANK",
        "fraudHotline": "+1-800-555-FRAUD",
        "website": "https://www.mockbank.com"
    }


# Map resource paths to generators
GENERATORS = {
    "/v2/api/customers": generate_customer_input,
    "/v2/api/accounts": generate_account_input,
    "/v2/api/transactions": generate_transaction_input,
    "/v2/api/cards": generate_card_input,
    "/v2/api/beneficiaries": generate_beneficiary_input,
    "/v2/api/transfers": generate_transfer_input,
    "/v2/api/loans": generate_loan_input,
    "/v2/api/billPayments": generate_bill_payment_input,
    "/v2/api/notifications": generate_notification_input,
    "/v2/api/branches": generate_branch_input,
    "/v2/api/atms": generate_atm_input,
    "/v2/api/exchangeRates": generate_exchange_rate_input,
    "/v2/api/investments": generate_investment_input,
    "/v2/api/holdings": generate_holding_input,
    "/v2/api/bankInfo": generate_bank_info_input,
}


def load_openapi_spec(spec_path: str) -> dict:
    with open(spec_path, 'r') as f:
        return yaml.safe_load(f)


def get_available_endpoints(spec: dict) -> list:
    """Extract all endpoints and their methods from the spec."""
    endpoints = []
    for path, methods in spec.get('paths', {}).items():
        for method in methods:
            if method in ['get', 'post', 'put', 'patch', 'delete']:
                endpoints.append({
                    'path': path,
                    'method': method.upper(),
                    'operation': methods[method]
                })
    return endpoints


def filter_endpoints(endpoints: list, allow_mutations: bool = False) -> list:
    """Keep state-changing operations out of ordinary traffic unless explicitly enabled."""
    if allow_mutations:
        return endpoints
    return [endpoint for endpoint in endpoints if endpoint['method'] == 'GET']


def resolve_local_ref(spec: dict, value: dict) -> dict:
    """Resolve the local component references used by the curated demo contract."""
    reference = value.get('$ref')
    if not reference:
        return value
    if not reference.startswith('#/'):
        raise ValueError(f"Only local OpenAPI references are supported: {reference}")
    resolved = spec
    for segment in reference[2:].split('/'):
        resolved = resolved[segment]
    return resolved


def generate_request_body(path: str, method: str) -> dict | None:
    """Generate appropriate request body based on path."""
    if method in ['GET', 'DELETE']:
        return None

    if path == '/v2/api/cards/{id}/block':
        return {'reason': 'suspected_fraud'}
    if path == '/v2/api/notifications':
        return {
            'customerId': 2,
            'type': 'security',
            'title': 'Synthetic card blocked',
            'message': 'Your synthetic card ending 7756 was blocked after suspected fraud.',
            'priority': 'high'
        }

    # Find the base path (without {id})
    base_path = path.split('/{id}')[0] if '/{id}' in path else path

    generator = GENERATORS.get(base_path)
    if generator:
        return generator()
    return None


def generate_query_params(path: str, spec: dict) -> dict:
    """Generate random query parameters for GET requests."""
    params = {}
    path_spec = spec.get('paths', {}).get(path, {}).get('get', {})
    parameters = path_spec.get('parameters', [])

    for param in parameters:
        param = resolve_local_ref(spec, param)
        if param.get('in') == 'query' and random.random() > 0.5:
            schema = param.get('schema', {})
            if schema.get('type') == 'integer':
                params[param['name']] = 4 if param['name'] == 'accountId' else 2
            elif schema.get('type') == 'string':
                if 'enum' in schema:
                    params[param['name']] = random.choice(schema['enum'])
            elif schema.get('type') == 'boolean':
                params[param['name']] = random.choice(['true', 'false'])

        elif param.get('in') == 'query' and param.get('required'):
            schema = param.get('schema', {})
            if schema.get('type') == 'integer':
                params[param['name']] = 4 if param['name'] == 'accountId' else 2

    return params


def generate_bad_request(fault_profile: str = 'stateful') -> dict:
    """Generate a verified negative case for the selected backend profile."""
    legacy_bad_requests = [
        # 404 - Non-existent resources
        {'method': 'GET', 'path': '/v2/api/customers/999', 'body': None, 'headers': {'Content-Type': 'application/json'}, 'expected_status': 404},
        {'method': 'GET', 'path': '/v2/api/accounts/999', 'body': None, 'headers': {'Content-Type': 'application/json'}, 'expected_status': 404},
        {'method': 'GET', 'path': '/v2/api/transactions/999', 'body': None, 'headers': {'Content-Type': 'application/json'}, 'expected_status': 404},
        {'method': 'GET', 'path': '/v2/api/cards/999', 'body': None, 'headers': {'Content-Type': 'application/json'}, 'expected_status': 404},
        {'method': 'GET', 'path': '/v2/api/loans/999', 'body': None, 'headers': {'Content-Type': 'application/json'}, 'expected_status': 404},
        {'method': 'GET', 'path': '/v2/api/nonexistent', 'body': None, 'headers': {'Content-Type': 'application/json'}, 'expected_status': 404},
        # 415 - Wrong content type
        {'method': 'POST', 'path': '/v2/api/customers', 'body': {'name': 'test'}, 'headers': {'Content-Type': 'application/xml'}, 'expected_status': 415},
        # 400 - Missing required fields
        {'method': 'POST', 'path': '/v2/api/accounts', 'body': {'customerId': None, 'accountType': 'checking'}, 'headers': {'Content-Type': 'application/json'}, 'expected_status': 400},
        {'method': 'POST', 'path': '/v2/api/customers', 'body': {}, 'headers': {'Content-Type': 'application/json'}, 'expected_status': 400},
        {'method': 'POST', 'path': '/v2/api/transactions', 'body': {'accountId': None}, 'headers': {'Content-Type': 'application/json'}, 'expected_status': 400},
        {'method': 'POST', 'path': '/v2/api/cards', 'body': {'customerId': None}, 'headers': {'Content-Type': 'application/json'}, 'expected_status': 400},
        {'method': 'POST', 'path': '/v2/api/loans', 'body': {}, 'headers': {'Content-Type': 'application/json'}, 'expected_status': 400},
        {'method': 'POST', 'path': '/v2/api/transfers', 'body': {'fromAccountId': None}, 'headers': {'Content-Type': 'application/json'}, 'expected_status': 400},
        # 400 - Invalid email format
        {'method': 'POST', 'path': '/v2/api/customers', 'body': {'firstName': 'Test', 'email': 'invalid-email'}, 'headers': {'Content-Type': 'application/json'}, 'expected_status': 400},
        # 400 - Invalid enum values
        {'method': 'POST', 'path': '/v2/api/accounts', 'body': {'customerId': 1, 'accountType': 'invalid_type'}, 'headers': {'Content-Type': 'application/json'}, 'expected_status': 400},
        {'method': 'POST', 'path': '/v2/api/cards', 'body': {'customerId': 1, 'cardType': 'invalid_type'}, 'headers': {'Content-Type': 'application/json'}, 'expected_status': 400},
        {'method': 'POST', 'path': '/v2/api/loans', 'body': {'customerId': 1, 'loanType': 'invalid_type'}, 'headers': {'Content-Type': 'application/json'}, 'expected_status': 400},
        # 400 - Invalid data types
        {'method': 'POST', 'path': '/v2/api/accounts', 'body': {'customerId': 'not_a_number', 'accountType': 'checking'}, 'headers': {'Content-Type': 'application/json'}, 'expected_status': 400},
        {'method': 'POST', 'path': '/v2/api/transactions', 'body': {'accountId': 1, 'amount': 'not_a_number'}, 'headers': {'Content-Type': 'application/json'}, 'expected_status': 400},
        # 422 - Invalid data
        {'method': 'POST', 'path': '/v2/api/transfers', 'body': {'amount': -100, 'fromAccountId': 1, 'toAccountId': 2}, 'headers': {'Content-Type': 'application/json'}, 'expected_status': 422},
        {'method': 'POST', 'path': '/v2/api/transactions', 'body': {'accountId': 1, 'amount': -50, 'type': 'debit'}, 'headers': {'Content-Type': 'application/json'}, 'expected_status': 422},
        # 409 - Conflict
        {'method': 'DELETE', 'path': '/v2/api/accounts/1', 'body': None, 'headers': {'Content-Type': 'application/json'}, 'expected_status': 409},
        # 401 - Unauthorized
        {'method': 'GET', 'path': '/v2/api/internal/admin', 'body': None, 'headers': {'Content-Type': 'application/json'}, 'expected_status': 401},
        # 403 - Forbidden
        {'method': 'DELETE', 'path': '/v2/api/customers/1', 'body': None, 'headers': {'Content-Type': 'application/json'}, 'expected_status': 403},
        # 500 - Internal Server Error
        {'method': 'GET', 'path': '/v2/api/customers/500', 'body': None, 'headers': {'Content-Type': 'application/json'}, 'expected_status': 500},
        {'method': 'GET', 'path': '/v2/api/accounts/500', 'body': None, 'headers': {'Content-Type': 'application/json'}, 'expected_status': 500},
        {'method': 'GET', 'path': '/v2/api/transactions/500', 'body': None, 'headers': {'Content-Type': 'application/json'}, 'expected_status': 500},
        {'method': 'POST', 'path': '/v2/api/transfers/process', 'body': {'amount': 1000000}, 'headers': {'Content-Type': 'application/json'}, 'expected_status': 500},
        {'method': 'POST', 'path': '/v2/api/payments/batch', 'body': {'count': 100}, 'headers': {'Content-Type': 'application/json'}, 'expected_status': 500},
        # 502 - Bad Gateway
        {'method': 'GET', 'path': '/v2/api/external/credit-score', 'body': None, 'headers': {'Content-Type': 'application/json'}, 'expected_status': 502},
        # 503 - Service Unavailable
        {'method': 'GET', 'path': '/v2/api/maintenance/status', 'body': None, 'headers': {'Content-Type': 'application/json'}, 'expected_status': 503},
        {'method': 'POST', 'path': '/v2/api/reports/generate', 'body': {'type': 'annual'}, 'headers': {'Content-Type': 'application/json'}, 'expected_status': 503},
        # 504 - Gateway Timeout
        {'method': 'GET', 'path': '/v2/api/external/verification', 'body': None, 'headers': {'Content-Type': 'application/json'}, 'expected_status': 504},
    ]
    stateful_bad_requests = [
        {'method': 'GET', 'path': '/v2/api/customers/999', 'body': None, 'headers': {'Content-Type': 'application/json'}, 'expected_status': 404},
        {'method': 'GET', 'path': '/v2/api/accounts', 'body': None, 'headers': {'Content-Type': 'application/json'}, 'expected_status': 400},
        {'method': 'GET', 'path': '/v2/api/accounts?customerId=999', 'body': None, 'headers': {'Content-Type': 'application/json'}, 'expected_status': 404},
        {'method': 'POST', 'path': '/v2/api/cards/999/block', 'body': {'reason': 'lost'}, 'headers': {'Content-Type': 'application/json'}, 'expected_status': 404},
        {'method': 'POST', 'path': '/v2/api/cards/3/block', 'body': {'reason': 'invalid'}, 'headers': {'Content-Type': 'application/json'}, 'expected_status': 400},
        {'method': 'POST', 'path': '/v2/api/notifications', 'body': {'customerId': 999, 'type': 'security', 'title': 'Test', 'message': 'Synthetic test'}, 'headers': {'Content-Type': 'application/json'}, 'expected_status': 404},
    ]
    cases = legacy_bad_requests if fault_profile == 'mockserver' else stateful_bad_requests
    return random.choice(cases)


def make_request(base_url: str, endpoint: dict, spec: dict, verbose: bool = False, bad_request: dict = None, extra_headers: dict[str, str] | None = None) -> dict:
    """Make a single API request."""
    if bad_request:
        method = bad_request['method']
        actual_path = bad_request['path']
        url = f"{base_url}{actual_path}"
        params = {}
        body = bad_request['body']
        headers = bad_request['headers']
        expected_status = bad_request.get('expected_status')
    else:
        path = endpoint['path']
        method = endpoint['method']

        # Replace path parameters
        stable_id = '3' if path.startswith('/v2/api/cards/') else '2'
        actual_path = path.replace('{id}', stable_id)
        url = f"{base_url}{actual_path}"

        # Generate query params for GET
        params = generate_query_params(path, spec) if method == 'GET' else {}

        # Generate body for POST/PUT/PATCH
        body = generate_request_body(path, method)

        headers = {'Content-Type': 'application/json'}
        expected_status = None

    if extra_headers:
        headers.update(extra_headers)

    try:
        if verbose:
            print(f"\n{'='*60}")
            print(f"{method} {url}")
            if params:
                print(f"Query: {params}")
            if body:
                print(f"Body: {json.dumps(body, indent=2)[:500]}...")

        response = requests.request(
            method=method,
            url=url,
            params=params,
            json=body,
            headers=headers,
            timeout=10
        )

        result = {
            'method': method,
            'path': actual_path,
            'status_code': response.status_code,
            'expected_status': expected_status,
            'negative_case': expected_status is not None,
            'success': response.status_code == expected_status if expected_status is not None else response.status_code < 400,
            'response_time_ms': response.elapsed.total_seconds() * 1000
        }

        if verbose:
            print(f"Status: {response.status_code} ({response.elapsed.total_seconds()*1000:.1f}ms)")
            try:
                print(f"Response: {json.dumps(response.json(), indent=2)[:300]}...")
            except:
                print(f"Response: {response.text[:300]}...")

        return result

    except requests.exceptions.RequestException as e:
        if verbose:
            print(f"Error: {e}")
        return {
            'method': method,
            'path': actual_path,
            'status_code': 0,
            'expected_status': expected_status,
            'negative_case': expected_status is not None,
            'success': False,
            'error': str(e)
        }


def run_traffic_generator(
    spec_path: str,
    base_url: str,
    num_requests: int,
    delay_ms: int,
    verbose: bool,
    methods: list[str] | None = None,
    error_rate: float = 0.0,
    extra_headers: dict[str, str] | None = None,
    path_filters: list[str] | None = None,
    allow_mutations: bool = False
):
    """Run the traffic generator."""
    print(f"Loading OpenAPI spec from: {spec_path}")
    spec = load_openapi_spec(spec_path)

    endpoints = get_available_endpoints(spec)
    if methods:
        endpoints = [e for e in endpoints if e['method'] in methods]
    if path_filters:
        endpoints = [e for e in endpoints if any(f in e['path'] for f in path_filters)]
    endpoints = filter_endpoints(endpoints, allow_mutations=allow_mutations)

    if not endpoints:
        print(f"No endpoints matched filters (methods={methods}, paths={path_filters})")
        return

    print(f"Found {len(endpoints)} endpoints")
    print(f"Target: {base_url}")
    print(f"Requests: {num_requests}")
    print(f"Delay: {delay_ms}ms between requests")
    if error_rate > 0:
        print(f"Error rate: {error_rate*100:.0f}% bad requests")
    print("-" * 60)

    results = {
        'total': 0,
        'success': 0,
        'failed': 0,
        'bad_requests': 0,
        'by_method': {},
        'by_status': {},
        'avg_response_time': 0,
        'total_response_time': 0
    }

    for i in range(num_requests):
        # Decide if this should be a bad request
        is_bad_request = error_rate > 0 and random.random() < error_rate

        if is_bad_request:
            bad_req = generate_bad_request()
            if path_filters or methods:
                matching_bad = [b for b in [generate_bad_request() for _ in range(50)]
                                if (not path_filters or any(f in b['path'] for f in path_filters))
                                and (not methods or b['method'] in methods)]
                if matching_bad:
                    bad_req = matching_bad[0]
                else:
                    # No matching bad request found, fall back to normal request
                    endpoint = random.choice(endpoints)
                    result = make_request(base_url, endpoint, spec, verbose, extra_headers=extra_headers)
                    results['total'] += 1
                    if result['success']:
                        results['success'] += 1
                    else:
                        results['failed'] += 1
                    method = result['method']
                    results['by_method'][method] = results['by_method'].get(method, 0) + 1
                    status = result.get('status_code', 0)
                    results['by_status'][status] = results['by_status'].get(status, 0) + 1
                    if 'response_time_ms' in result:
                        results['total_response_time'] += result['response_time_ms']
                    if delay_ms > 0:
                        time.sleep(delay_ms / 1000.0)
                    continue
            endpoint = {'path': bad_req['path'], 'method': bad_req['method']}
            result = make_request(base_url, endpoint, spec, verbose, bad_request=bad_req, extra_headers=extra_headers)
            results['bad_requests'] += 1
        else:
            endpoint = random.choice(endpoints)
            result = make_request(base_url, endpoint, spec, verbose, extra_headers=extra_headers)

        results['total'] += 1
        if result['success']:
            results['success'] += 1
        else:
            results['failed'] += 1

        method = result['method']
        results['by_method'][method] = results['by_method'].get(method, 0) + 1

        status = result.get('status_code', 0)
        results['by_status'][status] = results['by_status'].get(status, 0) + 1

        if 'response_time_ms' in result:
            results['total_response_time'] += result['response_time_ms']

        if not verbose and (i + 1) % 10 == 0:
            print(f"Progress: {i + 1}/{num_requests} requests completed")

        if delay_ms > 0:
            time.sleep(delay_ms / 1000.0)

    if results['total'] > 0:
        results['avg_response_time'] = results['total_response_time'] / results['total']

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total requests: {results['total']}")
    print(f"Passed verification: {results['success']} ({results['success']/results['total']*100:.1f}%)")
    print(f"Failed verification: {results['failed']} ({results['failed']/results['total']*100:.1f}%)")
    if results['bad_requests'] > 0:
        print(f"Bad requests sent: {results['bad_requests']} ({results['bad_requests']/results['total']*100:.1f}%)")
    print(f"Avg response time: {results['avg_response_time']:.1f}ms")
    print("\nBy Method:")
    for method, count in sorted(results['by_method'].items()):
        print(f"  {method}: {count}")
    print("\nBy Status Code:")
    for status, count in sorted(results['by_status'].items()):
        print(f"  {status}: {count}")

    return results


def main():
    parser = argparse.ArgumentParser(description='Generate random API traffic from OpenAPI spec')
    parser.add_argument('--spec', '-s', default='openapi.flowplane-demo.yaml',
                        help='Path to OpenAPI spec file (default: openapi.flowplane-demo.yaml)')
    parser.add_argument('--url', '-u', default='http://localhost:10097',
                        help='Base URL for API requests (default: http://localhost:10097)')
    parser.add_argument('--requests', '-n', type=int, default=100,
                        help='Number of requests to generate (default: 100)')
    parser.add_argument('--delay', '-d', type=int, default=100,
                        help='Delay between requests in ms (default: 100)')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Show detailed request/response info')
    parser.add_argument('--methods', '-m', nargs='+',
                        choices=['GET', 'POST', 'PUT', 'PATCH', 'DELETE'],
                        help='Filter to specific HTTP methods')
    parser.add_argument('--error-rate', '-e', type=float, default=0.0,
                        help='Percentage of bad requests to generate (0.0-1.0, default: 0.0)')
    parser.add_argument('--allow-mutations', action='store_true',
                        help='Allow POST/PUT/PATCH/DELETE requests that change sandbox state')
    parser.add_argument('--paths', '-p', nargs='+', default=[],
                        help='Filter to endpoints matching these path segments (e.g. --paths customers accounts)')
    parser.add_argument('--header', '-H', action='append', default=[],
                        help='Extra headers as "Key: Value" (can be repeated, e.g. -H "Authorization: Bearer tok123")')

    args = parser.parse_args()

    if args.methods and any(method != 'GET' for method in args.methods) and not args.allow_mutations:
        parser.error('state-changing methods require --allow-mutations')

    extra_headers = {}
    for h in args.header:
        if ':' not in h:
            parser.error(f'Invalid header format "{h}", expected "Key: Value"')
        key, value = h.split(':', 1)
        extra_headers[key.strip()] = value.strip()

    results = run_traffic_generator(
        spec_path=args.spec,
        base_url=args.url,
        num_requests=args.requests,
        delay_ms=args.delay,
        verbose=args.verbose,
        methods=args.methods,
        error_rate=args.error_rate,
        extra_headers=extra_headers,
        path_filters=args.paths if args.paths else None,
        allow_mutations=args.allow_mutations
    )
    return 1 if results and results['failed'] else 0


if __name__ == '__main__':
    sys.exit(main())
